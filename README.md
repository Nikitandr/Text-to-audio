# Text-to-Audio конвертер

[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://docker.com)
[![Yandex SpeechKit](https://img.shields.io/badge/Yandex-SpeechKit-red.svg)](https://cloud.yandex.com/services/speechkit)

Приложение для конвертации текстовых документов в аудиофайлы с использованием технологии синтеза речи Yandex SpeechKit API v3.

## 🎯 Возможности

- **Поддержка множества форматов**: txt, docx, pdf, md
- **Различные аудиоформаты**: WAV, MP3, OGG
- **Умная разбивка текста**: автоматическое деление на фрагменты больших текстов с сохранением смысла
- **Объединение аудиофайлов**: автоматическое объединение аудиофайлов после озвучивания большого текста по частям
- **Контейнеризация**: полная изоляция в Docker
- **Гибкая конфигурация**: настройка через переменные окружения
- **Подробное логирование**: структурированные логи и статистика

## 📋 Требования

### Системные требования
- Docker 20.10+
- Docker Compose 2.0+
- 2GB свободного места на диске
- Стабильное интернет-соединение

### Yandex Cloud
- Аккаунт в Yandex Cloud
- Сервисный аккаунт с ролью `ai.speechkit-tts.user`
- Авторизованный ключ

## ⚙️ Предварительная настройка

### Настройка Yandex Cloud

Перед использованием приложения необходимо настроить доступ к Yandex SpeechKit API:

#### 1. Создание аккаунта Yandex Cloud

1. Перейдите на [cloud.yandex.com](https://cloud.yandex.com/)
2. Нажмите **"Войти в консоль"** и авторизуйтесь
3. Создайте новый каталог или используйте существующий. Если зарегистрировались впервые, автоматически будет создан каталог *Default*

#### 2. Создание платежного аккаунта
1. В консоли [Yandex Cloud](https://console.yandex.cloud/folders/) на панели слева нажмите на кнопку **"Все сервисы"** и введите в поиске **"Yandex Cloud Billing"**
2. Привяжите карту для оплаты сервисов

#### 3. Создание сервисного аккаунта

1. В консоли [Yandex Cloud](https://console.yandex.cloud/folders/) на панели слева нажмите на кнопку **"Все сервисы"** и введите в поиске **"Identity and Access Management"**
2. Нажмите **"Создать сервисный аккаунт"**
3. Укажите имя (например, `text-to-audio-service`)
4. Добавьте роль **`ai.speechkit-tts.user`**
5. Нажмите **"Создать"**

#### 4. Создание авторизованного ключа

1. Откройте созданный сервисный аккаунт
2. Нажмите **"Создать новый ключ" -> "Создать авторизованный ключ"**
4. Выберите алгоритм **RSA-2048**
5. Нажмите **"Создать"**
6. **Сохраните файл JSON** - он понадобится для настройки приложения

## 🚀 Быстрый старт

### 1. Клонирование репозитория

```bash
git clone https://github.com/Nikitandr/Text-to-audio.git
cd Text-to-audio
```

### 2. Настройка production конфигурации

```bash
# Копируем пример production конфигурации
cp .env.prod.example .env.prod

# Редактируем production конфигурацию
nano .env.prod
```

### Переменные окружения

```bash
# ID ключа сервисного аккаунта
# Скопируйте из authorized_key.json
YANDEX_KEY_ID=your_key_id

# ID сервисного аккаунта
# Скопируйте из authorized_key.json
YANDEX_SERVICE_ACCOUNT_ID=your_service_account_id

# Алгоритм шифрования ключа
# Скопируйте из authorized_key.json
YANDEX_KEY_ALGORITHM=your_key_algorithm

# Публичный ключ
# Скопируйте из authorized_key.json
YANDEX_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----...

# Приватный ключ
# Скопируйте из authorized_key.json
YANDEX_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----...

# Голос для синтеза речи
# МОЖНО ИЗМЕНИТЬ: jane (женский), omazh (женский), zahar (мужской), ermil (мужской)
DEFAULT_VOICE=jane

# Роль/эмоциональная окраска
# МОЖНО ИЗМЕНИТЬ: good (доброжелательный), neutral (нейтральный), evil (злой)
DEFAULT_ROLE=good

# Формат аудио по умолчанию
# МОЖНО ИЗМЕНИТЬ: wav, mp3, ogg
DEFAULT_FORMAT=wav

# Максимальный размер текстового фрагмента (символы)
# SpeechKit ограничивает 5000 символами. Рекомендуется 4500 (с запасом)
MAX_CHUNK_SIZE=4500

# Количество повторных попыток при ошибках
# МОЖНО ИЗМЕНИТЬ: 3-10
MAX_RETRIES=5

# Задержка между повторными попытками (секунды)
# МОЖНО ИЗМЕНИТЬ: 1-5
RETRY_DELAY=2

# Максимальное количество запросов в секунду к API
# МОЖНО ИЗМЕНИТЬ: 20-40 (рекомендуется 30)
REQUESTS_PER_SECOND=30

# Уровень логирования
# МОЖНО ИЗМЕНИТЬ: DEBUG, INFO, WARNING (рекомендуется), ERROR
LOG_LEVEL=WARNING

# Формат логов
# МОЖНО ИЗМЕНИТЬ: plain, json (рекомендуется)
LOG_FORMAT=json

# Путь к папке с данными для Docker volume
# Нужно указать ваш существующий путь
DATA_PATH=/absolute/path/to/data
```

### 3. Подготовка данных

```bash
# Создаем папку для данных
mkdir -p data/input data/output

# Устанавливаем правильные права доступа
chmod 755 data data/input data/output

# Копируем файлы для обработки
cp your-document.txt data/input/
```

### 4. Запуск production версии

```bash
# Сборка образа в фоновом режиме
docker-compose -f docker-compose.prod.yml --build -d

# Конвертация файла
docker-compose -f docker-compose.prod.yml run --rm text-to-audio \
  -i //app/data/input/your-document.txt \
  -o //app/data/output/result.wav

```

## 📖 Параметры командной строки

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


### Примеры использования
```bash
# Конвертация PDF в MP3
docker-compose -f docker-compose.prod.yml run --rm text-to-audio \
  -i /app/data/input/book.pdf \
  -o /app/data/output/audiobook.mp3 \
  -f mp3

# Конвертация с отладочными логами
docker-compose -f docker-compose.prod.yml run --rm text-to-audio \
  -i /app/data/input/document.txt \
  -o /app/data/output/audio.wav \
  --log-level DEBUG

# Пакетная обработка нескольких файлов
for file in data/input/*.txt; do
  filename=$(basename "$file" .txt)
  docker-compose -f docker-compose.prod.yml run --rm text-to-audio \
    -i "/app/data/input/$filename.txt" \
    -o "/app/data/output/$filename.wav"
done
```


## 🏗️ Архитектура

Приложение состоит из следующих основных компонентов:

- **main.py** - CLI интерфейс и оркестрация процесса
- **auth.py** - аутентификация с Yandex Cloud (JWT токены)
- **file_handlers.py** - чтение различных форматов файлов
- **text_processor.py** - разбивка текста на фрагменты
- **synthesizer.py** - синтез речи через Yandex SpeechKit API
- **audio_merger.py** - объединение аудиофрагментов
- **utils.py** - вспомогательные функции


## 🔧 Локальная разработка

```bash
# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
source venv/Scripts/activate  # Windows

# Установка зависимостей
pip install -r requirements.txt

# Запуск приложения
python src/main.py --help
```

## 🎨 Оптимизация текста

Для получения наилучшего качества синтеза речи рекомендуется предварительно оптимизировать текст. Подробное руководство доступно в файле [doc/text_optimization_guide.md](doc/text_optimization_guide.md).

### Основные принципы:
- Замена символов разметки на словесные обозначения
- Расшифровка аббревиатур и сокращений
- Преобразование списков в связный текст
- Добавление естественных пауз

---

**Версия**: 1.0.0  
**Дата обновления**: 29.08.2025
