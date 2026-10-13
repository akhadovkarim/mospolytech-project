import logging
import os
import time

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger("passgen.db")


def get_dsn() -> str:
    return (
        f"host={os.getenv('POSTGRES_HOST', 'db')} "
        f"port={os.getenv('POSTGRES_PORT', '5432')} "
        f"dbname={os.getenv('POSTGRES_DB', 'passgen')} "
        f"user={os.getenv('POSTGRES_USER', 'passgen')} "
        f"password={os.getenv('POSTGRES_PASSWORD', '')}"
    )


def connect() -> psycopg.Connection:
    return psycopg.connect(get_dsn(), row_factory=dict_row, connect_timeout=5)


def wait_for_db(retries: int = 30, delay: float = 2.0) -> None:
    """Ждём, пока PostgreSQL начнёт принимать соединения."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with connect() as conn:
                conn.execute("SELECT 1")
            logger.info("База данных доступна (попытка %d)", attempt)
            return
        except psycopg.Error as exc:
            last_error = exc
            logger.warning("БД недоступна (попытка %d/%d): %s", attempt, retries, exc)
            time.sleep(delay)
    raise RuntimeError(f"Не удалось подключиться к базе данных: {last_error}")


def check_connection() -> bool:
    try:
        with connect() as conn:
            conn.execute("SELECT 1")
        return True
    except psycopg.Error:
        return False
