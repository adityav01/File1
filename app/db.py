from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DEFAULT_DB = DATA_DIR / "rmp_payroll.db"


def db_path() -> Path:
    return Path(os.environ.get("RMP_DB_PATH", DEFAULT_DB))


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                biometric_user_id TEXT NOT NULL UNIQUE,
                department TEXT NOT NULL DEFAULT 'Operations',
                designation TEXT NOT NULL DEFAULT 'Staff',
                basic REAL NOT NULL DEFAULT 0,
                hra REAL NOT NULL DEFAULT 0,
                other_allowance REAL NOT NULL DEFAULT 0,
                join_date TEXT,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS punches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                biometric_user_id TEXT NOT NULL,
                punch_time TEXT NOT NULL,
                direction TEXT NOT NULL DEFAULT 'UNKNOWN',
                device_serial TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'manual',
                raw TEXT NOT NULL DEFAULT '',
                UNIQUE(biometric_user_id, punch_time, device_serial)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS payroll_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month TEXT NOT NULL,
                created_at TEXT NOT NULL,
                working_days INTEGER NOT NULL,
                notes TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS payroll_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                employee_id INTEGER NOT NULL,
                present_days REAL NOT NULL,
                absent_days REAL NOT NULL,
                ot_hours REAL NOT NULL,
                late_count INTEGER NOT NULL,
                earned_basic REAL NOT NULL,
                earned_hra REAL NOT NULL,
                earned_other REAL NOT NULL,
                ot_pay REAL NOT NULL,
                gross REAL NOT NULL,
                pf REAL NOT NULL,
                esi REAL NOT NULL,
                other_deduction REAL NOT NULL,
                net REAL NOT NULL,
                FOREIGN KEY(run_id) REFERENCES payroll_runs(id) ON DELETE CASCADE,
                FOREIGN KEY(employee_id) REFERENCES employees(id)
            );

            CREATE INDEX IF NOT EXISTS idx_punches_user_time
                ON punches(biometric_user_id, punch_time);
            """
        )
        defaults = {
            "company_name": "RMP",
            "soap_url": "http://192.168.1.10:8080/iclock/WebAPIService.asmx",
            "soap_username": "",
            "soap_password": "",
            "device_serial": "",
            "timezone": "Asia/Kolkata",
            "shift_start": "09:00",
            "shift_end": "18:00",
            "grace_minutes": "15",
            "ot_rate_per_hour": "100",
            "standard_working_days": "26",
        }
        for key, value in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
                (key, value),
            )


def get_settings(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {row["key"]: row["value"] for row in rows}


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
