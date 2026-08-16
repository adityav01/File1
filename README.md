# RMP Payroll + eSSL biometric attendance

Collect **IN / OUT** punches from an eSSL biometric device (via eTimeTrackLite / eBioServer SOAP, CSV, or HTTP push), map them to RMP staff, and run monthly payroll.

## What it does

- Syncs punch logs with SOAP `GetTransactionsLog`
- Accepts CSV imports and JSON device push
- Pairs first IN / last OUT per person per day
- Calculates present/absent, overtime, PF, and ESI
- Stores data locally in SQLite (`data/rmp_payroll.db`)

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://127.0.0.1:8000/import**

1. Download a sample file or export CSV/Excel from eTimeTrackLite.
2. Import employees (User ID must match the device).
3. Import punches (IN/OUT).
4. Open Attendance, then run Payroll.

Typical SOAP URL:

`http://<etime-server>:<port>/iclock/WebAPIService.asmx`

Demo eSSL server (if reachable on your network): `http://etime.esslsecurity.com:3366/WebAPIService.asmx`

## CSV columns

`biometric_user_id,punch_time,direction`

Example:

```csv
biometric_user_id,punch_time,direction
1001,2026-08-01 09:04:00,IN
1001,2026-08-01 18:07:00,OUT
```

## Tests

```bash
pip install -r requirements.txt
pytest -q
```

API credentials stay in the local SQLite settings table. Leave the password field blank when saving settings to keep the existing value.
