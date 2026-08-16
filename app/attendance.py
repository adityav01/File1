from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


@dataclass(frozen=True)
class DailyAttendance:
    biometric_user_id: str
    work_date: date
    first_in: datetime | None
    last_out: datetime | None
    worked_hours: float
    ot_hours: float
    late: bool
    incomplete: bool
    punch_count: int


def parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def combine(day: date, clock: time) -> datetime:
    return datetime.combine(day, clock)


def pair_daily_attendance(
    punches: list[tuple[str, datetime, str]],
    *,
    shift_start: str = "09:00",
    shift_end: str = "18:00",
    grace_minutes: int = 15,
) -> list[DailyAttendance]:
    grouped: dict[tuple[str, date], list[tuple[datetime, str]]] = defaultdict(list)
    for user_id, punch_time, direction in punches:
        grouped[(user_id, punch_time.date())].append((punch_time, direction.upper()))

    start_clock = parse_hhmm(shift_start)
    end_clock = parse_hhmm(shift_end)
    shift_hours = (
        datetime.combine(date.today(), end_clock) - datetime.combine(date.today(), start_clock)
    ).total_seconds() / 3600
    grace = timedelta(minutes=grace_minutes)

    results: list[DailyAttendance] = []
    for (user_id, work_date), events in sorted(grouped.items()):
        events.sort(key=lambda item: item[0])
        ins = [event[0] for event in events if event[1] == "IN"]
        outs = [event[0] for event in events if event[1] == "OUT"]

        if ins or outs:
            first_in = min(ins) if ins else events[0][0]
            last_out = max(outs) if outs else (events[-1][0] if len(events) > 1 else None)
        else:
            first_in = events[0][0]
            last_out = events[-1][0] if len(events) > 1 else None

        incomplete = last_out is None or first_in is None
        worked_hours = 0.0
        if first_in and last_out and last_out > first_in:
            worked_hours = round((last_out - first_in).total_seconds() / 3600, 2)

        ot_hours = round(max(0.0, worked_hours - shift_hours), 2) if worked_hours else 0.0
        late = bool(first_in and first_in > combine(work_date, start_clock) + grace)
        results.append(
            DailyAttendance(
                biometric_user_id=user_id,
                work_date=work_date,
                first_in=first_in,
                last_out=last_out,
                worked_hours=worked_hours,
                ot_hours=ot_hours,
                late=late,
                incomplete=incomplete,
                punch_count=len(events),
            )
        )
    return results


def weekday_count(start: date, end: date) -> int:
    days = 0
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5:
            days += 1
        cursor += timedelta(days=1)
    return days
