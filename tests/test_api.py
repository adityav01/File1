from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RMP_DB_PATH", str(tmp_path / "test.db"))
    from app.db import init_db
    from app.main import app

    init_db()
    return TestClient(app)


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_employee_and_csv_payroll_flow(client: TestClient):
    create = client.post(
        "/employees",
        data={
            "emp_code": "RMP001",
            "name": "Anita Sharma",
            "biometric_user_id": "1001",
            "department": "Operations",
            "designation": "Supervisor",
            "basic": "18000",
            "hra": "7200",
            "other_allowance": "2800",
        },
        follow_redirects=False,
    )
    assert create.status_code == 303

    csv_body = (
        "biometric_user_id,punch_time,direction\n"
        "1001,2026-08-03 09:00:00,IN\n"
        "1001,2026-08-03 18:30:00,OUT\n"
    )
    imported = client.post(
        "/punches/import",
        files={"file": ("punches.csv", csv_body, "text/csv")},
        follow_redirects=False,
    )
    assert imported.status_code == 303

    attendance = client.get("/attendance?year=2026&month=8")
    assert attendance.status_code == 200
    assert "Anita Sharma" in attendance.text
    assert "18:30" in attendance.text

    payroll = client.post(
        "/payroll/run",
        data={"month": "2026-08", "notes": "test"},
        follow_redirects=True,
    )
    assert payroll.status_code == 200
    assert "Anita Sharma" in payroll.text
    assert "PF" in payroll.text


def test_essl_push_endpoint(client: TestClient):
    response = client.post(
        "/api/essl/push",
        json={
            "SerialNumber": "ESSL-RMP-01",
            "PunchLog": {
                "Type": "IN",
                "UserId": "2002",
                "LogTime": "2026-08-03T09:01:00",
            },
        },
    )
    assert response.json()["inserted"] == 1
