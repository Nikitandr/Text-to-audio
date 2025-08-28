"""
Модуль аутентификации с Yandex Cloud SpeechKit
"""

import os
import json
import time
import jwt
import requests
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import structlog
from utils import safe_log

logger = structlog.get_logger(__name__)


class YandexAuthError(Exception):
    """Исключение для ошибок аутентификации"""
    pass


class TokenManager:
    """Менеджер для управления IAM токенами"""
    
    def __init__(self, key_path: Optional[str] = None):
        """
        Инициализация менеджера токенов
        """
        self.key_data: Optional[Dict[str, Any]] = None
        self.iam_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        
        # Загружаем ключ при инициализации
        self._load_key()
    
    def _load_key(self) -> None:
        """Загрузка авторизованного ключа из переменных окружения"""
        try:
            # Пытаемся загрузить из переменных окружения
            key_id = os.getenv('YANDEX_KEY_ID')
            service_account_id = os.getenv('YANDEX_SERVICE_ACCOUNT_ID')
            private_key = os.getenv('YANDEX_PRIVATE_KEY')
            public_key = os.getenv('YANDEX_PUBLIC_KEY')
            key_algorithm = os.getenv('YANDEX_KEY_ALGORITHM', 'RSA_2048')
            
            if not all([key_id, service_account_id, private_key]):
                raise YandexAuthError(
                    "Не найдены переменные окружения для авторизации Yandex Cloud. "
                    "Установите YANDEX_KEY_ID, YANDEX_SERVICE_ACCOUNT_ID, YANDEX_PRIVATE_KEY"
                )
            
            # Загружаем из переменных окружения
            self.key_data = {
                'id': key_id,
                'service_account_id': service_account_id,
                'private_key': private_key.replace('\\n', '\n'),  # Восстанавливаем переносы строк
                'public_key': public_key.replace('\\n', '\n') if public_key else None,
                'key_algorithm': key_algorithm
            }
            
            safe_log(
                logger, "info", "Авторизованный ключ загружен из переменных окружения",
                key_id=self.key_data['id'],
                service_account_id=self.key_data['service_account_id']
            )
            
            # Валидация ключа
            self._validate_key()
            
        except json.JSONDecodeError as e:
            raise YandexAuthError(f"Ошибка парсинга JSON ключа: {e}")
        except Exception as e:
            raise YandexAuthError(f"Ошибка загрузки ключа: {e}")
    
    def _validate_key(self) -> None:
        """Валидация структуры ключа"""
        if not self.key_data:
            raise YandexAuthError("Данные ключа не загружены")
        
        required_fields = ['id', 'service_account_id', 'private_key', 'key_algorithm']
        missing_fields = [field for field in required_fields if field not in self.key_data]
        
        if missing_fields:
            raise YandexAuthError(f"Отсутствуют обязательные поля в ключе: {missing_fields}")
        
        if self.key_data['key_algorithm'] != 'RSA_2048':
            raise YandexAuthError(f"Неподдерживаемый алгоритм ключа: {self.key_data['key_algorithm']}")
    
    def _create_jwt_token(self) -> str:
        """
        Создание JWT токена для обмена на IAM токен
        
        Returns:
            JWT токен
        """
        if not self.key_data:
            raise YandexAuthError("Данные ключа не загружены")
        
        now = int(time.time())
        
        # Заголовок JWT
        headers = {
            'typ': 'JWT',
            'alg': 'PS256',
            'kid': self.key_data['id']
        }
        
        # Полезная нагрузка JWT
        payload = {
            'iss': self.key_data['service_account_id'],
            'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
            'iat': now,
            'exp': now + 3600  # Токен действует 1 час
        }
        
        try:
            # Создание JWT токена
            jwt_token = jwt.encode(
                payload,
                self.key_data['private_key'],
                algorithm='PS256',
                headers=headers
            )
            
            logger.debug("JWT токен успешно создан")
            return jwt_token
            
        except Exception as e:
            raise YandexAuthError(f"Ошибка создания JWT токена: {e}")
    
    def _exchange_jwt_for_iam(self, jwt_token: str) -> Dict[str, Any]:
        """
        Обмен JWT токена на IAM токен
        
        Args:
            jwt_token: JWT токен
        
        Returns:
            Ответ с IAM токеном
        """
        url = 'https://iam.api.cloud.yandex.net/iam/v1/tokens'
        headers = {'Content-Type': 'application/json'}
        data = {'jwt': jwt_token}
        
        try:
            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            logger.debug("IAM токен успешно получен")
            return result
            
        except requests.exceptions.RequestException as e:
            raise YandexAuthError(f"Ошибка запроса IAM токена: {e}")
        except json.JSONDecodeError as e:
            raise YandexAuthError(f"Ошибка парсинга ответа IAM API: {e}")
    
    def _is_token_expired(self) -> bool:
        """
        Проверка истечения срока действия токена
        
        Returns:
            True если токен истек или истекает в ближайшие 10 минут
        """
        if not self.token_expires_at:
            return True
        
        # Обновляем токен за 10 минут до истечения
        buffer_time = timedelta(minutes=10)
        return datetime.now() + buffer_time >= self.token_expires_at
    
    def get_iam_token(self, force_refresh: bool = False) -> str:
        """
        Получение действующего IAM токена
        
        Args:
            force_refresh: Принудительное обновление токена
        
        Returns:
            IAM токен
        """
        if not force_refresh and self.iam_token and not self._is_token_expired():
            return self.iam_token
        
        try:
            # Создаем JWT токен
            jwt_token = self._create_jwt_token()
            
            # Обмениваем на IAM токен
            iam_response = self._exchange_jwt_for_iam(jwt_token)
            
            # Сохраняем токен и время истечения
            self.iam_token = iam_response['iamToken']
            
            # Парсим время истечения из ответа
            expires_at_str = iam_response.get('expiresAt')
            if expires_at_str:
                try:
                    # Формат может быть: 2023-12-31T23:59:59Z или 2023-12-31T23:59:59.123456789Z
                    # Убираем Z и обрабатываем наносекунды
                    clean_time = expires_at_str.replace('Z', '')
                    
                    # Если есть наносекунды, обрезаем до микросекунд (6 знаков)
                    if '.' in clean_time:
                        time_part, fraction = clean_time.split('.')
                        # Обрезаем до 6 знаков (микросекунды)
                        fraction = fraction[:6].ljust(6, '0')
                        clean_time = f"{time_part}.{fraction}"
                    
                    self.token_expires_at = datetime.fromisoformat(clean_time)
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Не удалось распарсить время истечения токена: {e}")
                    # Если время не указано или некорректно, считаем что токен действует 12 часов
                    self.token_expires_at = datetime.now() + timedelta(hours=12)
            else:
                # Если время не указано, считаем что токен действует 12 часов
                self.token_expires_at = datetime.now() + timedelta(hours=12)
            
            safe_log(
                logger, "info", "IAM токен успешно получен",
                expires_at=self.token_expires_at.isoformat()
            )
            
            return self.iam_token
            
        except Exception as e:
            raise YandexAuthError(f"Ошибка получения IAM токена: {e}")
    
    def get_auth_headers(self) -> Dict[str, str]:
        """
        Получение заголовков для аутентификации
        
        Returns:
            Словарь с заголовками
        """
        token = self.get_iam_token()
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
    
    def refresh_token(self) -> str:
        """
        Принудительное обновление токена
        
        Returns:
            Новый IAM токен
        """
        return self.get_iam_token(force_refresh=True)


# Глобальный экземпляр менеджера токенов
_token_manager: Optional[TokenManager] = None


def get_token_manager() -> TokenManager:
    """
    Получение глобального экземпляра менеджера токенов
    
    Returns:
        Экземпляр TokenManager
    """
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenManager()
    return _token_manager


def get_iam_token() -> str:
    """
    Удобная функция для получения IAM токена
    
    Returns:
        IAM токен
    """
    return get_token_manager().get_iam_token()


def get_auth_headers() -> Dict[str, str]:
    """
    Удобная функция для получения заголовков аутентификации
    
    Returns:
        Словарь с заголовками
    """
    return get_token_manager().get_auth_headers()


def validate_key_file(key_path: str) -> bool:
    """
    Валидация файла с ключом без его загрузки
    
    Args:
        key_path: Путь к файлу с ключом
    
    Returns:
        True если ключ валиден
    """
    try:
        if not os.path.exists(key_path):
            return False
        
        with open(key_path, 'r', encoding='utf-8') as f:
            key_data = json.load(f)
        
        required_fields = ['id', 'service_account_id', 'private_key', 'key_algorithm']
        return all(field in key_data for field in required_fields)
        
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return False


def test_authentication() -> bool:
    """
    Тестирование аутентификации
    
    Returns:
        True если аутентификация прошла успешно
    """
    try:
        token_manager = get_token_manager()
        token = token_manager.get_iam_token()
        
        # Простая проверка формата токена
        if token and len(token) > 50:
            logger.info("Тест аутентификации прошел успешно")
            return True
        else:
            logger.error("Получен некорректный токен")
            return False
            
    except Exception as e:
        logger.error("Тест аутентификации не прошел", error=str(e))
        return False
