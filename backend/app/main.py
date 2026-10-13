import hashlib
import logging
import math
import secrets
import string
from contextlib import asynccontextmanager
from typing import Literal

import bcrypt
import psycopg
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from app.db import check_connection, connect, wait_for_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("passgen")

Algorithm = Literal["md5", "sha1", "sha256", "sha512", "bcrypt"]
ALGORITHMS = ("md5", "sha1", "sha256", "sha512", "bcrypt")

UPPER = string.ascii_uppercase
LOWER = string.ascii_lowercase
DIGITS = string.digits
SYMBOLS = "!@#$%^&*()-_=+[]{};:,.<>?"

MIN_LENGTH = 4
MAX_LENGTH = 128
MAX_TEXT_LENGTH = 10_000
BCRYPT_MAX_BYTES = 72


@asynccontextmanager
async def lifespan(_: FastAPI):
    wait_for_db()
    yield


app = FastAPI(
    title="Генератор паролей и хэшей",
    description="Лабораторная работа, вариант N20",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------- Модели запросов ----------

class PasswordRequest(BaseModel):
    length: int = 16
    upper: bool = True
    lower: bool = True
    digits: bool = True
    symbols: bool = False

    @field_validator("length")
    @classmethod
    def validate_length(cls, value: int) -> int:
        if not MIN_LENGTH <= value <= MAX_LENGTH:
            raise ValueError(f"Длина пароля должна быть от {MIN_LENGTH} до {MAX_LENGTH} символов")
        return value

    @model_validator(mode="after")
    def validate_charsets(self):
        if not (self.upper or self.lower or self.digits or self.symbols):
            raise ValueError("Выберите хотя бы один набор символов")
        return self


class HashRequest(BaseModel):
    text: str
    algorithm: Algorithm = "sha256"

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Текст не должен быть пустым")
        if len(value) > MAX_TEXT_LENGTH:
            raise ValueError(f"Текст слишком длинный (максимум {MAX_TEXT_LENGTH} символов)")
        return value


# ---------- Обработка ошибок ----------

ERROR_MESSAGES = {
    "missing": "обязательное поле",
    "int_parsing": "ожидается целое число",
    "int_type": "ожидается целое число",
    "int_from_float": "ожидается целое число",
    "bool_parsing": "ожидается true или false",
    "bool_type": "ожидается true или false",
    "string_type": "ожидается строка",
    "json_invalid": "некорректный JSON в теле запроса",
}


def describe_error(err: dict) -> str:
    msg = err.get("msg", "")
    err_type = err.get("type", "")
    if msg.startswith("Value error, "):
        return msg[len("Value error, "):]
    if err_type == "literal_error":
        return f"допустимые значения: {err.get('ctx', {}).get('expected', '')}"
    return ERROR_MESSAGES.get(err_type, msg)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    messages = []
    for err in exc.errors():
        loc = ".".join(p for p in err.get("loc", []) if isinstance(p, str) and p not in ("body", "query"))
        msg = describe_error(err)
        messages.append(f"{loc}: {msg}" if loc else msg)
    return JSONResponse(status_code=422, content={"detail": "; ".join(messages)})


@app.exception_handler(psycopg.Error)
async def db_error_handler(_: Request, exc: psycopg.Error):
    logger.error("Ошибка БД: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "База данных недоступна"})


# ---------- Логика ----------

def generate_password(length: int, upper: bool, lower: bool, digits: bool, symbols: bool) -> str:
    pools = [p for flag, p in ((upper, UPPER), (lower, LOWER), (digits, DIGITS), (symbols, SYMBOLS)) if flag]
    alphabet = "".join(pools)
    chars = [secrets.choice(pool) for pool in pools]
    chars += [secrets.choice(alphabet) for _ in range(length - len(chars))]
    for i in range(len(chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        chars[i], chars[j] = chars[j], chars[i]
    return "".join(chars)


def estimate_strength(length: int, upper: bool, lower: bool, digits: bool, symbols: bool) -> tuple[str, float]:
    alphabet_size = (len(UPPER) if upper else 0) + (len(LOWER) if lower else 0) \
        + (len(DIGITS) if digits else 0) + (len(SYMBOLS) if symbols else 0)
    entropy = round(length * math.log2(alphabet_size), 1)
    if entropy < 40:
        return "weak", entropy
    if entropy < 70:
        return "medium", entropy
    return "strong", entropy


def compute_hash(text: str, algorithm: str) -> str:
    data = text.encode("utf-8")
    if algorithm == "bcrypt":
        if len(data) > BCRYPT_MAX_BYTES:
            raise HTTPException(status_code=422, detail=f"Для bcrypt текст не может быть длиннее {BCRYPT_MAX_BYTES} байт")
        return bcrypt.hashpw(data, bcrypt.gensalt()).decode()
    return hashlib.new(algorithm, data).hexdigest()


# ---------- Эндпоинты ----------

@app.get("/api/health")
def health():
    if check_connection():
        return {"status": "ok", "database": "connected"}
    return JSONResponse(status_code=503, content={"status": "error", "database": "unavailable"})


@app.post("/api/passwords/generate", status_code=201)
def create_password(req: PasswordRequest):
    value = generate_password(req.length, req.upper, req.lower, req.digits, req.symbols)
    strength, entropy = estimate_strength(req.length, req.upper, req.lower, req.digits, req.symbols)
    with connect() as conn:
        row = conn.execute(
            """
            INSERT INTO passwords (value, length, has_upper, has_lower, has_digits, has_symbols, strength)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, value, length, has_upper, has_lower, has_digits, has_symbols, strength, created_at
            """,
            (value, req.length, req.upper, req.lower, req.digits, req.symbols, strength),
        ).fetchone()
    row["entropy_bits"] = entropy
    return row


@app.get("/api/passwords")
def list_passwords(limit: int = Query(20, ge=1, le=100)):
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, value, length, has_upper, has_lower, has_digits, has_symbols, strength, created_at
            FROM passwords
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    return {"items": rows, "count": len(rows)}


@app.post("/api/hashes", status_code=201)
def create_hash(req: HashRequest):
    hash_value = compute_hash(req.text, req.algorithm)
    with connect() as conn:
        row = conn.execute(
            """
            INSERT INTO hashes (source_text, algorithm, hash_value)
            VALUES (%s, %s, %s)
            RETURNING id, source_text, algorithm, hash_value, created_at
            """,
            (req.text, req.algorithm, hash_value),
        ).fetchone()
    return row


@app.get("/api/hashes")
def list_hashes(
    algorithm: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    if algorithm:
        algorithm = algorithm.lower()
        if algorithm not in ALGORITHMS:
            raise HTTPException(status_code=422, detail=f"Неизвестный алгоритм: {algorithm}. Доступны: {', '.join(ALGORITHMS)}")
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, source_text, algorithm, hash_value, created_at
            FROM hashes
            WHERE (%(algorithm)s::text IS NULL OR algorithm = %(algorithm)s)
            ORDER BY created_at DESC, id DESC
            LIMIT %(limit)s
            """,
            {"algorithm": algorithm, "limit": limit},
        ).fetchall()
    return {"items": rows, "count": len(rows), "algorithm": algorithm}


@app.get("/api/stats")
def stats():
    with connect() as conn:
        pw = conn.execute(
            "SELECT COUNT(*) AS total, COALESCE(ROUND(AVG(length), 1), 0) AS avg_length FROM passwords"
        ).fetchone()
        by_strength = conn.execute(
            "SELECT strength, COUNT(*) AS cnt FROM passwords GROUP BY strength"
        ).fetchall()
        hs = conn.execute("SELECT COUNT(*) AS total FROM hashes").fetchone()
        by_algorithm = conn.execute(
            "SELECT algorithm, COUNT(*) AS cnt FROM hashes GROUP BY algorithm"
        ).fetchall()

    strength_map = {"weak": 0, "medium": 0, "strong": 0}
    strength_map.update({r["strength"]: r["cnt"] for r in by_strength})
    algorithm_map = {a: 0 for a in ALGORITHMS}
    algorithm_map.update({r["algorithm"]: r["cnt"] for r in by_algorithm})

    return {
        "passwords": {
            "total": pw["total"],
            "avg_length": float(pw["avg_length"]),
            "by_strength": strength_map,
        },
        "hashes": {
            "total": hs["total"],
            "by_algorithm": algorithm_map,
        },
    }


@app.delete("/api/history")
def clear_history():
    with connect() as conn:
        pw_count = conn.execute("SELECT COUNT(*) AS c FROM passwords").fetchone()["c"]
        hs_count = conn.execute("SELECT COUNT(*) AS c FROM hashes").fetchone()["c"]
        conn.execute("TRUNCATE TABLE passwords, hashes RESTART IDENTITY")
    return {"deleted": {"passwords": pw_count, "hashes": hs_count}}
