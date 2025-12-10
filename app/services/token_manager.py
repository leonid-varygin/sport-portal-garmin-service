import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class TokenManager:
    """Менеджер для работы с OAuth токенами Garmin"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.tokens_dir = Path("tokens")
        self.oauth1_file = self.tokens_dir / f"user_{user_id}_oauth1_token.json"
        self.oauth2_file = self.tokens_dir / f"user_{user_id}_oauth2_token.json"
        
        # Создаем директорию для токенов, если ее нет
        self.tokens_dir.mkdir(exist_ok=True)
    
    def save_tokens(self, garmin_client) -> bool:
        """
        Сохранить OAuth токены в файлы
        
        Args:
            garmin_client: Клиент GarminConnect с активной сессией
            
        Returns:
            bool: Успешность сохранения
        """
        try:
            # Сохраняем OAuth1 токен
            if garmin_client.garth.oauth1_token:
                oauth1_data = {
                    "oauth_token": garmin_client.garth.oauth1_token.oauth_token,
                    "oauth_token_secret": garmin_client.garth.oauth1_token.oauth_token_secret,
                    "mfa_token": garmin_client.garth.oauth1_token.mfa_token,
                    "mfa_expiration_timestamp": garmin_client.garth.oauth1_token.mfa_expiration_timestamp,
                    "domain": garmin_client.garth.oauth1_token.domain
                }
                
                with open(self.oauth1_file, 'w') as f:
                    json.dump(oauth1_data, f, indent=2, default=str)
                
                logger.info(f"Saved OAuth1 token for user {self.user_id}")
            
            # Сохраняем OAuth2 токен
            if garmin_client.garth.oauth2_token:
                oauth2_data = {
                    "scope": garmin_client.garth.oauth2_token.scope,
                    "jti": garmin_client.garth.oauth2_token.jti,
                    "token_type": garmin_client.garth.oauth2_token.token_type,
                    "access_token": garmin_client.garth.oauth2_token.access_token,
                    "refresh_token": garmin_client.garth.oauth2_token.refresh_token,
                    "expires_in": garmin_client.garth.oauth2_token.expires_in,
                    "expires_at": garmin_client.garth.oauth2_token.expires_at,
                    "refresh_token_expires_in": garmin_client.garth.oauth2_token.refresh_token_expires_in,
                    "refresh_token_expires_at": garmin_client.garth.oauth2_token.refresh_token_expires_at
                }
                
                with open(self.oauth2_file, 'w') as f:
                    json.dump(oauth2_data, f, indent=2, default=str)
                
                logger.info(f"Saved OAuth2 token for user {self.user_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save tokens for user {self.user_id}: {str(e)}")
            return False
    
    def load_tokens(self) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Загрузить OAuth токены из файлов
        
        Returns:
            Tuple[Optional[Dict], Optional[Dict]]: (oauth1_token, oauth2_token)
        """
        try:
            oauth1_token = None
            oauth2_token = None
            
            # Загружаем OAuth1 токен
            if self.oauth1_file.exists():
                with open(self.oauth1_file, 'r') as f:
                    oauth1_token = json.load(f)
                logger.info(f"Loaded OAuth1 token for user {self.user_id}")
            
            # Загружаем OAuth2 токен
            if self.oauth2_file.exists():
                with open(self.oauth2_file, 'r') as f:
                    oauth2_token = json.load(f)
                logger.info(f"Loaded OAuth2 token for user {self.user_id}")
            
            return oauth1_token, oauth2_token
            
        except Exception as e:
            logger.error(f"Failed to load tokens for user {self.user_id}: {str(e)}")
            return None, None
    
    def are_tokens_valid(self) -> bool:
        """
        Проверить валидность токенов
        
        Returns:
            bool: Токены валидны и не истекли
        """
        try:
            oauth1_token, oauth2_token = self.load_tokens()
            
            if not oauth1_token or not oauth2_token:
                return False
            
            # Проверяем наличие обязательных полей
            required_oauth1_fields = ['oauth_token', 'oauth_token_secret', 'domain']
            required_oauth2_fields = ['access_token', 'refresh_token', 'expires_at']
            
            for field in required_oauth1_fields:
                if not oauth1_token.get(field):
                    return False
            
            for field in required_oauth2_fields:
                if not oauth2_token.get(field):
                    return False
            
            # Проверяем срок действия OAuth2 токена
            expires_at = oauth2_token.get('expires_at')
            if expires_at:
                # Если expires_at это строка, конвертируем в timestamp
                if isinstance(expires_at, str):
                    try:
                        expires_at = float(expires_at)
                    except ValueError:
                        # Пробуем распарсить как ISO дату
                        try:
                            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00')).timestamp()
                        except:
                            logger.error(f"Cannot parse expires_at: {expires_at}")
                            return False
                
                # Добавляем буфер в 5 минут до истечения срока
                current_time = datetime.now().timestamp()
                if current_time > (expires_at - 300):  # 5 минут буфера
                    logger.warning(f"OAuth2 token expired for user {self.user_id}")
                    return False
            
            logger.info(f"Tokens are valid for user {self.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error validating tokens for user {self.user_id}: {str(e)}")
            return False
    
    def restore_tokens_to_client(self, garmin_client) -> bool:
        """
        Восстановить токены в клиенте Garmin
        
        Args:
            garmin_client: Клиент GarminConnect
            
        Returns:
            bool: Успешность восстановления
        """
        try:
            oauth1_token, oauth2_token = self.load_tokens()
            
            if not oauth1_token or not oauth2_token:
                logger.warning(f"No tokens found to restore for user {self.user_id}")
                return False
            
            # Создаем объекты токенов и устанавливаем их в клиент
            from garth.auth_tokens import OAuth1Token, OAuth2Token
            
            # Восстанавливаем OAuth1 токен
            oauth1_obj = OAuth1Token(
                oauth_token=oauth1_token['oauth_token'],
                oauth_token_secret=oauth1_token['oauth_token_secret'],
                mfa_token=oauth1_token.get('mfa_token'),
                mfa_expiration_timestamp=oauth1_token.get('mfa_expiration_timestamp'),
                domain=oauth1_token['domain']
            )
            garmin_client.garth.oauth1_token = oauth1_obj
            
            # Восстанавливаем OAuth2 токен
            oauth2_obj = OAuth2Token(
                scope=oauth2_token['scope'],
                jti=oauth2_token['jti'],
                token_type=oauth2_token['token_type'],
                access_token=oauth2_token['access_token'],
                refresh_token=oauth2_token['refresh_token'],
                expires_in=oauth2_token['expires_in'],
                expires_at=oauth2_token['expires_at'],
                refresh_token_expires_in=oauth2_token['refresh_token_expires_in'],
                refresh_token_expires_at=oauth2_token['refresh_token_expires_at']
            )
            garmin_client.garth.oauth2_token = oauth2_obj
            
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
            deleted_files = []
            
            if self.oauth1_file.exists():
                self.oauth1_file.unlink()
                deleted_files.append("oauth1_token.json")
            
            if self.oauth2_file.exists():
                self.oauth2_file.unlink()
                deleted_files.append("oauth2_token.json")
            
            if deleted_files:
                logger.info(f"Deleted token files for user {self.user_id}: {', '.join(deleted_files)}")
            
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
            oauth1_token, oauth2_token = self.load_tokens()
            
            info = {
                "user_id": self.user_id,
                "oauth1_token_exists": oauth1_token is not None,
                "oauth2_token_exists": oauth2_token is not None,
                "tokens_valid": self.are_tokens_valid(),
                "oauth1_file_path": str(self.oauth1_file) if self.oauth1_file.exists() else None,
                "oauth2_file_path": str(self.oauth2_file) if self.oauth2_file.exists() else None
            }
            
            if oauth2_token and oauth2_token.get('expires_at'):
                expires_at = oauth2_token['expires_at']
                if isinstance(expires_at, str):
                    try:
                        expires_at = float(expires_at)
                    except ValueError:
                        expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00')).timestamp()
                
                current_time = datetime.now().timestamp()
                time_left = expires_at - current_time
                info["expires_in_seconds"] = max(0, time_left)
                info["expires_in_minutes"] = max(0, time_left / 60)
                info["expires_in_hours"] = max(0, time_left / 3600)
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get token info for user {self.user_id}: {str(e)}")
            return {
                "user_id": self.user_id,
                "error": str(e),
                "tokens_valid": False
            }
