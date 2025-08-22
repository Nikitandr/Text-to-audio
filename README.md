# Text-to-Audio конвертер

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://docker.com)
[![Yandex SpeechKit](https://img.shields.io/badge/Yandex-SpeechKit-red.svg)](https://cloud.yandex.com/services/speechkit)

Приложение для конвертации текстовых документов в аудиофайлы с использованием технологии синтеза речи Yandex SpeechKit API v3.

## 🎯 Возможности

- **Поддержка множества форматов**: txt, docx, pdf, md
- **Различные аудиоформаты**: WAV, MP3, OGG
- **Умная разбивка текста**: автоматическое деление на фрагменты с сохранением смысла
- **Высокое качество синтеза**: использование Yandex SpeechKit API v3 в unsafe режиме
- **Надежность**: retry логика, обработка ошибок, частичное восстановление
- **Безопасность**: Docker Secrets для хранения ключей
- **Контейнеризация**: полная изоляция в Docker
- **Мониторинг**: подробное логирование и статистика

## 📋 Требования

### Системные требования
- Docker 20.10+
- Docker Compose 2.0+
- 2GB свободного места на диске
- Стабильное интернет-соединение

### Yandex Cloud
- Аккаунт в Yandex Cloud
- Сервисный аккаунт с ролью `ai.speechkit-tts.user`
- Авторизованный ключ в формате JSON

## 🚀 Быстрый старт

### 1. Клонирование репозитория

```bash
git clone https://github.com/your-username/text-to-audio.git
cd text-to-audio
```

### 2. Настройка ключей

```bash
# Создаем папку для секретов
mkdir secrets

# Копируем ваш авторизованный ключ
cp /path/to/your/authorized_key.json secrets/

# Устанавливаем правильные права доступа
chmod 600 secrets/authorized_key.json
```

### 3. Подготовка файлов

```bash
# Создаем необходимые папки
mkdir -p input output

# Копируем файлы для обработки в папку input
cp your-document.txt input/
```

### 4. Запуск приложения

```bash
# Сборка и запуск
docker-compose up --build

# Использование
docker-compose exec text-to-audio python src/main.py \
  -i /app/input/your-document.txt \
  -o /app/output/result.wav
```

## 📖 Использование

### Базовые команды

```bash
# Конвертация txt в WAV
docker-compose exec text-to-audio python src/main.py \
  -i /app/input/document.txt \
  -o /app/output/audio.wav

# Конвертация PDF в MP3
docker-compose exec text-to-audio python src/main.py \
  -i /app/input/book.pdf \
  -o /app/output/audiobook.mp3 \
  -f mp3

# Конвертация Markdown в OGG
docker-compose exec text-to-audio python src/main.py \
  -i /app/input/readme.md \
  -o /app/output/readme_audio.ogg \
  -f ogg
```

### Параметры командной строки

| Параметр | Короткий | Описание | Обязательный |
|----------|----------|----------|--------------|
| `--input` | `-i` | Путь к входному файлу | ✅ |
| `--output` | `-o` | Путь к выходному файлу | ✅ |
| `--format` | `-f` | Формат аудио (wav/mp3/ogg) | ❌ (по умолчанию: wav) |
| `--temp-dir` | | Папка для временных файлов | ❌ |
| `--log-level` | | Уровень логирования | ❌ (по умолчанию: INFO) |
| `--help` | `-h` | Справочная информация | ❌ |

### Поддерживаемые форматы

#### Входные форматы
- **TXT** - обычные текстовые файлы
- **DOCX** - документы Microsoft Word
- **PDF** - документы в формате PDF
- **MD** - файлы разметки Markdown

#### Выходные форматы
- **WAV** - несжатый аудиоформат (по умолчанию)
- **MP3** - сжатый аудиоформат
- **OGG** - открытый аудиоформат

## ⚙️ Конфигурация

### Переменные окружения

Основные настройки можно изменить через переменные окружения:

```bash
# Настройки синтеза речи
DEFAULT_VOICE=jane          # Голос (jane, omazh, zahar, ermil)
DEFAULT_ROLE=good           # Роль (good, neutral, evil)
DEFAULT_FORMAT=wav          # Формат по умолчанию

# Настройки обработки
MAX_CHUNK_SIZE=4500         # Максимальный размер фрагмента
MAX_RETRIES=3               # Количество повторных попыток
RETRY_DELAY=1               # Задержка между попытками (сек)

# Настройки rate limiting
REQUESTS_PER_SECOND=35      # Запросов в секунду

# Настройки логирования
LOG_LEVEL=INFO              # Уровень логирования
LOG_FORMAT=plain            # Формат логов (plain/json)
```

### Настройка .env файла

```bash
# Копируем пример конфигурации
cp .env.example .env

# Редактируем под свои нужды
nano .env
```

## 🐳 Docker

### Development

```bash
# Запуск в development режиме
docker-compose up --build

# Просмотр логов
docker-compose logs -f text-to-audio

# Остановка
docker-compose down
```

### Production

```bash
# Создание внешнего секрета для production
docker secret create yandex_authorized_key secrets/authorized_key.json

# Запуск в production режиме
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Мониторинг с Redis Exporter
docker-compose --profile monitoring -f docker-compose.prod.yml up -d
```

### Полезные команды

```bash
# Просмотр статуса контейнеров
docker-compose ps

# Выполнение команд внутри контейнера
docker-compose exec text-to-audio bash

# Очистка volumes
docker-compose down -v

# Пересборка образов
docker-compose build --no-cache
```

## 🔧 Разработка

### Локальная разработка

```bash
# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

# Установка зависимостей
pip install -r requirements.txt

# Запуск приложения
python src/main.py --help
```

### Структура проекта

```
text-to-audio/
├── src/                           # Исходный код
│   ├── __init__.py
│   ├── main.py                    # CLI интерфейс
│   ├── auth.py                    # Аутентификация
│   ├── synthesizer.py             # Синтез речи
│   ├── text_processor.py          # Обработка текста
│   ├── file_handlers.py           # Чтение файлов
│   ├── audio_merger.py            # Объединение аудио
│   └── utils.py                   # Утилиты
├── secrets/                       # Секреты (не в Git)
├── input/                         # Входные файлы
├── output/                        # Выходные файлы
├── requirements.txt               # Python зависимости
├── Dockerfile                     # Docker конфигурация
├── docker-compose.yml             # Development
├── docker-compose.prod.yml        # Production
└── README.md                      # Документация
```

### Тестирование

```bash
# Тест аутентификации
docker-compose exec text-to-audio python -c "
from src.auth import test_authentication
print('Auth test:', test_authentication())
"

# Тест синтеза речи
docker-compose exec text-to-audio python -c "
from src.synthesizer import test_synthesis
print('Synthesis test:', test_synthesis())
"
```

## 📊 Мониторинг

### Логирование

Приложение поддерживает структурированное логирование:

```bash
# Просмотр логов в реальном времени
docker-compose logs -f text-to-audio

# Логи в JSON формате (production)
docker-compose -f docker-compose.prod.yml logs text-to-audio
```

### Метрики

В production режиме доступны метрики Redis:

```bash
# Запуск с мониторингом
docker-compose --profile monitoring -f docker-compose.prod.yml up -d

# Метрики доступны на http://localhost:9121/metrics
curl http://localhost:9121/metrics
```

## 🔒 Безопасность

### Управление ключами

- Ключи хранятся как Docker Secrets
- Никогда не коммитьте ключи в Git
- Используйте правильные права доступа (600)

### Рекомендации

```bash
# Проверка прав на ключ
ls -la secrets/authorized_key.json
# Должно быть: -rw------- 1 user user

# Ротация ключей
cp new_authorized_key.json secrets/authorized_key.json
docker-compose restart text-to-audio
```

## 🚨 Устранение неполадок

### Частые проблемы

#### 1. Ошибка аутентификации

```bash
# Проверьте наличие ключа
ls -la secrets/authorized_key.json

# Проверьте формат ключа
cat secrets/authorized_key.json | jq .

# Проверьте права доступа
chmod 600 secrets/authorized_key.json
```

#### 2. Ошибки синтеза речи

```bash
# Проверьте квоты в Yandex Cloud
# Проверьте интернет-соединение
# Увеличьте количество повторных попыток

export MAX_RETRIES=5
export RETRY_DELAY=2
```

#### 3. Проблемы с аудио

```bash
# Проверьте наличие ffmpeg в контейнере
docker-compose exec text-to-audio which ffmpeg

# Проверьте права на папку output
chmod 755 output/
```

#### 4. Проблемы с памятью

```bash
# Увеличьте лимиты в docker-compose.prod.yml
# Очистите временные файлы
docker-compose exec text-to-audio rm -rf /app/temp/*
```

### Логи и диагностика

```bash
# Подробные логи
docker-compose exec text-to-audio python src/main.py \
  -i /app/input/test.txt \
  -o /app/output/test.wav \
  --log-level DEBUG

# Проверка состояния Redis
docker-compose exec redis redis-cli ping

# Проверка дискового пространства
docker system df
```

## 📈 Производительность

### Оптимизация

- Используйте SSD для временных файлов
- Настройте правильные лимиты памяти
- Мониторьте использование API квот
- Используйте Redis для кэширования токенов

### Рекомендуемые настройки

```bash
# Для больших файлов
MAX_CHUNK_SIZE=4000
REQUESTS_PER_SECOND=30

# Для быстрой обработки
MAX_CHUNK_SIZE=4500
REQUESTS_PER_SECOND=35
```

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch (`git checkout -b feature/amazing-feature`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing-feature`)
5. Создайте Pull Request

## 📄 Лицензия

Этот проект распространяется под лицензией MIT. См. файл `LICENSE` для подробностей.

## 🙏 Благодарности

- [Yandex Cloud](https://cloud.yandex.com/) за SpeechKit API
- [pydub](https://github.com/jiaaro/pydub) за работу с аудио
- [click](https://click.palletsprojects.com/) за CLI интерфейс
- [structlog](https://www.structlog.org/) за структурированное логирование

## 📞 Поддержка

Если у вас есть вопросы или проблемы:

1. Проверьте [раздел устранения неполадок](#-устранение-неполадок)
2. Посмотрите [существующие issues](https://github.com/your-username/text-to-audio/issues)
3. Создайте [новый issue](https://github.com/your-username/text-to-audio/issues/new)

---

**Версия**: 1.0.0  
**Дата обновления**: 22.08.2025
