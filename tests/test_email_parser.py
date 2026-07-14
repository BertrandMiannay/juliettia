from __future__ import annotations

import json
from pathlib import Path

from juliettia.email_parser import parse_message

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_parse_message_extracts_headers():
    message = load_fixture("sample_message.json")

    email = parse_message(message)

    assert email.gmail_id == "18abc1234567890"
    assert email.thread_id == "18abc1234567800"
    assert email.subject == "Quarterly report"
    assert email.sender == "Alice Example <alice@example.com>"
    assert email.rfc_message_id == "<CA+abc123@mail.example.com>"
    assert email.date == "Mon, 14 Jul 2026 09:00:00 +0000"


def test_parse_message_prefers_plain_text_body():
    message = load_fixture("sample_message.json")

    email = parse_message(message)

    assert "Can you send me the report by Friday?" in email.body
    assert "<p>" not in email.body


def test_parse_message_falls_back_to_html_when_no_plain_part():
    message = load_fixture("sample_message.json")
    # Drop the text/plain part so only text/html remains.
    message["payload"]["parts"] = [
        p for p in message["payload"]["parts"] if p["mimeType"] != "text/plain"
    ]

    email = parse_message(message)

    assert "Can you send me the report by Friday?" in email.body
    assert "<p>" not in email.body
    assert "<html>" not in email.body


def test_parse_message_missing_subject_defaults():
    message = load_fixture("sample_message.json")
    message["payload"]["headers"] = [
        h for h in message["payload"]["headers"] if h["name"] != "Subject"
    ]

    email = parse_message(message)

    assert email.subject == "(no subject)"
