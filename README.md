# Генератор паролей и хэшей

Лабораторная работа «Развёртывание веб-приложения в Docker Compose», вариант **N20**.

Веб-приложение генерирует криптостойкие пароли с оценкой стойкости и вычисляет хэши текста
(MD5, SHA-1, SHA-256, SHA-512, bcrypt). Все результаты сохраняются в PostgreSQL, историю
и статистику можно посмотреть прямо на странице.

## Стек

| Слой     | Технологии                                     |
|----------|------------------------------------------------|
| frontend | nginx 1.27 (alpine), HTML / CSS / JS без фреймворков |
| backend  | Python 3.12, FastAPI, uvicorn, psycopg 3, bcrypt |
| db       | PostgreSQL 16 (alpine)                         |
| запуск   | Docker Compose, 3 контейнера, общая сеть       |

## Архитектура

```
                 http://localhost:8080
                          │
                          ▼
              ┌───────────────────────┐
              │   frontend (nginx)    │
              │  статика  +  /api/ ──┐│
              └──────────────────────┼┘
                                     │ proxy_pass
                                     ▼
              ┌───────────────────────┐
              │   backend (FastAPI)   │  :8000
              │  secrets / hashlib /  │
              │        bcrypt         │
              └───────────┬───────────┘
                          │ psycopg
                          ▼
              ┌───────────────────────┐
              │   db (PostgreSQL 16)  │  :5432 (только внутри сети)
              │  passwords, hashes    │
              └───────────────────────┘
                   volume: pgdata
```

Наружу открыт только frontend (порт 8080). Backend дополнительно опубликован на 8000, чтобы
можно было посмотреть Swagger-документацию (`/docs`) и проверить API напрямую. База данных
доступна только внутри сети Compose.

## Структура проекта

```
mospolytech-project/
├── docker-compose.yml        описание трёх сервисов, сети, тома, healthcheck
├── .env.example              пример переменных окружения
├── .gitignore
├── README.md
├── db/
│   └── init.sql              схема таблиц + тестовые данные
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py           FastAPI-приложение, эндпоинты, валидация
│       └── db.py             подключение к PostgreSQL, ожидание готовности БД
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf            раздача статики, проксирование /api/ на backend
│   └── public/
│       ├── index.html
│       ├── style.css
│       └── app.js
└── docs/
    └── screenshots/          скриншоты работы приложения
```

## Запуск

```bash
git clone https://github.com/akhadovkarim/mospolytech-project.git
cd mospolytech-project
cp .env.example .env
docker compose up -d --build
```

После сборки открыть в браузере: **http://localhost:8080**

Swagger-документация backend: http://localhost:8000/docs

Проверить состояние контейнеров:

```bash
docker compose ps
docker compose logs -f backend
```

## База данных

Схема создаётся автоматически при первом запуске из `db/init.sql`
(скрипт монтируется в `/docker-entrypoint-initdb.d/`).

**passwords** — сгенерированные пароли

| Поле        | Тип         | Описание                         |
|-------------|-------------|----------------------------------|
| id          | serial      | первичный ключ                   |
| value       | varchar(128)| пароль                           |
| length      | integer     | длина (4–128)                    |
| has_upper   | boolean     | использованы A–Z                 |
| has_lower   | boolean     | использованы a–z                 |
| has_digits  | boolean     | использованы 0–9                 |
| has_symbols | boolean     | использованы спецсимволы         |
| strength    | varchar(10) | weak / medium / strong           |
| created_at  | timestamptz | время создания                   |

**hashes** — вычисленные хэши

| Поле        | Тип         | Описание                              |
|-------------|-------------|---------------------------------------|
| id          | serial      | первичный ключ                        |
| source_text | text        | исходный текст                        |
| algorithm   | varchar(10) | md5 / sha1 / sha256 / sha512 / bcrypt |
| hash_value  | text        | результат                             |
| created_at  | timestamptz | время создания                        |

Стойкость пароля оценивается по энтропии `length · log2(размер_алфавита)`:
меньше 40 бит — weak, 40–70 — medium, больше 70 — strong.

## API

Все эндпоинты доступны через frontend по префиксу `/api/` и напрямую на backend.

| Метод  | Путь                       | Описание                                                   |
|--------|----------------------------|------------------------------------------------------------|
| GET    | `/api/health`              | проверка работы backend и подключения к БД                 |
| POST   | `/api/passwords/generate`  | генерация пароля, тело `{length, upper, lower, digits, symbols}` |
| GET    | `/api/passwords`           | последние 20 паролей (параметр `limit`, до 100)            |
| POST   | `/api/hashes`              | вычисление хэша, тело `{text, algorithm}`                  |
| GET    | `/api/hashes?algorithm=`   | история хэшей, фильтр по алгоритму                         |
| GET    | `/api/stats`               | статистика: количество паролей и хэшей, распределения      |
| DELETE | `/api/history`             | очистка обеих таблиц                                       |

Примеры:

```bash
curl http://localhost:8080/api/health

curl -X POST http://localhost:8080/api/passwords/generate \
  -H 'Content-Type: application/json' \
  -d '{"length": 16, "upper": true, "lower": true, "digits": true, "symbols": true}'

curl -X POST http://localhost:8080/api/hashes \
  -H 'Content-Type: application/json' \
  -d '{"text": "hello", "algorithm": "sha256"}'

curl 'http://localhost:8080/api/hashes?algorithm=sha256'
curl http://localhost:8080/api/stats
curl -X DELETE http://localhost:8080/api/history
```

Валидация: длина пароля от 4 до 128, хотя бы один набор символов, непустой текст для хэша,
для bcrypt текст не длиннее 72 байт. При ошибке возвращается код 422 и понятное сообщение
в поле `detail`.

## Остановка

```bash
docker compose down        # остановить и удалить контейнеры, данные в томе сохранятся
docker compose down -v     # остановить и удалить вместе с томом базы данных
```

## Скриншоты

Скриншоты работы приложения находятся в папке `docs/screenshots/`.
