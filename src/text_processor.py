"""
Модуль для обработки и разбивки текста на фрагменты
"""

import re
import os
from typing import List, Dict, Any, Optional
import structlog

logger = structlog.get_logger(__name__)


class TextProcessorError(Exception):
    """Исключение для ошибок обработки текста"""
    pass


class TextChunk:
    """Класс для представления фрагмента текста"""
    
    def __init__(self, text: str, index: int, original_length: int = None):
        """
        Инициализация фрагмента текста
        
        Args:
            text: Текст фрагмента
            index: Индекс фрагмента
            original_length: Длина оригинального текста (для статистики)
        """
        self.text = text.strip()
        self.index = index
        self.length = len(self.text)
        self.original_length = original_length
        self.processed = False
        self.audio_file: Optional[str] = None
    
    def __str__(self) -> str:
        return f"TextChunk(index={self.index}, length={self.length})"
    
    def __repr__(self) -> str:
        return self.__str__()


class TextSplitter:
    """Класс для умной разбивки текста на фрагменты"""
    
    def __init__(self, max_chunk_size: int = None):
        """
        Инициализация разбивщика текста
        
        Args:
            max_chunk_size: Максимальный размер фрагмента в символах
        """
        self.max_chunk_size = max_chunk_size or int(os.getenv('MAX_CHUNK_SIZE', '4500'))
        
        # Паттерны для разбивки
        self.sentence_endings = re.compile(r'[.!?]+\s+')
        self.paragraph_breaks = re.compile(r'\n\s*\n')
        self.word_boundaries = re.compile(r'\s+')
    
    def split_text(self, text: str) -> List[TextChunk]:
        """
        Разбивка текста на фрагменты
        
        Args:
            text: Исходный текст
        
        Returns:
            Список фрагментов текста
        """
        if not text or not text.strip():
            raise TextProcessorError("Пустой текст для обработки")
        
        # Предварительная обработка текста
        processed_text = self._preprocess_text(text)
        
        logger.info(
            "Начинаем разбивку текста",
            original_length=len(text),
            processed_length=len(processed_text),
            max_chunk_size=self.max_chunk_size
        )
        
        # Если текст помещается в один фрагмент
        if len(processed_text) <= self.max_chunk_size:
            return [TextChunk(processed_text, 0, len(text))]
        
        # Разбиваем текст на фрагменты
        chunks = self._split_into_chunks(processed_text)
        
        # Создаем объекты TextChunk
        text_chunks = []
        for i, chunk_text in enumerate(chunks):
            if chunk_text.strip():  # Пропускаем пустые фрагменты
                text_chunks.append(TextChunk(chunk_text, i, len(text)))
        
        logger.info(
            "Разбивка текста завершена",
            total_chunks=len(text_chunks),
            average_chunk_size=sum(chunk.length for chunk in text_chunks) // len(text_chunks) if text_chunks else 0
        )
        
        return text_chunks
    
    def _preprocess_text(self, text: str) -> str:
        """
        Предварительная обработка текста
        
        Args:
            text: Исходный текст
        
        Returns:
            Обработанный текст
        """
        # Нормализация переносов строк
        text = re.sub(r'\r\n', '\n', text)
        text = re.sub(r'\r', '\n', text)
        
        # Удаление лишних пробелов
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Нормализация множественных переносов строк
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Удаление пробелов в начале и конце строк
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        return text.strip()
    
    def _split_into_chunks(self, text: str) -> List[str]:
        """
        Разбивка текста на фрагменты с учетом границ предложений и абзацев
        
        Args:
            text: Текст для разбивки
        
        Returns:
            Список фрагментов
        """
        chunks = []
        
        # Сначала пробуем разбить по абзацам
        paragraphs = self.paragraph_breaks.split(text)
        
        current_chunk = ""
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # Если абзац помещается в текущий фрагмент
            potential_chunk = current_chunk + ("\n\n" if current_chunk else "") + paragraph
            
            if len(potential_chunk) <= self.max_chunk_size:
                current_chunk = potential_chunk
            else:
                # Сохраняем текущий фрагмент, если он не пустой
                if current_chunk:
                    chunks.append(current_chunk)
                
                # Если абзац слишком длинный, разбиваем его по предложениям
                if len(paragraph) > self.max_chunk_size:
                    sentence_chunks = self._split_by_sentences(paragraph)
                    chunks.extend(sentence_chunks[:-1])  # Все кроме последнего
                    current_chunk = sentence_chunks[-1] if sentence_chunks else ""
                else:
                    current_chunk = paragraph
        
        # Добавляем последний фрагмент
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _split_by_sentences(self, text: str) -> List[str]:
        """
        Разбивка текста по предложениям
        
        Args:
            text: Текст для разбивки
        
        Returns:
            Список фрагментов
        """
        chunks = []
        
        # Разбиваем по предложениям
        sentences = self.sentence_endings.split(text)
        
        # Восстанавливаем знаки препинания
        sentence_parts = []
        endings = self.sentence_endings.findall(text)
        
        for i, sentence in enumerate(sentences[:-1]):
            if sentence.strip():
                sentence_parts.append(sentence + endings[i].rstrip())
        
        # Добавляем последнее предложение
        if sentences[-1].strip():
            sentence_parts.append(sentences[-1])
        
        current_chunk = ""
        
        for sentence in sentence_parts:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            potential_chunk = current_chunk + (" " if current_chunk else "") + sentence
            
            if len(potential_chunk) <= self.max_chunk_size:
                current_chunk = potential_chunk
            else:
                # Сохраняем текущий фрагмент
                if current_chunk:
                    chunks.append(current_chunk)
                
                # Если предложение слишком длинное, разбиваем принудительно
                if len(sentence) > self.max_chunk_size:
                    word_chunks = self._split_by_words(sentence)
                    chunks.extend(word_chunks[:-1])
                    current_chunk = word_chunks[-1] if word_chunks else ""
                else:
                    current_chunk = sentence
        
        # Добавляем последний фрагмент
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _split_by_words(self, text: str) -> List[str]:
        """
        Принудительная разбивка по словам (последний резерв)
        
        Args:
            text: Текст для разбивки
        
        Returns:
            Список фрагментов
        """
        chunks = []
        words = self.word_boundaries.split(text)
        
        current_chunk = ""
        
        for word in words:
            if not word.strip():
                continue
            
            potential_chunk = current_chunk + (" " if current_chunk else "") + word
            
            if len(potential_chunk) <= self.max_chunk_size:
                current_chunk = potential_chunk
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                
                # Если даже одно слово слишком длинное, обрезаем его
                if len(word) > self.max_chunk_size:
                    # Разбиваем слово на части
                    for i in range(0, len(word), self.max_chunk_size):
                        chunk_part = word[i:i + self.max_chunk_size]
                        chunks.append(chunk_part)
                    current_chunk = ""
                else:
                    current_chunk = word
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks


class TextProcessor:
    """Основной класс для обработки текста"""
    
    def __init__(self, max_chunk_size: int = None):
        """
        Инициализация процессора текста
        
        Args:
            max_chunk_size: Максимальный размер фрагмента
        """
        self.splitter = TextSplitter(max_chunk_size)
        self.stats = {
            "total_texts_processed": 0,
            "total_chunks_created": 0,
            "total_characters_processed": 0
        }
    
    def process_text(self, text: str) -> List[TextChunk]:
        """
        Обработка текста и разбивка на фрагменты
        
        Args:
            text: Исходный текст
        
        Returns:
            Список фрагментов текста
        """
        if not text or not text.strip():
            raise TextProcessorError("Пустой текст для обработки")
        
        try:
            # Разбиваем текст на фрагменты
            chunks = self.splitter.split_text(text)
            
            # Обновляем статистику
            self.stats["total_texts_processed"] += 1
            self.stats["total_chunks_created"] += len(chunks)
            self.stats["total_characters_processed"] += len(text)
            
            # Валидация фрагментов
            self._validate_chunks(chunks)
            
            logger.info(
                "Текст успешно обработан",
                chunks_count=len(chunks),
                total_characters=len(text),
                average_chunk_size=sum(chunk.length for chunk in chunks) // len(chunks)
            )
            
            return chunks
            
        except Exception as e:
            logger.error("Ошибка обработки текста", error=str(e))
            raise TextProcessorError(f"Ошибка обработки текста: {e}")
    
    def _validate_chunks(self, chunks: List[TextChunk]) -> None:
        """
        Валидация фрагментов текста
        
        Args:
            chunks: Список фрагментов для валидации
        """
        if not chunks:
            raise TextProcessorError("Не удалось создать фрагменты текста")
        
        for chunk in chunks:
            if chunk.length > self.splitter.max_chunk_size:
                logger.warning(
                    "Фрагмент превышает максимальный размер",
                    chunk_index=chunk.index,
                    chunk_length=chunk.length,
                    max_size=self.splitter.max_chunk_size
                )
            
            if chunk.length == 0:
                raise TextProcessorError(f"Пустой фрагмент с индексом {chunk.index}")
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Получение статистики обработки
        
        Returns:
            Словарь со статистикой
        """
        stats = self.stats.copy()
        
        if stats["total_chunks_created"] > 0:
            stats["average_chunks_per_text"] = (
                stats["total_chunks_created"] / stats["total_texts_processed"]
            )
            stats["average_characters_per_chunk"] = (
                stats["total_characters_processed"] / stats["total_chunks_created"]
            )
        else:
            stats["average_chunks_per_text"] = 0
            stats["average_characters_per_chunk"] = 0
        
        return stats
    
    def reset_stats(self) -> None:
        """Сброс статистики"""
        self.stats = {
            "total_texts_processed": 0,
            "total_chunks_created": 0,
            "total_characters_processed": 0
        }


# Глобальный экземпляр процессора
_text_processor: Optional[TextProcessor] = None


def get_text_processor() -> TextProcessor:
    """
    Получение глобального экземпляра процессора текста
    
    Returns:
        Экземпляр TextProcessor
    """
    global _text_processor
    if _text_processor is None:
        _text_processor = TextProcessor()
    return _text_processor


def process_text(text: str) -> List[TextChunk]:
    """
    Удобная функция для обработки текста
    
    Args:
        text: Исходный текст
    
    Returns:
        Список фрагментов текста
    """
    processor = get_text_processor()
    return processor.process_text(text)


def estimate_chunks_count(text: str, max_chunk_size: int = None) -> int:
    """
    Оценка количества фрагментов без фактической разбивки
    
    Args:
        text: Исходный текст
        max_chunk_size: Максимальный размер фрагмента
    
    Returns:
        Примерное количество фрагментов
    """
    if not text:
        return 0
    
    chunk_size = max_chunk_size or int(os.getenv('MAX_CHUNK_SIZE', '4500'))
    
    # Простая оценка
    estimated_count = (len(text) + chunk_size - 1) // chunk_size
    
    # Добавляем небольшой запас на разбивку по границам предложений
    return max(1, int(estimated_count * 1.2))


def validate_text_for_processing(text: str) -> bool:
    """
    Валидация текста перед обработкой
    
    Args:
        text: Текст для валидации
    
    Returns:
        True если текст можно обработать
    """
    if not text or not isinstance(text, str):
        return False
    
    # Проверяем, что есть хотя бы некоторое количество текста
    clean_text = text.strip()
    if len(clean_text) < 10:
        return False
    
    # Проверяем, что текст содержит буквы (не только цифры и символы)
    if not re.search(r'[а-яёa-z]', clean_text, re.IGNORECASE):
        return False
    
    return True


def clean_text_for_synthesis(text: str) -> str:
    """
    Очистка текста для синтеза речи
    
    Args:
        text: Исходный текст
    
    Returns:
        Очищенный текст
    """
    # Удаляем лишние пробелы
    text = re.sub(r'\s+', ' ', text)
    
    # Нормализуем знаки препинания
    text = re.sub(r'\.{2,}', '...', text)  # Многоточие
    text = re.sub(r'[!]{2,}', '!', text)   # Множественные восклицательные знаки
    text = re.sub(r'[?]{2,}', '?', text)   # Множественные вопросительные знаки
    
    # Удаляем специальные символы, которые могут мешать синтезу
    text = re.sub(r'[^\w\s\.,!?;:()\-—–""«»\']+', '', text, flags=re.UNICODE)
    
    return text.strip()
