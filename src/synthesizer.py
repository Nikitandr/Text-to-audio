"""
Модуль синтеза речи через Yandex SpeechKit API v3
"""

import os
import time
import tempfile
from typing import List, Optional, Dict, Any
from pathlib import Path
import structlog

# Импорт Yandex SpeechKit SDK
try:
    from speechkit import model_repository, configure_credentials, creds
except ImportError:
    model_repository = None
    configure_credentials = None
    creds = None

from auth import get_token_manager, YandexAuthError
from text_processor import TextChunk, clean_text_for_synthesis
from utils import ProgressTracker, StatisticsCollector, ensure_directory

logger = structlog.get_logger(__name__)


class SynthesizerError(Exception):
    """Исключение для ошибок синтеза речи"""
    pass


class RateLimiter:
    """Класс для контроля частоты запросов"""
    
    def __init__(self, requests_per_second: float = None):
        """
        Инициализация ограничителя частоты
        
        Args:
            requests_per_second: Максимальное количество запросов в секунду
        """
        self.requests_per_second = requests_per_second or float(os.getenv('REQUESTS_PER_SECOND', '35'))
        self.min_interval = 1.0 / self.requests_per_second
        self.last_request_time = 0.0
    
    def wait_if_needed(self) -> None:
        """Ожидание если необходимо соблюсти лимит"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()


class SpeechSynthesizer:
    """Основной класс для синтеза речи"""
    
    def __init__(self, 
                 voice: str = None,
                 role: str = None,
                 temp_dir: str = None):
        """
        Инициализация синтезатора
        
        Args:
            voice: Голос для синтеза (по умолчанию jane)
            role: Роль голоса (по умолчанию good)
            temp_dir: Директория для временных файлов
        """
        if model_repository is None:
            raise SynthesizerError("yandex-speechkit не установлен")
        
        self.voice = voice or os.getenv('DEFAULT_VOICE', 'jane')
        self.role = role or os.getenv('DEFAULT_ROLE', 'good')
        self.temp_dir = temp_dir or os.getenv('TEMP_DIR', tempfile.gettempdir())
        
        # Настройки retry
        self.max_retries = int(os.getenv('MAX_RETRIES', '3'))
        self.retry_delay = float(os.getenv('RETRY_DELAY', '1.0'))
        
        # Ограничитель частоты запросов
        self.rate_limiter = RateLimiter()
        
        # Статистика
        self.stats = StatisticsCollector()
        
        # Инициализация SDK
        self._initialize_sdk()
        
        logger.info(
            "Синтезатор речи инициализирован",
            voice=self.voice,
            role=self.role,
            temp_dir=self.temp_dir
        )
    
    def _initialize_sdk(self) -> None:
        """Инициализация Yandex SpeechKit SDK"""
        try:
            # Получаем токен для аутентификации
            token_manager = get_token_manager()
            iam_token = token_manager.get_iam_token()
            
            # Настраиваем credentials для SDK
            configure_credentials(
                yandex_credentials=creds.YandexCredentials(
                    iam_token=iam_token
                )
            )
            
            # Создаем модель синтеза
            self.model = model_repository.synthesis_model()
            
            # Настраиваем параметры модели
            self.model.voice = self.voice
            self.model.role = self.role
            
            logger.info("SpeechKit SDK успешно инициализирован")
            
        except Exception as e:
            raise SynthesizerError(f"Ошибка инициализации SpeechKit SDK: {e}")
    
    def synthesize_chunk(self, chunk: TextChunk, output_path: str = None) -> str:
        """
        Синтез одного фрагмента текста
        
        Args:
            chunk: Фрагмент текста для синтеза
            output_path: Путь для сохранения аудио (опционально)
        
        Returns:
            Путь к созданному аудиофайлу
        """
        if chunk.processed:
            logger.debug(f"Фрагмент {chunk.index} уже обработан")
            return chunk.audio_file
        
        # Очищаем текст для синтеза
        clean_text = clean_text_for_synthesis(chunk.text)
        
        if not clean_text.strip():
            raise SynthesizerError(f"Пустой текст после очистки в фрагменте {chunk.index}")
        
        # Генерируем путь для выходного файла
        if output_path is None:
            ensure_directory(self.temp_dir)
            output_path = os.path.join(
                self.temp_dir, 
                f"chunk_{chunk.index:04d}.wav"
            )
        
        logger.debug(
            "Начинаем синтез фрагмента",
            chunk_index=chunk.index,
            chunk_length=chunk.length,
            output_path=output_path
        )
        
        # Синтез с retry логикой
        for attempt in range(self.max_retries):
            try:
                # Соблюдаем лимит частоты запросов
                self.rate_limiter.wait_if_needed()
                
                # Выполняем синтез
                logger.debug(
                    "Параметры синтеза",
                    text_length=len(clean_text),
                    voice=self.model.voice,
                    role=self.model.role
                )
                
                result = self.model.synthesize(
                    clean_text,
                    raw_format=False
                )
                
                # Сохраняем результат
                result.export(output_path, 'wav')
                
                # Проверяем, что файл создан
                if not os.path.exists(output_path):
                    raise SynthesizerError("Аудиофайл не был создан")
                
                # Обновляем информацию о фрагменте
                chunk.processed = True
                chunk.audio_file = output_path
                
                # Обновляем статистику
                self.stats.add_request_stats(True)
                
                logger.debug(
                    "Фрагмент успешно синтезирован",
                    chunk_index=chunk.index,
                    output_file=output_path,
                    attempt=attempt + 1
                )
                
                return output_path
                
            except Exception as e:
                error_msg = f"Ошибка синтеза фрагмента {chunk.index}, попытка {attempt + 1}: {e}"
                logger.warning(error_msg)
                
                # Обновляем статистику
                self.stats.add_request_stats(False, str(e))
                
                if attempt < self.max_retries - 1:
                    # Ждем перед повторной попыткой
                    sleep_time = self.retry_delay * (2 ** attempt)  # Экспоненциальный backoff
                    time.sleep(sleep_time)
                    
                    # Пробуем обновить токен
                    try:
                        self._refresh_credentials()
                    except Exception as refresh_error:
                        logger.warning(f"Не удалось обновить credentials: {refresh_error}")
                else:
                    # Последняя попытка не удалась
                    raise SynthesizerError(f"Не удалось синтезировать фрагмент {chunk.index} после {self.max_retries} попыток: {e}")
    
    def _refresh_credentials(self) -> None:
        """Обновление credentials для SDK"""
        try:
            token_manager = get_token_manager()
            iam_token = token_manager.refresh_token()
            
            configure_credentials(
                yandex_credentials=creds.YandexCredentials(
                    iam_token=iam_token
                )
            )
            
            logger.debug("Credentials успешно обновлены")
            
        except Exception as e:
            logger.error(f"Ошибка обновления credentials: {e}")
            raise
    
    def synthesize_chunks(self, chunks: List[TextChunk]) -> List[str]:
        """
        Синтез списка фрагментов текста
        
        Args:
            chunks: Список фрагментов для синтеза
        
        Returns:
            Список путей к созданным аудиофайлам
        """
        if not chunks:
            raise SynthesizerError("Пустой список фрагментов для синтеза")
        
        logger.info(
            "Начинаем синтез фрагментов",
            total_chunks=len(chunks),
            total_characters=sum(chunk.length for chunk in chunks)
        )
        
        # Обновляем статистику
        total_chars = sum(chunk.length for chunk in chunks)
        self.stats.add_text_stats(total_chars, len(chunks))
        
        # Создаем трекер прогресса
        progress = ProgressTracker(len(chunks), "Синтез речи")
        
        audio_files = []
        successful_chunks = 0
        
        try:
            for chunk in chunks:
                try:
                    progress.set_description(f"Синтез фрагмента {chunk.index + 1}/{len(chunks)}")
                    
                    audio_file = self.synthesize_chunk(chunk)
                    audio_files.append(audio_file)
                    successful_chunks += 1
                    
                    progress.update(1)
                    
                except Exception as e:
                    logger.error(
                        "Ошибка синтеза фрагмента",
                        chunk_index=chunk.index,
                        error=str(e)
                    )
                    
                    # В случае ошибки добавляем None, чтобы сохранить порядок
                    audio_files.append(None)
                    
                    # Можно продолжить с остальными фрагментами
                    progress.update(1)
            
            # Закрываем прогресс и получаем статистику
            progress_stats = progress.close()
            
            logger.info(
                "Синтез фрагментов завершен",
                successful_chunks=successful_chunks,
                total_chunks=len(chunks),
                success_rate=successful_chunks / len(chunks),
                processing_time=progress_stats["elapsed_time"]
            )
            
            # Фильтруем None значения
            valid_audio_files = [f for f in audio_files if f is not None]
            
            if not valid_audio_files:
                raise SynthesizerError("Не удалось синтезировать ни одного фрагмента")
            
            return valid_audio_files
            
        except KeyboardInterrupt:
            logger.info("Синтез прерван пользователем")
            progress.close()
            raise
        except Exception as e:
            progress.close()
            raise SynthesizerError(f"Критическая ошибка синтеза: {e}")
    
    def get_synthesis_stats(self) -> Dict[str, Any]:
        """
        Получение статистики синтеза
        
        Returns:
            Словарь со статистикой
        """
        return self.stats.finalize()
    
    def cleanup_temp_files(self, audio_files: List[str]) -> int:
        """
        Очистка временных аудиофайлов
        
        Args:
            audio_files: Список путей к аудиофайлам
        
        Returns:
            Количество удаленных файлов
        """
        deleted_count = 0
        
        for audio_file in audio_files:
            if audio_file and os.path.exists(audio_file):
                try:
                    os.unlink(audio_file)
                    deleted_count += 1
                except OSError as e:
                    logger.warning(f"Не удалось удалить временный файл {audio_file}: {e}")
        
        logger.debug(f"Удалено {deleted_count} временных файлов")
        return deleted_count


# Глобальный экземпляр синтезатора
_synthesizer: Optional[SpeechSynthesizer] = None


def get_synthesizer() -> SpeechSynthesizer:
    """
    Получение глобального экземпляра синтезатора
    
    Returns:
        Экземпляр SpeechSynthesizer
    """
    global _synthesizer
    if _synthesizer is None:
        _synthesizer = SpeechSynthesizer()
    return _synthesizer


def synthesize_text_chunks(chunks: List[TextChunk]) -> List[str]:
    """
    Удобная функция для синтеза списка фрагментов
    
    Args:
        chunks: Список фрагментов текста
    
    Returns:
        Список путей к аудиофайлам
    """
    synthesizer = get_synthesizer()
    return synthesizer.synthesize_chunks(chunks)


def synthesize_single_chunk(chunk: TextChunk, output_path: str = None) -> str:
    """
    Удобная функция для синтеза одного фрагмента
    
    Args:
        chunk: Фрагмент текста
        output_path: Путь для сохранения
    
    Returns:
        Путь к аудиофайлу
    """
    synthesizer = get_synthesizer()
    return synthesizer.synthesize_chunk(chunk, output_path)


def test_synthesis() -> bool:
    """
    Тестирование синтеза речи
    
    Returns:
        True если тест прошел успешно
    """
    try:
        from text_processor import TextChunk
        
        # Создаем тестовый фрагмент
        test_chunk = TextChunk("Это тест синтеза речи.", 0)
        
        # Пробуем синтезировать
        synthesizer = get_synthesizer()
        audio_file = synthesizer.synthesize_chunk(test_chunk)
        
        # Проверяем, что файл создан
        if os.path.exists(audio_file):
            # Удаляем тестовый файл
            os.unlink(audio_file)
            logger.info("Тест синтеза речи прошел успешно")
            return True
        else:
            logger.error("Тестовый аудиофайл не был создан")
            return False
            
    except Exception as e:
        logger.error("Тест синтеза речи не прошел", error=str(e))
        return False


def estimate_synthesis_time(chunks: List[TextChunk]) -> float:
    """
    Оценка времени синтеза
    
    Args:
        chunks: Список фрагментов
    
    Returns:
        Примерное время в секундах
    """
    if not chunks:
        return 0.0
    
    # Примерная оценка: 1 секунда на запрос + время на rate limiting
    requests_per_second = float(os.getenv('REQUESTS_PER_SECOND', '35'))
    
    # Время на запросы
    request_time = len(chunks) / requests_per_second
    
    # Добавляем время на обработку (примерно 0.5 сек на запрос)
    processing_time = len(chunks) * 0.5
    
    return request_time + processing_time
