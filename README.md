# Garmin Service

Микросервис для интеграции с Garmin Connect API.

## Описание

Garmin Service - это отдельный микросервис, который отвечает за:
- Аутентификацию пользователей в Garmin Connect
- Получение активностей из Garmin
- Управление токенами доступа
- Автоматическое обновление сессий

## Технологии

- FastAPI (Python)
- garminconnect библиотека для работы с Garmin Connect API
- Docker для контейнеризации

## API Эндпоинты

### Аутентификация
- `POST /auth/authenticate` - Аутентификация в Garmin
- `GET /auth/status/{user_id}` - Получение статуса подключения
- `POST /auth/disconnect/{user_id}` - Отключение от Garmin
- `POST /auth/refresh/{user_id}` - Обновление сессии

### Активности
- `GET /activities/{user_id}` - Получение активностей
- `POST /activities/sync/{user_id}` - Синхронизация активностей
- `GET /activities/recent/{user_id}` - Последние активности
- `GET /activities/summary/{user_id}` - Сводная статистика

### Health
- `GET /health` - Проверка здоровья сервиса

## Переменные окружения

```bash
SERVICE_NAME=garmin-service
DEBUG=false
BACKEND_URL=http://localhost:3001
SECRET_KEY=your-secret-key-change-in-production
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
LOG_LEVEL=INFO
```

## Запуск

### С Docker

1. Соберите образ:
```bash
docker build -t garmin-service .
```

2. Запустите контейнер:
```bash
docker run -p 8002:8002 --env-file .env garmin-service
```

### С Docker Compose

Сервис уже добавлен в `docker-compose.yml` основного проекта:
```bash
cd ../backend-sport-portal
docker-compose up garmin-service
```

### Локально

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Запустите сервис:
```bash
cd app
uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

## Интеграция с основным бэкендом

Сервис автоматически взаимодействует с основным бэкендом для:
- Сохранения токенов в БД
- Отправки активностей на обработку
- Уведомления об отключениях

## Архитектура

```
Frontend (Vue) -> Backend (NestJS) -> Garmin Service (FastAPI) -> Garmin Connect API
                                   ↘                    ↗
                                 Database (PostgreSQL)
```

## Обработка ошибок

Сервис обрабатывает различные типы ошибок:
- Неверные учетные данные
- Требуется двухфакторная аутентификация
- Заблокированные аккаунты
- Проблемы с подключением к серверам Garmin
- Истекшие сессии

## Безопасность

- Пароли хранятся в зашифрованном виде в БД
- Сессии автоматически обновляются при истечении
- CORS настроен для доступа только с разрешенных доменов
