import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class TokenManager:
    """Менеджер для работы с DI OAuth токенами Garmin (garminconnect 0.3.x)"""

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.tokens_dir = Path("tokens")
        self.token_file = self.tokens_dir / f"user_{user_id}_garmin_tokens.json"

        # Создаем директорию для токенов, если ее нет
        self.tokens_dir.mkdir(exist_ok=True)

    def save_tokens(self, garmin_client) -> bool:
        """
        Сохранить DI OAuth токены в файл через встроенный метод клиента

        Args:
            garmin_client: Клиент GarminConnect с активной сессией

        Returns:
            bool: Успешность сохранения
        """
        try:
            # Используем встроенный метод dump() из garminconnect 0.3.x
            garmin_client.client.dump(str(self.token_file))
            logger.info(f"Saved DI OAuth tokens for user {self.user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save tokens for user {self.user_id}: {str(e)}")
            return False

    def load_tokens(self) -> Optional[Dict[str, Any]]:
        """
        Загрузить DI OAuth токены из файла

        Returns:
            Optional[Dict[str, Any]]: Данные токенов или None
        """
        try:
            if not self.token_file.exists():
                return None

            with open(self.token_file, 'r') as f:
                tokens = json.load(f)

            logger.info(f"Loaded DI OAuth tokens for user {self.user_id}")
            return tokens

        except Exception as e:
            logger.error(f"Failed to load tokens for user {self.user_id}: {str(e)}")
            return None

    def are_tokens_valid(self) -> bool:
        """
        Проверить наличие валидных токенов

        Returns:
            bool: Токены существуют и содержат обязательные поля
        """
        try:
            tokens = self.load_tokens()

            if not tokens:
                return False

            # Проверяем наличие обязательных полей нового формата
            required_fields = ['di_token', 'di_refresh_token']
            for field in required_fields:
                if not tokens.get(field):
                    logger.warning(f"Missing required token field: {field}")
                    return False

            logger.info(f"Tokens are valid for user {self.user_id}")
            return True

        except Exception as e:
            logger.error(f"Error validating tokens for user {self.user_id}: {str(e)}")
            return False

    def restore_tokens_to_client(self, garmin_client) -> bool:
        """
        Восстановить токены в клиенте Garmin через встроенный метод

        Args:
            garmin_client: Клиент GarminConnect

        Returns:
            bool: Успешность восстановления
        """
        try:
            # Используем встроенный метод load() из garminconnect 0.3.x
            garmin_client.client.load(str(self.token_file))

            if not garmin_client.client.is_authenticated:
                logger.warning(f"Client not authenticated after loading tokens for user {self.user_id}")
                return False

            logger.info(f"Successfully restored tokens for user {self.user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore tokens for user {self.user_id}: {str(e)}")
            return False

    def delete_tokens(self) -> bool:
        """
        Удалить сохраненные токены

        Returns:
            bool: Успешность удаления
        """
        try:
            if self.token_file.exists():
                self.token_file.unlink()
                logger.info(f"Deleted token file for user {self.user_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to delete tokens for user {self.user_id}: {str(e)}")
            return False

    def get_token_info(self) -> Dict[str, Any]:
        """
        Получить информацию о токенах

        Returns:
            Dict[str, Any]: Информация о токенах
        """
        try:
            tokens = self.load_tokens()

            info: Dict[str, Any] = {
                "user_id": self.user_id,
                "token_file_exists": self.token_file.exists(),
                "token_file_path": str(self.token_file) if self.token_file.exists() else None,
                "tokens_valid": self.are_tokens_valid(),
            }

            if tokens:
                info["has_di_token"] = bool(tokens.get('di_token'))
                info["has_di_refresh_token"] = bool(tokens.get('di_refresh_token'))
                info["has_di_client_id"] = bool(tokens.get('di_client_id'))

            return info

        except Exception as e:
            logger.error(f"Failed to get token info for user {self.user_id}: {str(e)}")
            return {
                "user_id": self.user_id,
                "error": str(e),
                "tokens_valid": False
            }