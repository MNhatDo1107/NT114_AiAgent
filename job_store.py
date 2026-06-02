"""
job_store.py

MySQL-backed persistent job store — thay thế dict in-memory trong api.py.
Dùng pymysql thuần, không ORM.

Đọc config từ .env (cùng pattern với project):
  DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

Schema (tự tạo nếu chưa có):
  ai_jobs(id, status, result JSON, error, created_at, updated_at)

Thread-safe: mỗi call tạo connection riêng (connection-per-call pattern).
PyMySQL không share connection giữa threads an toàn.
"""

import json
import time
import os
from typing import Optional, Any

import pymysql
import pymysql.cursors
from dotenv import load_dotenv

load_dotenv()

# ── Config từ .env ────────────────────────────────────────────────────────────

def _db_config() -> dict:
    return {
        "host":     os.getenv("DB_HOST", "localhost"),
        "port":     int(os.getenv("DB_PORT", "3306")),
        "database": os.getenv("DB_NAME", "nt114"),
        "user":     os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "charset":  "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": True,
    }


def _get_conn() -> pymysql.connections.Connection:
    return pymysql.connect(**_db_config())


# ── Init ──────────────────────────────────────────────────────────────────────

def init_db(retries: int = 10, delay: int = 3) -> None:
    """
    Tạo bảng ai_jobs nếu chưa có.
    Retry tối đa `retries` lần với `delay` giây — xử lý race condition
    khi MySQL container chưa sẵn sàng lúc ai-agent khởi động trong Docker.
    """
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            conn = _get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS ai_jobs (
                            id         VARCHAR(36)  PRIMARY KEY,
                            status     VARCHAR(20)  NOT NULL DEFAULT 'pending',
                            result     JSON,
                            error      TEXT,
                            created_at DOUBLE       NOT NULL,
                            updated_at DOUBLE       NOT NULL,
                            INDEX idx_updated_at (updated_at)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """)
                print(f"[job_store] MySQL connected (attempt {attempt})")
                return
            finally:
                conn.close()
        except pymysql.err.OperationalError as e:
            last_err = e
            print(f"[job_store] MySQL not ready (attempt {attempt}/{retries}), retry in {delay}s...")
            time.sleep(delay)

    raise RuntimeError(f"[job_store] Cannot connect to MySQL after {retries} attempts: {last_err}")


# ── CRUD ──────────────────────────────────────────────────────────────────────

def set_job(job_id: str, status: str,
            result: Optional[Any] = None,
            error: Optional[str] = None) -> None:
    """
    INSERT ... ON DUPLICATE KEY UPDATE — upsert an toàn.
    result: dict hoặc None, tự serialize sang JSON string cho MySQL.
    """
    now = time.time()
    result_json = json.dumps(result, ensure_ascii=False) if result is not None else None

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO ai_jobs (id, status, result, error, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    status     = VALUES(status),
                    result     = VALUES(result),
                    error      = VALUES(error),
                    updated_at = VALUES(updated_at)
            """, (job_id, status, result_json, error, now, now))
    finally:
        conn.close()


def get_job(job_id: str) -> Optional[dict]:
    """
    Trả về {"status", "result", "error"} hoặc None nếu không tồn tại.
    MySQL JSON column trả về string → parse lại thành dict.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, result, error FROM ai_jobs WHERE id = %s",
                (job_id,)
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    # MySQL JSON column đã được pymysql parse thành dict/list tự động
    # nhưng để an toàn, handle cả trường hợp còn là string
    result = row["result"]
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "status": row["status"],
        "result": result,
        "error":  row["error"],
    }


def job_exists(job_id: str) -> bool:
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM ai_jobs WHERE id = %s LIMIT 1", (job_id,)
            )
            return cur.fetchone() is not None
    finally:
        conn.close()


def cleanup_old_jobs(older_than_seconds: int = 86400) -> int:
    """
    Xóa job cũ hơn N giây. Mặc định 24h.
    Trả về số row đã xóa.
    """
    cutoff = time.time() - older_than_seconds
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM ai_jobs WHERE updated_at < %s", (cutoff,)
            )
            return cur.rowcount
    finally:
        conn.close()