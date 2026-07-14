from __future__ import annotations

import base64

import pytest

from juliettia.email_parser import ParsedEmail
from juliettia.reply_builder import (
    build_mime_reply,
    build_references,
    build_reply_subject,
)


def make_email(**overrides) -> ParsedEmail:
    defaults = dict(
        gmail_id="msg-1",
        thread_id="thread-1",
        subject="Quarterly report",
        sender="Alice Example <alice@example.com>",
        rfc_message_id="<CA+abc123@mail.example.com>",
        references=None,
        date="Mon, 14 Jul 2026 09:00:00 +0000",
        body="Can you send me the report by Friday?",
    )
    defaults.update(overrides)
    return ParsedEmail(**defaults)


def test_build_reply_subject_adds_re_prefix():
    assert build_reply_subject("Quarterly report") == "Re: Quarterly report"


def test_build_reply_subject_does_not_double_prefix():
    assert build_reply_subject("Re: Quarterly report") == "Re: Quarterly report"
    assert build_reply_subject("RE:   Quarterly report") == "RE:   Quarterly report"


def test_build_references_appends_original_message_id():
    email = make_email(references="<old-1@example.com>")
    assert (
        build_references(email)
        == "<old-1@example.com> <CA+abc123@mail.example.com>"
    )


def test_build_references_falls_back_to_message_id_only():
    email = make_email(references=None)
    assert build_references(email) == "<CA+abc123@mail.example.com>"


def test_build_mime_reply_sets_threading_headers():
    email = make_email()

    raw = build_mime_reply(email, "Sure, I'll send it by Friday.")
    decoded = base64.urlsafe_b64decode(raw).decode("utf-8")

    assert "To: alice@example.com" in decoded
    assert "Subject: Re: Quarterly report" in decoded
    assert "In-Reply-To: <CA+abc123@mail.example.com>" in decoded
    assert "References: <CA+abc123@mail.example.com>" in decoded
    assert "Sure, I'll send it by Friday." in decoded


def test_build_mime_reply_raises_without_parseable_sender():
    email = make_email(sender="")

    with pytest.raises(ValueError):
        build_mime_reply(email, "Hello")
