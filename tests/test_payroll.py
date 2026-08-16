from datetime import datetime

from app.attendance import DailyAttendance, pair_daily_attendance
from app.payroll import SalaryStructure, calculate_payroll_line


def test_full_month_present_pays_full_gross_minus_statutory():
    days = pair_daily_attendance(
        [
            ("1001", datetime(2026, 8, 3, 9, 0), "IN"),
            ("1001", datetime(2026, 8, 3, 18, 0), "OUT"),
        ]
    )
    # Pretend 1 working day month for a clean ratio.
    line = calculate_payroll_line(
        SalaryStructure(10000, 4000, 1000),
        days,
        working_days=1,
        ot_rate_per_hour=100,
    )
    assert line.present_days == 1
    assert line.earned_basic == 10000
    assert line.gross == 15000
    assert line.pf == 1200
    assert line.esi == 112.5
    assert line.net == 13687.5


def test_absent_day_reduces_earnings():
    line = calculate_payroll_line(
        SalaryStructure(26000, 0, 0),
        [],
        working_days=26,
        ot_rate_per_hour=0,
    )
    assert line.present_days == 0
    assert line.absent_days == 26
    assert line.net == 0


def test_overtime_and_incomplete_ignored():
    complete = DailyAttendance(
        biometric_user_id="1",
        work_date=datetime(2026, 8, 3).date(),
        first_in=datetime(2026, 8, 3, 9, 0),
        last_out=datetime(2026, 8, 3, 20, 0),
        worked_hours=11,
        ot_hours=2,
        late=False,
        incomplete=False,
        punch_count=2,
    )
    incomplete = DailyAttendance(
        biometric_user_id="1",
        work_date=datetime(2026, 8, 4).date(),
        first_in=datetime(2026, 8, 4, 9, 0),
        last_out=None,
        worked_hours=0,
        ot_hours=0,
        late=False,
        incomplete=True,
        punch_count=1,
    )
    line = calculate_payroll_line(
        SalaryStructure(2600, 0, 0),
        [complete, incomplete],
        working_days=2,
        ot_rate_per_hour=50,
    )
    assert line.present_days == 1
    assert line.ot_hours == 2
    assert line.ot_pay == 100
    assert line.earned_basic == 1300
