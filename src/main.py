"""
Главный модуль CLI приложения Text-to-Audio
"""

import os
import sys
import click
from typing import Optional
from pathlib import Path
import structlog

# Импорт модулей приложения
from utils import (
    setup_logging, print_colored, format_duration, format_file_size,
    validate_file_path, get_file_extension, cleanup_temp_files
)
from file_handlers import (
    extract_text_from_file, get_file_info, validate_input_file,
    FileHandlerError
)
from text_processor import (
    process_text, estimate_chunks_count, validate_text_for_processing,
    TextProcessorError
)
from synthesizer import (
    synthesize_text_chunks, estimate_synthesis_time,
    SynthesizerError
)
from audio_merger import (
    merge_audio_files, get_audio_file_info,
    AudioMergerError
)
from auth import test_authentication, YandexAuthError

# Настройка логгера
logger = structlog.get_logger(__name__)


class TextToAudioApp:
    """Основной класс приложения"""
    
    def __init__(self, log_level: str = "INFO", temp_dir: str = None):
        """
        Инициализация приложения
        
        Args:
            log_level: Уровень логирования
            temp_dir: Директория для временных файлов
        """
        # Настройка логирования
        self.logger = setup_logging(log_level, "plain")
        
        # Настройка директорий
        self.temp_dir = temp_dir or os.getenv('TEMP_DIR', '/tmp/text-to-audio')
        
        # Статистика
        self.stats = {
            "start_time": None,
            "end_time": None,
            "input_file": None,
            "output_file": None,
            "text_length": 0,
            "chunks_count": 0,
            "audio_duration": 0.0,
            "success": False
        }
    
    def run(self, input_file: str, output_file: str, audio_format: str = "wav") -> bool:
        """
        Основной метод выполнения конвертации
        
        Args:
            input_file: Путь к входному файлу
            output_file: Путь к выходному файлу
            audio_format: Формат аудио
        
        Returns:
            True если конвертация прошла успешно
        """
        import time
        self.stats["start_time"] = time.time()
        self.stats["input_file"] = input_file
        self.stats["output_file"] = output_file
        
        try:
            print_colored("🎤 Text-to-Audio конвертер", "cyan")
            print_colored("=" * 50, "cyan")
            
            # 1. Валидация входных параметров
            self._validate_inputs(input_file, output_file, audio_format)
            
            # 2. Тестирование аутентификации
            self._test_authentication()
            
            # 3. Чтение входного файла
            text = self._read_input_file(input_file)
            self.stats["text_length"] = len(text)
            
            # 4. Обработка текста
            chunks = self._process_text(text)
            self.stats["chunks_count"] = len(chunks)
            
            # 5. Синтез речи
            audio_files = self._synthesize_speech(chunks)
            
            # 6. Объединение аудио
            final_audio = self._merge_audio(audio_files, output_file, audio_format)
            
            # 7. Получение информации о результате
            audio_info = get_audio_file_info(final_audio)
            self.stats["audio_duration"] = audio_info["duration_seconds"]
            
            # 8. Очистка временных файлов
            self._cleanup_temp_files(audio_files)
            
            # 9. Вывод результатов
            self._print_success_summary(audio_info)
            
            self.stats["success"] = True
            return True
            
        except KeyboardInterrupt:
            print_colored("\n❌ Операция прервана пользователем", "yellow")
            return False
        except Exception as e:
            self.logger.error("Критическая ошибка", error=str(e))
            print_colored(f"❌ Ошибка: {e}", "red")
            return False
        finally:
            self.stats["end_time"] = time.time()
    
    def _validate_inputs(self, input_file: str, output_file: str, audio_format: str) -> None:
        """Валидация входных параметров"""
        print_colored("📋 Проверка входных параметров...", "blue")
        
        # Проверка входного файла
        if not validate_file_path(input_file, must_exist=True):
            raise ValueError(f"Входной файл не найден: {input_file}")
        
        if not validate_input_file(input_file):
            raise ValueError(f"Неподдерживаемый формат файла: {get_file_extension(input_file)}")
        
        # Проверка выходного файла
        if not validate_file_path(output_file, must_exist=False):
            raise ValueError(f"Невозможно создать выходной файл: {output_file}")
        
        # Проверка формата аудио
        supported_formats = ['wav', 'mp3', 'ogg']
        if audio_format.lower() not in supported_formats:
            raise ValueError(f"Неподдерживаемый формат аудио: {audio_format}")
        
        print_colored("✅ Входные параметры корректны", "green")
    
    def _test_authentication(self) -> None:
        """Тестирование аутентификации"""
        print_colored("🔐 Проверка аутентификации...", "blue")
        
        if not test_authentication():
            raise YandexAuthError("Ошибка аутентификации с Yandex Cloud")
        
        print_colored("✅ Аутентификация прошла успешно", "green")
    
    def _read_input_file(self, input_file: str) -> str:
        """Чтение входного файла"""
        print_colored("📖 Чтение входного файла...", "blue")
        
        try:
            # Получаем информацию о файле
            file_info = get_file_info(input_file)
            print_colored(
                f"   Файл: {file_info['name']} ({file_info['size_formatted']})",
                "white"
            )
            
            # Извлекаем текст
            text = extract_text_from_file(input_file)
            
            if not validate_text_for_processing(text):
                raise ValueError("Файл не содержит достаточно текста для обработки")
            
            print_colored(
                f"✅ Текст извлечен: {len(text)} символов",
                "green"
            )
            
            return text
            
        except FileHandlerError as e:
            raise ValueError(f"Ошибка чтения файла: {e}")
    
    def _process_text(self, text: str) -> list:
        """Обработка и разбивка текста"""
        print_colored("✂️  Обработка текста...", "blue")
        
        try:
            # Оценка количества фрагментов
            estimated_chunks = estimate_chunks_count(text)
            print_colored(
                f"   Ожидается ~{estimated_chunks} фрагментов",
                "white"
            )
            
            # Разбивка текста
            chunks = process_text(text)
            
            print_colored(
                f"✅ Текст разбит на {len(chunks)} фрагментов",
                "green"
            )
            
            return chunks
            
        except TextProcessorError as e:
            raise ValueError(f"Ошибка обработки текста: {e}")
    
    def _synthesize_speech(self, chunks: list) -> list:
        """Синтез речи"""
        print_colored("🎙️  Синтез речи...", "blue")
        
        try:
            # Оценка времени
            estimated_time = estimate_synthesis_time(chunks)
            print_colored(
                f"   Ожидаемое время: {format_duration(estimated_time)}",
                "white"
            )
            
            # Синтез
            audio_files = synthesize_text_chunks(chunks)
            
            print_colored(
                f"✅ Синтез завершен: {len(audio_files)} аудиофайлов",
                "green"
            )
            
            return audio_files
            
        except SynthesizerError as e:
            raise ValueError(f"Ошибка синтеза речи: {e}")
    
    def _merge_audio(self, audio_files: list, output_file: str, audio_format: str) -> str:
        """Объединение аудиофайлов"""
        print_colored("🔗 Объединение аудиофайлов...", "blue")
        
        try:
            final_audio = merge_audio_files(audio_files, output_file, audio_format)
            
            print_colored(
                f"✅ Аудио объединено: {output_file}",
                "green"
            )
            
            return final_audio
            
        except AudioMergerError as e:
            raise ValueError(f"Ошибка объединения аудио: {e}")
    
    def _cleanup_temp_files(self, audio_files: list) -> None:
        """Очистка временных файлов"""
        print_colored("🧹 Очистка временных файлов...", "blue")
        
        try:
            from audio_merger import cleanup_audio_files
            deleted_count = cleanup_audio_files(audio_files)
            
            print_colored(
                f"✅ Удалено {deleted_count} временных файлов",
                "green"
            )
            
        except Exception as e:
            self.logger.warning("Ошибка очистки временных файлов", error=str(e))
    
    def _print_success_summary(self, audio_info: dict) -> None:
        """Вывод итоговой информации"""
        print_colored("\n🎉 Конвертация завершена успешно!", "green")
        print_colored("=" * 50, "green")
        
        # Информация о результате
        print_colored("📊 Статистика:", "cyan")
        print_colored(f"   📄 Исходный текст: {self.stats['text_length']} символов", "white")
        print_colored(f"   ✂️  Фрагментов: {self.stats['chunks_count']}", "white")
        print_colored(f"   🎵 Длительность: {audio_info['duration_formatted']}", "white")
        print_colored(f"   💾 Размер файла: {audio_info['file_size_formatted']}", "white")
        
        # Время обработки
        if self.stats["start_time"] and self.stats["end_time"]:
            processing_time = self.stats["end_time"] - self.stats["start_time"]
            print_colored(f"   ⏱️  Время обработки: {format_duration(processing_time)}", "white")
        
        print_colored(f"\n🎧 Результат сохранен: {self.stats['output_file']}", "cyan")


@click.command()
@click.option(
    '--input', '-i',
    required=True,
    type=click.Path(exists=True),
    help='Путь к входному текстовому файлу (txt, docx, pdf, md)'
)
@click.option(
    '--output', '-o',
    required=True,
    type=click.Path(),
    help='Путь к выходному аудиофайлу'
)
@click.option(
    '--format', '-f',
    default='wav',
    type=click.Choice(['wav', 'mp3', 'ogg'], case_sensitive=False),
    help='Формат выходного аудиофайла (по умолчанию: wav)'
)
@click.option(
    '--temp-dir',
    type=click.Path(),
    help='Директория для временных файлов'
)
@click.option(
    '--log-level',
    default='INFO',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR'], case_sensitive=False),
    help='Уровень логирования (по умолчанию: INFO)'
)
@click.version_option(version='1.0.0', prog_name='Text-to-Audio')
def main(input: str, output: str, format: str, temp_dir: Optional[str], log_level: str):
    """
    Text-to-Audio конвертер с использованием Yandex SpeechKit
    
    Конвертирует текстовые документы в аудиофайлы.
    
    Примеры использования:
    
    \b
    # Базовое использование
    python main.py -i document.txt -o audio.wav
    
    \b
    # С указанием формата
    python main.py -i book.pdf -o audiobook.mp3 -f mp3
    
    \b
    # С дополнительными параметрами
    python main.py -i article.md -o result.ogg -f ogg --log-level DEBUG
    """
    try:
        # Создаем экземпляр приложения
        app = TextToAudioApp(log_level=log_level.upper(), temp_dir=temp_dir)
        
        # Запускаем конвертацию
        success = app.run(input, output, format.lower())
        
        # Завершаем с соответствующим кодом
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print_colored(f"❌ Критическая ошибка: {e}", "red")
        sys.exit(1)


if __name__ == '__main__':
    main()
