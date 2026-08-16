from datetime import datetime

from app.essl_client import parse_csv, parse_log_line, parse_soap_response, punches_from_push_payload


def test_parse_etimetracklite_tab_line():
    record = parse_log_line("1001\t2026-08-01 09:04:11\tIN\tESSL-RMP-01")
    assert record is not None
    assert record.biometric_user_id == "1001"
    assert record.punch_time == datetime(2026, 8, 1, 9, 4, 11)
    assert record.direction == "IN"
    assert record.device_serial == "ESSL-RMP-01"


def test_parse_direction_aliases():
    assert parse_log_line("1001,2026-08-01 18:01:00,0").direction == "IN"
    assert parse_log_line("1001,2026-08-01 18:01:00,1").direction == "OUT"
    assert parse_log_line("1001,01-08-2026 18:01:00,OUT").direction == "OUT"


def test_parse_ebio_device_log():
    record = parse_log_line("88,2026-08-01 09:02:00,1003,K30PRO,Gate,IN")
    assert record.biometric_user_id == "1003"
    assert record.direction == "IN"
    assert record.device_serial == "K30PRO"


def test_parse_soap_str_data_list():
    xml = """<?xml version="1.0"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
      <soap:Body>
        <GetTransactionsLogResponse xmlns="http://tempuri.org/">
          <strDataList>1001\t2026-08-01 09:00:00\tin\tSN1
1001\t2026-08-01 18:00:00\tout\tSN1</strDataList>
        </GetTransactionsLogResponse>
      </soap:Body>
    </soap:Envelope>
    """
    records = parse_soap_response(xml)
    assert len(records) == 2
    assert records[0].direction == "IN"
    assert records[1].direction == "OUT"


def test_parse_csv_headers():
    csv_text = "biometric_user_id,punch_time,direction\n1002,2026-08-02 09:10:00,IN\n"
    records = parse_csv(csv_text)
    assert len(records) == 1
    assert records[0].biometric_user_id == "1002"


def test_push_payload():
    records = list(
        punches_from_push_payload(
            {
                "SerialNumber": "K30PRO",
                "PunchLog": {
                    "Type": "OUT",
                    "UserId": "1004",
                    "LogTime": "2026-08-02T18:05:00+05:30",
                },
            }
        )
    )
    assert records[0].biometric_user_id == "1004"
    assert records[0].direction == "OUT"
    assert records[0].punch_time.hour == 18
