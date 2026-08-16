from __future__ import annotations

from dataclasses import dataclass

from app.attendance import DailyAttendance


@dataclass(frozen=True)
class SalaryStructure:
    basic: float
    hra: float
    other_allowance: float


@dataclass(frozen=True)
class PayrollLine:
    present_days: float
    absent_days: float
    ot_hours: float
    late_count: int
    earned_basic: float
    earned_hra: float
    earned_other: float
    ot_pay: float
    gross: float
    pf: float
    esi: float
    other_deduction: float
    net: float


def round_money(value: float) -> float:
    return round(value + 1e-9, 2)


def calculate_payroll_line(
    structure: SalaryStructure,
    days: list[DailyAttendance],
    *,
    working_days: int,
    ot_rate_per_hour: float,
    late_penalty: float = 0.0,
) -> PayrollLine:
    if working_days <= 0:
        raise ValueError("working_days must be positive")

    complete_days = [day for day in days if not day.incomplete and day.worked_hours > 0]
    present_days = float(len(complete_days))
    absent_days = max(0.0, working_days - present_days)
    ot_hours = round(sum(day.ot_hours for day in complete_days), 2)
    late_count = sum(1 for day in complete_days if day.late)

    ratio = present_days / working_days
    earned_basic = round_money(structure.basic * ratio)
    earned_hra = round_money(structure.hra * ratio)
    earned_other = round_money(structure.other_allowance * ratio)
    ot_pay = round_money(ot_hours * ot_rate_per_hour)
    gross = round_money(earned_basic + earned_hra + earned_other + ot_pay)

    pf_base = min(earned_basic, 15000.0)
    pf = round_money(pf_base * 0.12)
    esi = round_money(gross * 0.0075) if gross <= 21000 else 0.0
    other_deduction = round_money(late_count * late_penalty)
    net = round_money(gross - pf - esi - other_deduction)
    return PayrollLine(
        present_days=present_days,
        absent_days=absent_days,
        ot_hours=ot_hours,
        late_count=late_count,
        earned_basic=earned_basic,
        earned_hra=earned_hra,
        earned_other=earned_other,
        ot_pay=ot_pay,
        gross=gross,
        pf=pf,
        esi=esi,
        other_deduction=other_deduction,
        net=net,
    )
