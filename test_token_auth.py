#!/usr/bin/env python3
"""
Тестовый скрипт для проверки автоматической переавторизации
"""
import asyncio
import sys
import os

# Добавляем путь к app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.garmin_service import GarminService
from app.models.garmin_models import GarminAuthRequest
from app.services.token_manager import TokenManager


async def test_token_autorization():
    """Тест автоматической переавторизации"""
    
    # Тестовые данные - передаются через аргументы командной строки или переменные окружения
    # Использование: python test_token_auth.py <user_id> <username> <password>
    # Или установите переменные окружения: GARMIN_TEST_USER_ID, GARMIN_TEST_USERNAME, GARMIN_TEST_PASSWORD
    
    import argparse
    parser = argparse.ArgumentParser(description='Тест авторизации Garmin')
    parser.add_argument('--user-id', type=int, help='ID пользователя')
    parser.add_argument('--username', type=str, help='Логин Garmin')
    parser.add_argument('--password', type=str, help='Пароль Garmin')
    args = parser.parse_args()
    
    TEST_USER_ID = args.user_id or int(os.environ.get('GARMIN_TEST_USER_ID', 0))
    TEST_USERNAME = args.username or os.environ.get('GARMIN_TEST_USERNAME', '')
    TEST_PASSWORD = args.password or os.environ.get('GARMIN_TEST_PASSWORD', '')
    
    if not TEST_USER_ID or not TEST_USERNAME or not TEST_PASSWORD:
        print("❌ Укажите данные для авторизации:")
        print("   python test_token_auth.py --user-id 1 --username user@email.com --password pass")
        print("   или установите переменные окружения GARMIN_TEST_USER_ID, GARMIN_TEST_USERNAME, GARMIN_TEST_PASSWORD")
        sys.exit(1)
    
    print("🚀 Начинаем тест автоматической переавторизации...")
    
    # Инициализация сервиса
    garmin_service = GarminService()
    
    try:
        # Шаг 1: Первичная авторизация и сохранение токенов
        print("\n📝 Шаг 1: Первичная авторизация...")
        auth_request = GarminAuthRequest(
            username=TEST_USERNAME,
            password=TEST_PASSWORD,
            user_id=TEST_USER_ID
        )
        
        auth_result = await garmin_service.authenticate(auth_request)
        
        if auth_result.success:
            print(f"✅ Успешная авторизация: {auth_result.message}")
            print(f"   Garmin User ID: {auth_result.garmin_user_id}")
            print(f"   Display Name: {auth_result.display_name}")
        else:
            print(f"❌ Ошибка авторизации: {auth_result.message}")
            return
        
        # Шаг 2: Проверка информации о токенах
        print("\n🔍 Шаг 2: Проверка информации о токенах...")
        token_info = await garmin_service.get_token_info(TEST_USER_ID)
        
        print("Информация о токенах:")
        for key, value in token_info.items():
            print(f"   {key}: {value}")
        
        # Шаг 3: Очистка сессии (симуляция перезагрузки)
        print("\n🧹 Шаг 3: Очистка сессии (симуляция перезагрузки)...")
        garmin_service.active_sessions.clear()
        garmin_service.session_cache.clear()
        print("✅ Сессия очищена")
        
        # Шаг 4: Попытка восстановления сессии из токенов
        print("\n🔄 Шаг 4: Восстановление сессии из токенов...")
        status = await garmin_service.get_connection_status(TEST_USER_ID)
        
        if status.connected:
            print(f"✅ Сессия успешно восстановлена из токенов!")
            print(f"   Garmin User ID: {status.garmin_user_id}")
            print(f"   Display Name: {status.display_name}")
            print(f"   Message: {status.message}")
        else:
            print(f"❌ Не удалось восстановить сессию: {status.message}")
            return
        
        # Шаг 5: Проверка получения активностей
        print("\n📊 Шаг 5: Проверка получения активностей...")
        try:
            activities = await garmin_service.get_activities(TEST_USER_ID)
            print(f"✅ Успешно получено {len(activities)} активностей")
            if activities:
                print(f"   Первая активность: {activities[0].activity_name}")
                print(f"   Тип: {activities[0].activity_type}")
        except Exception as e:
            print(f"❌ Ошибка получения активностей: {str(e)}")
        
        print("\n🎉 Тест автоматической переавторизации успешно завершен!")
        
    except Exception as e:
        print(f"❌ Ошибка в процессе теста: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Очистка
        print("\n🧹 Очистка тестовых данных...")
        await garmin_service.disconnect(TEST_USER_ID)
        
        # Удаление файлов токенов
        token_manager = TokenManager(TEST_USER_ID)
        token_manager.delete_tokens()
        print("✅ Тестовые данные очищены")


if __name__ == "__main__":
    asyncio.run(test_token_autorization())
