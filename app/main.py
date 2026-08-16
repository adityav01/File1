from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import get_db, get_settings, init_db, set_setting
from app.essl_client import (
    EsslSoapClient,
    parse_employee_upload,
    parse_upload,
    punches_from_push_payload,
)
from app.seed import seed_demo_data
from app.services import (
    attendance_for_month,
    month_bounds,
    run_payroll,
    store_employees,
    store_punches,
)

ROOT = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="RMP Payroll", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=str(ROOT / "templates"))


def render(request: Request, name: str, **context):
    with get_db() as conn:
        settings = get_settings(conn)
    context.update(request=request, settings=settings, today=date.today())
    return templates.TemplateResponse(request, name, context)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    with get_db() as conn:
        employees = conn.execute("SELECT COUNT(*) AS c FROM employees WHERE active = 1").fetchone()["c"]
        punches = conn.execute("SELECT COUNT(*) AS c FROM punches").fetchone()["c"]
        last_punch = conn.execute(
            "SELECT punch_time FROM punches ORDER BY punch_time DESC LIMIT 1"
        ).fetchone()
        runs = conn.execute("SELECT COUNT(*) AS c FROM payroll_runs").fetchone()["c"]
        unmatched = conn.execute(
            """
            SELECT COUNT(DISTINCT biometric_user_id) AS c FROM punches
            WHERE biometric_user_id NOT IN (SELECT biometric_user_id FROM employees)
            """
        ).fetchone()["c"]
    return render(
        request,
        "dashboard.html",
        employee_count=employees,
        punch_count=punches,
        last_punch=last_punch["punch_time"] if last_punch else None,
        payroll_runs=runs,
        unmatched=unmatched,
    )


@app.get("/employees", response_class=HTMLResponse)
def employees_page(request: Request):
    with get_db() as conn:
        employees = conn.execute("SELECT * FROM employees ORDER BY emp_code").fetchall()
    return render(request, "employees.html", employees=employees)


@app.post("/employees")
def create_employee(
    emp_code: str = Form(...),
    name: str = Form(...),
    biometric_user_id: str = Form(...),
    department: str = Form("Operations"),
    designation: str = Form("Staff"),
    basic: float = Form(0),
    hra: float = Form(0),
    other_allowance: float = Form(0),
):
    with get_db() as conn:
        try:
            conn.execute(
                """
                INSERT INTO employees(
                    emp_code, name, biometric_user_id, department, designation,
                    basic, hra, other_allowance, join_date, active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    emp_code.strip(),
                    name.strip(),
                    biometric_user_id.strip(),
                    department.strip(),
                    designation.strip(),
                    basic,
                    hra,
                    other_allowance,
                    date.today().isoformat(),
                ),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not save employee: {exc}") from exc
    return RedirectResponse("/employees", status_code=303)


@app.get("/punches", response_class=HTMLResponse)
def punches_page(request: Request, year: int | None = None, month: int | None = None):
    today = date.today()
    year = year or today.year
    month = month or today.month
    start, end = month_bounds(year, month)
    with get_db() as conn:
        punches = conn.execute(
            """
            SELECT p.*, e.name, e.emp_code
            FROM punches p
            LEFT JOIN employees e ON e.biometric_user_id = p.biometric_user_id
            WHERE p.punch_time >= ? AND p.punch_time <= ?
            ORDER BY p.punch_time DESC
            LIMIT 2000
            """,
            (
                datetime.combine(start, datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S"),
                datetime.combine(end, datetime.max.time().replace(microsecond=0)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            ),
        ).fetchall()
    return render(request, "punches.html", punches=punches, year=year, month=month)


@app.post("/punches/sync")
def sync_essl(
    from_date: str = Form(...),
    to_date: str = Form(...),
):
    with get_db() as conn:
        settings = get_settings(conn)
    client = EsslSoapClient(settings["soap_url"])
    records = client.fetch_transactions(
        from_time=datetime.strptime(from_date, "%Y-%m-%d"),
        to_time=datetime.strptime(to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59),
        username=settings.get("soap_username", ""),
        password=settings.get("soap_password", ""),
        serial_number=settings.get("device_serial", ""),
    )
    inserted, skipped = store_punches(records, "essl_soap")
    return RedirectResponse(
        f"/import?kind=punches&parsed={len(records)}&inserted={inserted}&skipped={skipped}",
        status_code=303,
    )


PUNCH_SAMPLE = """biometric_user_id,punch_time,direction,device_serial
1001,2026-08-01 09:04:00,IN,ESSL-RMP-01
1001,2026-08-01 18:07:00,OUT,ESSL-RMP-01
1002,2026-08-01 09:08:00,IN,ESSL-RMP-01
1002,2026-08-01 18:11:00,OUT,ESSL-RMP-01
"""

EMPLOYEE_SAMPLE = """emp_code,name,biometric_user_id,department,designation,basic,hra,other_allowance
RMP001,Anita Sharma,1001,Operations,Supervisor,18000,7200,2800
RMP002,Rahul Verma,1002,Operations,Technician,15000,6000,2000
"""


@app.get("/import", response_class=HTMLResponse)
def import_page(
    request: Request,
    kind: str | None = None,
    parsed: int | None = None,
    inserted: int | None = None,
    skipped: int | None = None,
    error: str | None = None,
    preview: str | None = None,
):
    return render(
        request,
        "import.html",
        kind=kind,
        parsed=parsed,
        inserted=inserted,
        skipped=skipped,
        error=error,
        preview_rows=(preview.split("||") if preview else []),
    )


@app.get("/import/sample/punches.csv")
def punch_sample():
    return PlainTextResponse(PUNCH_SAMPLE, media_type="text/csv")


@app.get("/import/sample/employees.csv")
def employee_sample():
    return PlainTextResponse(EMPLOYEE_SAMPLE, media_type="text/csv")


def _preview(records) -> str:
    lines = []
    for record in records[:8]:
        lines.append(
            f"{record.biometric_user_id} · {record.punch_time.strftime('%Y-%m-%d %H:%M:%S')} · {record.direction}"
        )
    return "||".join(lines)


@app.post("/import/punches")
async def import_punches(file: UploadFile = File(...)):
    data = await file.read()
    filename = file.filename or "punches.csv"
    try:
        records = parse_upload(filename, data)
    except Exception as exc:
        return RedirectResponse(f"/import?error={quote(str(exc))}", status_code=303)
    if not records:
        return RedirectResponse(
            "/import?error=" + quote("No punch rows found. Use User ID, date/time, and IN/OUT columns."),
            status_code=303,
        )
    inserted, skipped = store_punches(records, "import")
    preview = _preview(records)
    return RedirectResponse(
        f"/import?kind=punches&parsed={len(records)}&inserted={inserted}&skipped={skipped}&preview={quote(preview)}",
        status_code=303,
    )


@app.post("/import/employees")
async def import_staff(file: UploadFile = File(...)):
    data = await file.read()
    filename = file.filename or "employees.csv"
    try:
        rows = parse_employee_upload(filename, data)
    except Exception as exc:
        return RedirectResponse(f"/import?error={quote(str(exc))}", status_code=303)
    if not rows:
        return RedirectResponse(
            "/import?error=" + quote("No employee rows found. Need emp_code, name, and biometric_user_id."),
            status_code=303,
        )
    inserted, skipped = store_employees(rows)
    return RedirectResponse(
        f"/import?kind=employees&parsed={len(rows)}&inserted={inserted}&skipped={skipped}",
        status_code=303,
    )


@app.post("/punches/import")
async def import_csv(file: UploadFile = File(...)):
    return await import_punches(file)


@app.post("/punches/demo")
def load_demo():
    seed_demo_data()
    return RedirectResponse("/", status_code=303)


@app.post("/api/essl/push")
def essl_push(payload: dict):
    records = list(punches_from_push_payload(payload))
    inserted, _skipped = store_punches(records, "essl_push")
    return {"inserted": inserted}


@app.get("/attendance", response_class=HTMLResponse)
def attendance_page(request: Request, year: int | None = None, month: int | None = None):
    today = date.today()
    year = year or today.year
    month = month or today.month
    days = attendance_for_month(year, month)
    with get_db() as conn:
        employees = {
            row["biometric_user_id"]: row
            for row in conn.execute("SELECT * FROM employees").fetchall()
        }
    rows = []
    for day in days:
        emp = employees.get(day.biometric_user_id)
        rows.append(
            {
                "emp_code": emp["emp_code"] if emp else "UNMAPPED",
                "name": emp["name"] if emp else day.biometric_user_id,
                "day": day,
            }
        )
    return render(request, "attendance.html", rows=rows, year=year, month=month)


@app.get("/payroll", response_class=HTMLResponse)
def payroll_page(request: Request):
    with get_db() as conn:
        runs = conn.execute("SELECT * FROM payroll_runs ORDER BY id DESC").fetchall()
    return render(request, "payroll.html", runs=runs, lines=None, selected=None)


@app.get("/payroll/{run_id}", response_class=HTMLResponse)
def payroll_detail(request: Request, run_id: int):
    with get_db() as conn:
        selected = conn.execute("SELECT * FROM payroll_runs WHERE id = ?", (run_id,)).fetchone()
        if not selected:
            raise HTTPException(status_code=404, detail="Payroll run not found")
        runs = conn.execute("SELECT * FROM payroll_runs ORDER BY id DESC").fetchall()
        lines = conn.execute(
            """
            SELECT l.*, e.emp_code, e.name, e.department
            FROM payroll_lines l
            JOIN employees e ON e.id = l.employee_id
            WHERE l.run_id = ?
            ORDER BY e.emp_code
            """,
            (run_id,),
        ).fetchall()
    return render(request, "payroll.html", runs=runs, lines=lines, selected=selected)


@app.post("/payroll/run")
def create_payroll_run(month: str = Form(...), notes: str = Form("")):
    year_s, month_s = month.split("-")
    run_id = run_payroll(int(year_s), int(month_s), notes)
    return RedirectResponse(f"/payroll/{run_id}", status_code=303)


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return render(request, "settings.html")


@app.post("/settings")
def save_settings(
    company_name: str = Form(...),
    soap_url: str = Form(...),
    soap_username: str = Form(""),
    soap_password: str = Form(""),
    device_serial: str = Form(""),
    shift_start: str = Form("09:00"),
    shift_end: str = Form("18:00"),
    grace_minutes: str = Form("15"),
    ot_rate_per_hour: str = Form("100"),
    standard_working_days: str = Form("26"),
):
    with get_db() as conn:
        current = get_settings(conn)
        values = {
            "company_name": company_name,
            "soap_url": soap_url,
            "soap_username": soap_username,
            "soap_password": soap_password or current.get("soap_password", ""),
            "device_serial": device_serial,
            "shift_start": shift_start,
            "shift_end": shift_end,
            "grace_minutes": grace_minutes,
            "ot_rate_per_hour": ot_rate_per_hour,
            "standard_working_days": standard_working_days,
        }
        for key, value in values.items():
            set_setting(conn, key, value)
    return RedirectResponse("/settings", status_code=303)


@app.get("/health")
def health():
    return {"ok": True, "days_in_month": monthrange(date.today().year, date.today().month)[1]}
