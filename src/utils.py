"""
Модуль утилит для логирования и вспомогательных функций
"""

import os
import sys
import time
import logging
import structlog
from typing import Optional, Dict, Any
from pathlib import Path
from tqdm import tqdm
from colorama import init, Fore, Style

# Инициализация colorama для Windows
init(autoreset=True)


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> structlog.BoundLogger:
    """
    Настройка системы логирования
    
    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR)
        log_format: Формат логов (json, plain)
    
    Returns:
        Настроенный логгер
    """
    # Настройка уровня логирования
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Настройка structlog
    if log_format.lower() == "json":
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ]
    else:
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.dev.ConsoleRenderer(colors=True)
        ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Настройка стандартного логгера
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )
    
    return structlog.get_logger("text-to-audio")


def safe_log(logger: structlog.BoundLogger, level: str, message: str, **kwargs) -> None:
    """
    Безопасное логирование без секретных данных
    
    Args:
        logger: Логгер
        level: Уровень логирования
        message: Сообщение
        **kwargs: Дополнительные параметры
    """
    # Удаляем потенциально секретные данные
    safe_kwargs = {}
    sensitive_keys = ['private_key', 'token', 'password', 'secret', 'key']
    
    for key, value in kwargs.items():
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            safe_kwargs[key] = "***HIDDEN***"
        else:
            safe_kwargs[key] = value
    
    # Логируем
    log_method = getattr(logger, level.lower(), logger.info)
    log_method(message, **safe_kwargs)


class ProgressTracker:
    """Класс для отслеживания прогресса обработки"""
    
    def __init__(self, total: int, description: str = "Processing"):
        """
        Инициализация трекера прогресса
        
        Args:
            total: Общее количество элементов
            description: Описание процесса
        """
        self.total = total
        self.description = description
        self.current = 0
        self.start_time = time.time()
        self.pbar = tqdm(
            total=total,
            desc=description,
            unit="items",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"
        )
    
    def update(self, count: int = 1) -> None:
        """Обновление прогресса"""
        self.current += count
        self.pbar.update(count)
    
    def set_description(self, description: str) -> None:
        """Изменение описания"""
        self.pbar.set_description(description)
    
    def close(self) -> Dict[str, Any]:
        """
        Закрытие трекера и возврат статистики
        
        Returns:
            Словарь со статистикой
        """
        elapsed_time = time.time() - self.start_time
        self.pbar.close()
        
        return {
            "total_items": self.total,
            "processed_items": self.current,
            "elapsed_time": elapsed_time,
            "items_per_second": self.current / elapsed_time if elapsed_time > 0 else 0
        }


class StatisticsCollector:
    """Класс для сбора статистики обработки"""
    
    def __init__(self):
        """Инициализация коллектора статистики"""
        self.stats = {
            "start_time": time.time(),
            "end_time": None,
            "total_characters": 0,
            "total_chunks": 0,
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_audio_duration": 0.0,
            "errors": []
        }
    
    def add_text_stats(self, characters: int, chunks: int) -> None:
        """Добавление статистики по тексту"""
        self.stats["total_characters"] += characters
        self.stats["total_chunks"] += chunks
    
    def add_request_stats(self, success: bool, error: Optional[str] = None) -> None:
        """Добавление статистики по запросам"""
        self.stats["total_requests"] += 1
        if success:
            self.stats["successful_requests"] += 1
        else:
            self.stats["failed_requests"] += 1
            if error:
                self.stats["errors"].append(error)
    
    def add_audio_duration(self, duration: float) -> None:
        """Добавление длительности аудио"""
        self.stats["total_audio_duration"] += duration
    
    def finalize(self) -> Dict[str, Any]:
        """
        Финализация статистики
        
        Returns:
            Полная статистика обработки
        """
        self.stats["end_time"] = time.time()
        self.stats["total_time"] = self.stats["end_time"] - self.stats["start_time"]
        self.stats["success_rate"] = (
            self.stats["successful_requests"] / self.stats["total_requests"] 
            if self.stats["total_requests"] > 0 else 0
        )
        
        return self.stats.copy()


def ensure_directory(path: str) -> Path:
    """
    Создание директории если она не существует
    
    Args:
        path: Путь к директории
    
    Returns:
        Path объект
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def format_duration(seconds: float) -> str:
    """
    Форматирование длительности в читаемый вид
    
    Args:
        seconds: Длительность в секундах
    
    Returns:
        Отформатированная строка
    """
    if seconds < 60:
        return f"{seconds:.1f}с"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{int(minutes)}м {secs:.1f}с"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{int(hours)}ч {int(minutes)}м {secs:.1f}с"


def format_file_size(bytes_size: int) -> str:
    """
    Форматирование размера файла в читаемый вид
    
    Args:
        bytes_size: Размер в байтах
    
    Returns:
        Отформатированная строка
    """
    for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} ТБ"


def print_colored(message: str, color: str = "white") -> None:
    """
    Вывод цветного сообщения в консоль
    
    Args:
        message: Сообщение
        color: Цвет (red, green, yellow, blue, magenta, cyan, white)
    """
    color_map = {
        "red": Fore.RED,
        "green": Fore.GREEN,
        "yellow": Fore.YELLOW,
        "blue": Fore.BLUE,
        "magenta": Fore.MAGENTA,
        "cyan": Fore.CYAN,
        "white": Fore.WHITE
    }
    
    color_code = color_map.get(color.lower(), Fore.WHITE)
    print(f"{color_code}{message}{Style.RESET_ALL}")


def validate_file_path(file_path: str, must_exist: bool = True) -> bool:
    """
    Валидация пути к файлу
    
    Args:
        file_path: Путь к файлу
        must_exist: Должен ли файл существовать
    
    Returns:
        True если путь валиден
    """
    path = Path(file_path)
    
    if must_exist:
        return path.exists() and path.is_file()
    else:
        # Проверяем, что родительская директория существует или может быть создана
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            return True
        except (OSError, PermissionError):
            return False


def get_file_extension(file_path: str) -> str:
    """
    Получение расширения файла
    
    Args:
        file_path: Путь к файлу
    
    Returns:
        Расширение файла в нижнем регистре
    """
    return Path(file_path).suffix.lower()


def cleanup_temp_files(temp_dir: str, pattern: str = "*") -> int:
    """
    Очистка временных файлов
    
    Args:
        temp_dir: Директория с временными файлами
        pattern: Паттерн файлов для удаления
    
    Returns:
        Количество удаленных файлов
    """
    temp_path = Path(temp_dir)
    if not temp_path.exists():
        return 0
    
    deleted_count = 0
    try:
        for file_path in temp_path.glob(pattern):
            if file_path.is_file():
                file_path.unlink()
                deleted_count += 1
    except (OSError, PermissionError) as e:
        print_colored(f"Ошибка при очистке временных файлов: {e}", "yellow")
    
    return deleted_count
