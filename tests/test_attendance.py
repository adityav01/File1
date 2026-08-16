from datetime import datetime

from app.attendance import pair_daily_attendance


def test_pairs_first_in_last_out():
    punches = [
        ("1001", datetime(2026, 8, 3, 9, 5), "IN"),
        ("1001", datetime(2026, 8, 3, 13, 0), "OUT"),
        ("1001", datetime(2026, 8, 3, 13, 45), "IN"),
        ("1001", datetime(2026, 8, 3, 18, 20), "OUT"),
    ]
    days = pair_daily_attendance(punches)
    assert len(days) == 1
    assert days[0].first_in.hour == 9
    assert days[0].last_out.hour == 18
    assert days[0].worked_hours == 9.25
    assert days[0].incomplete is False


def test_single_punch_is_incomplete():
    punches = [("1001", datetime(2026, 8, 3, 9, 1), "IN")]
    days = pair_daily_attendance(punches)
    assert days[0].incomplete is True
    assert days[0].worked_hours == 0.0


def test_unknown_direction_uses_first_and_last():
    punches = [
        ("1001", datetime(2026, 8, 3, 9, 0), "UNKNOWN"),
        ("1001", datetime(2026, 8, 3, 18, 0), "UNKNOWN"),
    ]
    days = pair_daily_attendance(punches)
    assert days[0].worked_hours == 9.0
    assert days[0].incomplete is False


def test_late_after_grace():
    punches = [
        ("1001", datetime(2026, 8, 3, 9, 20), "IN"),
        ("1001", datetime(2026, 8, 3, 18, 0), "OUT"),
    ]
    days = pair_daily_attendance(punches, grace_minutes=15)
    assert days[0].late is True
