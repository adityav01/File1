from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from xml.etree import ElementTree as ET

import httpx

SOAP_NS = "http://tempuri.org/"
SOAP_ENV = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetTransactionsLog xmlns="http://tempuri.org/">
      <FromDateTime>{from_time}</FromDateTime>
      <ToDateTime>{to_time}</ToDateTime>
      <SerialNumber>{serial}</SerialNumber>
      <UserName>{username}</UserName>
      <UserPassword>{password}</UserPassword>
      <strDataList></strDataList>
    </GetTransactionsLog>
  </soap:Body>
</soap:Envelope>
"""


@dataclass(frozen=True)
class PunchRecord:
    biometric_user_id: str
    punch_time: datetime
    direction: str
    device_serial: str = ""
    raw: str = ""


def normalize_direction(value: str | None) -> str:
    if not value:
        return "UNKNOWN"
    token = value.strip().upper()
    mapping = {
        "IN": "IN",
        "I": "IN",
        "0": "IN",
        "CHECK-IN": "IN",
        "CHECKIN": "IN",
        "ENTRY": "IN",
        "OUT": "OUT",
        "O": "OUT",
        "1": "OUT",
        "CHECK-OUT": "OUT",
        "CHECKOUT": "OUT",
        "EXIT": "OUT",
    }
    return mapping.get(token, "UNKNOWN")


def parse_punch_time(value: str) -> datetime:
    text = value.strip().strip('"')
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported punch time: {value}")


def parse_log_line(line: str) -> PunchRecord | None:
    text = line.strip()
    if not text:
        return None
    if "\t" in text:
        parts = [part.strip() for part in text.split("\t")]
    elif ";" in text:
        parts = [part.strip() for part in text.split(";")]
    else:
        parts = [part.strip() for part in re.split(r"\s*,\s*", text)]

    if len(parts) < 2:
        return None

    # eBioServer device logs: LogId, DateTime, EmpCode, Device, Location, Direction
    if len(parts) >= 6 and _looks_like_datetime(parts[1]):
        return PunchRecord(
            biometric_user_id=parts[2],
            punch_time=parse_punch_time(parts[1]),
            direction=normalize_direction(parts[5]),
            device_serial=parts[3],
            raw=text,
        )

    # eTimeTrackLite GetTransactionsLog: UserId, DateTime, Direction, Serial
    if _looks_like_datetime(parts[1]):
        return PunchRecord(
            biometric_user_id=parts[0],
            punch_time=parse_punch_time(parts[1]),
            direction=normalize_direction(parts[2] if len(parts) > 2 else ""),
            device_serial=parts[3] if len(parts) > 3 else "",
            raw=text,
        )
    return None


def _looks_like_datetime(value: str) -> bool:
    try:
        parse_punch_time(value)
        return True
    except ValueError:
        return False


def parse_str_data_list(payload: str) -> list[PunchRecord]:
    records: list[PunchRecord] = []
    for line in payload.splitlines():
        record = parse_log_line(line)
        if record:
            records.append(record)
    return records


def parse_soap_response(xml_text: str) -> list[PunchRecord]:
    root = ET.fromstring(xml_text)
    node = root.find(f".//{{{SOAP_NS}}}strDataList")
    if node is None or not node.text:
        node = root.find(".//{*}strDataList")
    if node is None or not node.text:
        return []
    return parse_str_data_list(node.text)


def parse_csv(content: str) -> list[PunchRecord]:
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames:
        rows = list(reader)
        records: list[PunchRecord] = []
        for row in rows:
            lowered = {str(k).strip().lower(): (v or "").strip() for k, v in row.items() if k}
            user_id = (
                lowered.get("biometric_user_id")
                or lowered.get("userid")
                or lowered.get("user_id")
                or lowered.get("empcode")
                or lowered.get("emp_code")
                or lowered.get("employeecode")
            )
            punch_time = (
                lowered.get("punch_time")
                or lowered.get("logtime")
                or lowered.get("datetime")
                or lowered.get("date_time")
            )
            if not user_id or not punch_time:
                continue
            records.append(
                PunchRecord(
                    biometric_user_id=user_id,
                    punch_time=parse_punch_time(punch_time),
                    direction=normalize_direction(
                        lowered.get("direction") or lowered.get("inout") or lowered.get("status")
                    ),
                    device_serial=lowered.get("device_serial") or lowered.get("serial") or "",
                    raw=",".join(row.values()),
                )
            )
        if records:
            return records

    records = []
    for line in content.splitlines()[1:] if "," in content.splitlines()[0] else content.splitlines():
        record = parse_log_line(line)
        if record:
            records.append(record)
    return records


class EsslSoapClient:
    def __init__(self, soap_url: str, timeout: float = 30.0):
        self.soap_url = soap_url.rstrip("/")
        self.timeout = timeout

    def fetch_transactions(
        self,
        *,
        from_time: datetime,
        to_time: datetime,
        username: str,
        password: str,
        serial_number: str,
    ) -> list[PunchRecord]:
        body = SOAP_ENV.format(
            from_time=from_time.strftime("%Y-%m-%d %H:%M:%S"),
            to_time=to_time.strftime("%Y-%m-%d %H:%M:%S"),
            serial=serial_number,
            username=username,
            password=password,
        )
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "http://tempuri.org/GetTransactionsLog",
        }
        response = httpx.post(self.soap_url, content=body, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return parse_soap_response(response.text)


def punches_from_push_payload(payload: dict) -> Iterable[PunchRecord]:
    punch = payload.get("PunchLog") or payload
    user_id = str(punch.get("UserId") or punch.get("biometric_user_id") or "")
    log_time = str(punch.get("LogTime") or punch.get("punch_time") or "")
    if not user_id or not log_time:
        return []
    serial = str(payload.get("SerialNumber") or punch.get("device_serial") or "")
    return [
        PunchRecord(
            biometric_user_id=user_id,
            punch_time=parse_punch_time(log_time.replace("T", " ").split("+")[0]),
            direction=normalize_direction(str(punch.get("Type") or punch.get("direction") or "")),
            device_serial=serial,
            raw=str(payload),
        )
    ]
