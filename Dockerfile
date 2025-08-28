# Используем официальный образ Python 3.9 slim
FROM python:3.13-slim

# Устанавливаем метаданные
LABEL maintainer="Text-to-Audio Team"
LABEL description="Text-to-Audio конвертер с использованием Yandex SpeechKit"
LABEL version="1.0.0"

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    # Для работы с аудио
    ffmpeg \
    # Для работы с PDF
    poppler-utils \
    # Общие утилиты
    curl \
    wget \
    # Очистка кэша
    && rm -rf /var/lib/apt/lists/*

# Создаем пользователя для безопасности
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем исходный код приложения
COPY src/ ./src/

# Создаем необходимые директории
RUN mkdir -p /app/data/input /app/data/output /app/temp && \
    chown -R appuser:appuser /app

# Переключаемся на непривилегированного пользователя
USER appuser

# Устанавливаем переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV TEMP_DIR=/app/temp
ENV INPUT_DIR=/app/data/input
ENV OUTPUT_DIR=/app/data/output


# Проверка здоровья контейнера
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.path.append('/app'); from src.auth import test_authentication; exit(0 if test_authentication() else 1)" || exit 1

# Точка входа
ENTRYPOINT ["python", "src/main.py"]

# Команда по умолчанию (показать справку)
CMD ["--help"]
