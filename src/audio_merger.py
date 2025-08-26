"""
Модуль для объединения аудиофрагментов в единый файл
"""

import os
import time
import tempfile
from typing import List, Optional, Dict, Any
from pathlib import Path
import structlog

# Импорт pydub для работы с аудио
try:
    from pydub import AudioSegment
    from pydub.utils import which
except ImportError:
    AudioSegment = None
    which = None

from utils import ensure_directory, format_file_size, format_duration

logger = structlog.get_logger(__name__)


class AudioMergerError(Exception):
    """Исключение для ошибок объединения аудио"""
    pass


class AudioMerger:
    """Класс для объединения аудиофрагментов"""
    
    def __init__(self, temp_dir: str = None):
        """
        Инициализация объединителя аудио
        
        Args:
            temp_dir: Директория для временных файлов
        """
        if AudioSegment is None:
            raise AudioMergerError("pydub не установлен")
        
        self.temp_dir = temp_dir or os.getenv('TEMP_DIR', tempfile.gettempdir())
        
        # Проверяем наличие ffmpeg
        self._check_ffmpeg()
        
        logger.info(
            "Объединитель аудио инициализирован",
            temp_dir=self.temp_dir
        )
    
    def _check_ffmpeg(self) -> None:
        """Проверка наличия ffmpeg"""
        if which is None:
            logger.warning("Не удалось проверить наличие ffmpeg")
            return
        
        ffmpeg_path = which("ffmpeg")
        if ffmpeg_path:
            logger.debug(f"ffmpeg найден: {ffmpeg_path}")
        else:
            logger.warning("ffmpeg не найден, некоторые форматы могут не поддерживаться")
    
    def merge_wav_files(self, audio_files: List[str], output_path: str) -> str:
        """
        Объединение WAV файлов в один
        
        Args:
            audio_files: Список путей к аудиофайлам
            output_path: Путь для сохранения результата
        
        Returns:
            Путь к объединенному файлу
        """
        if not audio_files:
            raise AudioMergerError("Пустой список аудиофайлов для объединения")
        
        # Фильтруем существующие файлы
        existing_files = [f for f in audio_files if f and os.path.exists(f)]
        
        if not existing_files:
            raise AudioMergerError("Не найдено ни одного существующего аудиофайла")
        
        if len(existing_files) != len(audio_files):
            missing_count = len(audio_files) - len(existing_files)
            logger.warning(f"Отсутствует {missing_count} аудиофайлов из {len(audio_files)}")
        
        logger.info(
            "Начинаем объединение аудиофайлов",
            total_files=len(existing_files),
            output_path=output_path
        )
        
        try:
            # Загружаем первый файл как основу
            combined_audio = AudioSegment.from_wav(existing_files[0])
            logger.debug(f"Загружен базовый файл: {existing_files[0]}")
            
            # Добавляем остальные файлы
            for i, audio_file in enumerate(existing_files[1:], 1):
                try:
                    audio_segment = AudioSegment.from_wav(audio_file)
                    combined_audio += audio_segment
                    
                    logger.debug(
                        f"Добавлен файл {i + 1}/{len(existing_files)}: {audio_file}",
                        duration=len(audio_segment) / 1000.0
                    )
                    
                except Exception as e:
                    logger.error(f"Ошибка загрузки файла {audio_file}: {e}")
                    # Продолжаем с остальными файлами
            
            # Создаем директорию для выходного файла
            output_dir = os.path.dirname(output_path)
            if output_dir:
                ensure_directory(output_dir)
            
            # Сохраняем объединенный файл
            combined_audio.export(output_path, format="wav")
            
            # Проверяем, что файл создан
            if not os.path.exists(output_path):
                raise AudioMergerError("Объединенный файл не был создан")
            
            # Получаем информацию о результате
            file_size = os.path.getsize(output_path)
            duration = len(combined_audio) / 1000.0  # в секундах
            
            logger.info(
                "Аудиофайлы успешно объединены",
                output_file=output_path,
                duration=format_duration(duration),
                file_size=format_file_size(file_size),
                merged_files=len(existing_files)
            )
            
            return output_path
            
        except Exception as e:
            raise AudioMergerError(f"Ошибка объединения аудиофайлов: {e}")
    
    def convert_format(self, input_path: str, output_path: str, target_format: str) -> str:
        """
        Конвертация аудиофайла в другой формат
        
        Args:
            input_path: Путь к исходному файлу
            output_path: Путь для сохранения результата
            target_format: Целевой формат (wav, mp3, ogg)
        
        Returns:
            Путь к сконвертированному файлу
        """
        if not os.path.exists(input_path):
            raise AudioMergerError(f"Исходный файл не найден: {input_path}")
        
        target_format = target_format.lower()
        supported_formats = ['wav', 'mp3', 'ogg']
        
        if target_format not in supported_formats:
            raise AudioMergerError(
                f"Неподдерживаемый формат: {target_format}. "
                f"Поддерживаемые форматы: {', '.join(supported_formats)}"
            )
        
        logger.info(
            "Начинаем конвертацию аудиофайла",
            input_file=input_path,
            output_file=output_path,
            target_format=target_format
        )
        
        try:
            # Загружаем исходный файл
            audio = AudioSegment.from_file(input_path)
            
            # Создаем директорию для выходного файла
            output_dir = os.path.dirname(output_path)
            if output_dir:
                ensure_directory(output_dir)
            
            # Настройки экспорта для разных форматов
            export_params = self._get_export_params(target_format)
            
            # Экспортируем в целевой формат
            audio.export(output_path, format=target_format, **export_params)
            
            # Проверяем, что файл создан
            if not os.path.exists(output_path):
                raise AudioMergerError("Сконвертированный файл не был создан")
            
            # Получаем информацию о результате
            input_size = os.path.getsize(input_path)
            output_size = os.path.getsize(output_path)
            duration = len(audio) / 1000.0
            
            logger.info(
                "Аудиофайл успешно сконвертирован",
                output_file=output_path,
                duration=format_duration(duration),
                input_size=format_file_size(input_size),
                output_size=format_file_size(output_size),
                compression_ratio=output_size / input_size if input_size > 0 else 0
            )
            
            return output_path
            
        except Exception as e:
            raise AudioMergerError(f"Ошибка конвертации аудиофайла: {e}")
    
    def _get_export_params(self, format_name: str) -> Dict[str, Any]:
        """
        Получение параметров экспорта для формата
        
        Args:
            format_name: Название формата
        
        Returns:
            Словарь с параметрами
        """
        params = {}
        
        if format_name == 'mp3':
            params.update({
                'bitrate': '128k',
                'parameters': ['-q:a', '2']  # Качество VBR
            })
        elif format_name == 'ogg':
            params.update({
                'codec': 'libvorbis',
                'parameters': ['-q:a', '5']  # Качество Vorbis
            })
        elif format_name == 'wav':
            params.update({
                'parameters': ['-acodec', 'pcm_s16le']  # 16-bit PCM
            })
        
        return params
    
    def merge_and_convert(self, 
                         audio_files: List[str], 
                         output_path: str, 
                         target_format: str = 'wav') -> str:
        """
        Объединение файлов и конвертация в целевой формат
        
        Args:
            audio_files: Список путей к аудиофайлам
            output_path: Путь для сохранения результата
            target_format: Целевой формат
        
        Returns:
            Путь к финальному файлу
        """
        target_format = target_format.lower()
        
        # Если целевой формат WAV, объединяем напрямую
        if target_format == 'wav':
            return self.merge_wav_files(audio_files, output_path)
        
        # Для других форматов сначала объединяем в WAV, затем конвертируем
        temp_wav_path = os.path.join(
            self.temp_dir,
            f"temp_merged_{int(time.time())}.wav"
        )
        
        try:
            # Объединяем в WAV
            self.merge_wav_files(audio_files, temp_wav_path)
            
            # Конвертируем в целевой формат
            result_path = self.convert_format(temp_wav_path, output_path, target_format)
            
            return result_path
            
        finally:
            # Удаляем временный файл
            if os.path.exists(temp_wav_path):
                try:
                    os.unlink(temp_wav_path)
                    logger.debug(f"Удален временный файл: {temp_wav_path}")
                except OSError as e:
                    logger.warning(f"Не удалось удалить временный файл {temp_wav_path}: {e}")
    
    def get_audio_info(self, file_path: str) -> Dict[str, Any]:
        """
        Получение информации об аудиофайле
        
        Args:
            file_path: Путь к аудиофайлу
        
        Returns:
            Словарь с информацией
        """
        if not os.path.exists(file_path):
            raise AudioMergerError(f"Аудиофайл не найден: {file_path}")
        
        try:
            audio = AudioSegment.from_file(file_path)
            file_size = os.path.getsize(file_path)
            
            return {
                "file_path": file_path,
                "duration_seconds": len(audio) / 1000.0,
                "duration_formatted": format_duration(len(audio) / 1000.0),
                "sample_rate": audio.frame_rate,
                "channels": audio.channels,
                "sample_width": audio.sample_width,
                "file_size": file_size,
                "file_size_formatted": format_file_size(file_size),
                "format": Path(file_path).suffix.lower()
            }
            
        except Exception as e:
            raise AudioMergerError(f"Ошибка получения информации об аудиофайле: {e}")


# Глобальный экземпляр объединителя
_audio_merger: Optional[AudioMerger] = None


def get_audio_merger() -> AudioMerger:
    """
    Получение глобального экземпляра объединителя аудио
    
    Returns:
        Экземпляр AudioMerger
    """
    global _audio_merger
    if _audio_merger is None:
        _audio_merger = AudioMerger()
    return _audio_merger


def merge_audio_files(audio_files: List[str], 
                     output_path: str, 
                     target_format: str = 'wav') -> str:
    """
    Удобная функция для объединения аудиофайлов
    
    Args:
        audio_files: Список путей к аудиофайлам
        output_path: Путь для сохранения результата
        target_format: Целевой формат
    
    Returns:
        Путь к объединенному файлу
    """
    merger = get_audio_merger()
    return merger.merge_and_convert(audio_files, output_path, target_format)


def convert_audio_format(input_path: str, 
                        output_path: str, 
                        target_format: str) -> str:
    """
    Удобная функция для конвертации аудиофайла
    
    Args:
        input_path: Путь к исходному файлу
        output_path: Путь для сохранения результата
        target_format: Целевой формат
    
    Returns:
        Путь к сконвертированному файлу
    """
    merger = get_audio_merger()
    return merger.convert_format(input_path, output_path, target_format)


def get_audio_file_info(file_path: str) -> Dict[str, Any]:
    """
    Удобная функция для получения информации об аудиофайле
    
    Args:
        file_path: Путь к аудиофайлу
    
    Returns:
        Словарь с информацией
    """
    merger = get_audio_merger()
    return merger.get_audio_info(file_path)


def validate_audio_files(audio_files: List[str]) -> List[str]:
    """
    Валидация списка аудиофайлов
    
    Args:
        audio_files: Список путей к аудиофайлам
    
    Returns:
        Список валидных аудиофайлов
    """
    valid_files = []
    
    for audio_file in audio_files:
        if not audio_file:
            continue
        
        if not os.path.exists(audio_file):
            logger.warning(f"Аудиофайл не найден: {audio_file}")
            continue
        
        try:
            # Пробуем загрузить файл для проверки
            if AudioSegment:
                AudioSegment.from_file(audio_file)
            valid_files.append(audio_file)
            
        except Exception as e:
            logger.warning(f"Некорректный аудиофайл {audio_file}: {e}")
    
    return valid_files


def estimate_merged_duration(audio_files: List[str]) -> float:
    """
    Оценка длительности объединенного аудио
    
    Args:
        audio_files: Список путей к аудиофайлам
    
    Returns:
        Примерная длительность в секундах
    """
    total_duration = 0.0
    
    for audio_file in audio_files:
        if audio_file and os.path.exists(audio_file):
            try:
                if AudioSegment:
                    audio = AudioSegment.from_file(audio_file)
                    total_duration += len(audio) / 1000.0
            except Exception:
                # Если не удалось загрузить файл, пропускаем
                continue
    
    return total_duration


def cleanup_audio_files(audio_files: List[str]) -> int:
    """
    Очистка списка аудиофайлов
    
    Args:
        audio_files: Список путей к аудиофайлам для удаления
    
    Returns:
        Количество удаленных файлов
    """
    deleted_count = 0
    
    for audio_file in audio_files:
        if audio_file and os.path.exists(audio_file):
            try:
                os.unlink(audio_file)
                deleted_count += 1
                logger.debug(f"Удален аудиофайл: {audio_file}")
            except OSError as e:
                logger.warning(f"Не удалось удалить аудиофайл {audio_file}: {e}")
    
    return deleted_count
