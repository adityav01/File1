from __future__ import annotations

import sqlite3
from datetime import date, datetime

from app.attendance import pair_daily_attendance
from app.db import get_db, get_settings
from app.essl_client import PunchRecord
from app.payroll import SalaryStructure, calculate_payroll_line


def store_punches(records: list[PunchRecord], source: str) -> tuple[int, int]:
    inserted = 0
    skipped = 0
    with get_db() as conn:
        for record in records:
            try:
                conn.execute(
                    """
                    INSERT INTO punches(
                        biometric_user_id, punch_time, direction, device_serial, source, raw
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.biometric_user_id,
                        record.punch_time.strftime("%Y-%m-%d %H:%M:%S"),
                        record.direction,
                        record.device_serial,
                        source,
                        record.raw,
                    ),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                skipped += 1
    return inserted, skipped


def store_employees(rows: list[dict[str, str]]) -> tuple[int, int]:
    inserted = 0
    skipped = 0
    with get_db() as conn:
        for row in rows:
            try:
                conn.execute(
                    """
                    INSERT INTO employees(
                        emp_code, name, biometric_user_id, department, designation,
                        basic, hra, other_allowance, join_date, active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        row["emp_code"],
                        row["name"],
                        row["biometric_user_id"],
                        row["department"],
                        row["designation"],
                        float(row["basic"] or 0),
                        float(row["hra"] or 0),
                        float(row["other_allowance"] or 0),
                        date.today().isoformat(),
                    ),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                skipped += 1
    return inserted, skipped


def load_punches(from_date: date, to_date: date) -> list[tuple[str, datetime, str]]:
    start = datetime.combine(from_date, datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S")
    end = _end_exclusive(to_date)
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT biometric_user_id, punch_time, direction
            FROM punches
            WHERE punch_time >= ? AND punch_time <= ?
            ORDER BY punch_time
            """,
            (start, end),
        ).fetchall()
    return [
        (
            row["biometric_user_id"],
            datetime.strptime(row["punch_time"], "%Y-%m-%d %H:%M:%S"),
            row["direction"],
        )
        for row in rows
    ]


def _end_exclusive(to_date: date) -> str:
    dt = datetime.combine(to_date, datetime.max.time().replace(microsecond=0))
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end - __import__("datetime").timedelta(days=1)


def attendance_for_month(year: int, month: int):
    start, end = month_bounds(year, month)
    with get_db() as conn:
        settings = get_settings(conn)
    punches = load_punches(start, end)
    return pair_daily_attendance(
        punches,
        shift_start=settings.get("shift_start", "09:00"),
        shift_end=settings.get("shift_end", "18:00"),
        grace_minutes=int(settings.get("grace_minutes", "15")),
    )


def run_payroll(year: int, month: int, notes: str = "") -> int:
    start, end = month_bounds(year, month)
    days = attendance_for_month(year, month)
    by_user: dict[str, list] = {}
    for day in days:
        by_user.setdefault(day.biometric_user_id, []).append(day)

    with get_db() as conn:
        settings = get_settings(conn)
        working_days = int(settings.get("standard_working_days", "26"))
        ot_rate = float(settings.get("ot_rate_per_hour", "100"))
        employees = conn.execute("SELECT * FROM employees WHERE active = 1").fetchall()
        cursor = conn.execute(
            """
            INSERT INTO payroll_runs(month, created_at, working_days, notes)
            VALUES (?, ?, ?, ?)
            """,
            (
                f"{year:04d}-{month:02d}",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                working_days,
                notes or f"RMP payroll {start.isoformat()} to {end.isoformat()}",
            ),
        )
        run_id = cursor.lastrowid
        for employee in employees:
            line = calculate_payroll_line(
                SalaryStructure(employee["basic"], employee["hra"], employee["other_allowance"]),
                by_user.get(employee["biometric_user_id"], []),
                working_days=working_days,
                ot_rate_per_hour=ot_rate,
            )
            conn.execute(
                """
                INSERT INTO payroll_lines(
                    run_id, employee_id, present_days, absent_days, ot_hours, late_count,
                    earned_basic, earned_hra, earned_other, ot_pay, gross, pf, esi,
                    other_deduction, net
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    employee["id"],
                    line.present_days,
                    line.absent_days,
                    line.ot_hours,
                    line.late_count,
                    line.earned_basic,
                    line.earned_hra,
                    line.earned_other,
                    line.ot_pay,
                    line.gross,
                    line.pf,
                    line.esi,
                    line.other_deduction,
                    line.net,
                ),
            )
    return run_id
