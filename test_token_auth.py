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
    
    # Тестовые данные (замените на реальные)
    TEST_USER_ID = 1
    TEST_USERNAME = "leonid.warygin@gmail.com"
    TEST_PASSWORD = "OsNvTbi6MCPK"
    
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
