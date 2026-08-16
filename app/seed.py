from __future__ import annotations

from datetime import date, datetime, timedelta

from app.db import get_db, get_settings, init_db


DEMO_EMPLOYEES = [
    ("RMP001", "Anita Sharma", "1001", "Operations", "Supervisor", 18000, 7200, 2800),
    ("RMP002", "Rahul Verma", "1002", "Operations", "Technician", 15000, 6000, 2000),
    ("RMP003", "Priya Nair", "1003", "Accounts", "Accountant", 22000, 8800, 3200),
    ("RMP004", "Imran Khan", "1004", "Operations", "Technician", 14000, 5600, 1800),
    ("RMP005", "Sneha Patel", "1005", "HR", "Executive", 20000, 8000, 2500),
]


def seed_demo_data(month: date | None = None) -> dict[str, int]:
    init_db()
    month = month or date.today().replace(day=1)
    start = month
    if start.month == 12:
        end = date(start.year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(start.year, start.month + 1, 1) - timedelta(days=1)

    inserted_employees = 0
    inserted_punches = 0
    with get_db() as conn:
        settings = get_settings(conn)
        serial = settings.get("device_serial") or "ESSL-RMP-01"
        for emp in DEMO_EMPLOYEES:
            existing = conn.execute(
                "SELECT id FROM employees WHERE emp_code = ?", (emp[0],)
            ).fetchone()
            if existing:
                continue
            conn.execute(
                """
                INSERT INTO employees(
                    emp_code, name, biometric_user_id, department, designation,
                    basic, hra, other_allowance, join_date, active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (*emp, start.isoformat()),
            )
            inserted_employees += 1

        cursor = start
        while cursor <= end:
            if cursor.weekday() < 5:
                for index, emp in enumerate(DEMO_EMPLOYEES):
                    in_minute = 2 + index * 3
                    out_minute = 5 + index * 2
                    in_time = datetime(cursor.year, cursor.month, cursor.day, 9, in_minute, 12)
                    out_time = datetime(cursor.year, cursor.month, cursor.day, 18, out_minute, 40)
                    for punch_time, direction in ((in_time, "IN"), (out_time, "OUT")):
                        try:
                            conn.execute(
                                """
                                INSERT INTO punches(
                                    biometric_user_id, punch_time, direction,
                                    device_serial, source, raw
                                ) VALUES (?, ?, ?, ?, 'demo', ?)
                                """,
                                (
                                    emp[2],
                                    punch_time.strftime("%Y-%m-%d %H:%M:%S"),
                                    direction,
                                    serial,
                                    f"{emp[2]} {punch_time} {direction}",
                                ),
                            )
                            inserted_punches += 1
                        except Exception:
                            pass
            cursor += timedelta(days=1)
    return {"employees": inserted_employees, "punches": inserted_punches}
