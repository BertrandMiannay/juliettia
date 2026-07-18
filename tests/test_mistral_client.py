from __future__ import annotations

import json
from types import SimpleNamespace

from juliettia import mistral_client
from juliettia.email_parser import ParsedEmail


def make_email(**overrides) -> ParsedEmail:
    defaults = dict(
        gmail_id="msg-1",
        thread_id="thread-1",
        subject="Quarterly report",
        sender="Alice Example <alice@example.com>",
        reply_to=None,
        rfc_message_id="<CA+abc123@mail.example.com>",
        references=None,
        date="Mon, 14 Jul 2026 09:00:00 +0000",
        body="Can you send me the report by Friday?",
    )
    defaults.update(overrides)
    return ParsedEmail(**defaults)


def install_fake_mistral(monkeypatch, content, calls: list):
    def complete(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    def fake_mistral(api_key):
        return SimpleNamespace(chat=SimpleNamespace(complete=complete))

    monkeypatch.setattr(mistral_client, "Mistral", fake_mistral)


def call_generate_reply(**overrides):
    kwargs = dict(
        api_key="key",
        model="mistral-large-latest",
        system_prompt="Be nice.",
        email=make_email(),
    )
    kwargs.update(overrides)
    return mistral_client.generate_reply(**kwargs)


def test_generate_reply_parses_legitimate_json(monkeypatch):
    calls: list = []
    content = json.dumps(
        {
            "reply_text": "Bonjour, merci pour votre message.",
            "classification": "legitimate",
            "redirect_to": None,
        }
    )
    install_fake_mistral(monkeypatch, content, calls)

    result = call_generate_reply()

    assert result == mistral_client.GeneratedReply(
        reply_text="Bonjour, merci pour votre message.",
        classification="legitimate",
        redirect_to=None,
    )
    assert calls[0]["response_format"] == mistral_client._RESPONSE_FORMAT
    assert calls[0]["response_format"]["type"] == "json_schema"
    assert calls[0]["response_format"]["json_schema"]["name"] == "GeneratedReply"


def test_generate_reply_parses_spam_classification(monkeypatch):
    calls: list = []
    content = json.dumps(
        {
            "reply_text": "N/A",
            "classification": "spam",
            "redirect_to": None,
        }
    )
    install_fake_mistral(monkeypatch, content, calls)

    result = call_generate_reply()

    assert result.classification == "spam"


def test_generate_reply_parses_redirect_to(monkeypatch):
    calls: list = []
    content = json.dumps(
        {
            "reply_text": "Merci, je transmets à la bonne personne.",
            "classification": "other",
            "redirect_to": "president@touraine-plongee.org",
        }
    )
    install_fake_mistral(monkeypatch, content, calls)

    result = call_generate_reply()

    assert result.redirect_to == "president@touraine-plongee.org"


def test_generate_reply_falls_back_on_non_json_content(monkeypatch):
    calls: list = []
    content = "Bonjour, voici ma réponse."
    install_fake_mistral(monkeypatch, content, calls)

    result = call_generate_reply()

    assert result.reply_text == "Bonjour, voici ma réponse."
    assert result.classification == "legitimate"
    assert result.redirect_to is None


def test_generate_reply_falls_back_when_reply_text_missing(monkeypatch):
    calls: list = []
    content = json.dumps({"classification": "spam"})
    install_fake_mistral(monkeypatch, content, calls)

    result = call_generate_reply()

    assert result.reply_text == content
    assert result.classification == "legitimate"
    assert result.redirect_to is None


def test_generate_reply_merges_list_content_chunks(monkeypatch):
    calls: list = []
    payload = json.dumps(
        {
            "reply_text": "Réponse assemblée.",
            "classification": "legitimate",
            "redirect_to": None,
        }
    )
    content = [SimpleNamespace(text=payload[:10]), SimpleNamespace(text=payload[10:])]
    install_fake_mistral(monkeypatch, content, calls)

    result = call_generate_reply()

    assert result.reply_text == "Réponse assemblée."


def test_generate_reply_sends_system_prompt_unchanged(monkeypatch):
    calls: list = []
    content = json.dumps(
        {"reply_text": "ok", "classification": "legitimate", "redirect_to": None}
    )
    install_fake_mistral(monkeypatch, content, calls)

    call_generate_reply(system_prompt="Be nice.")

    system_message = calls[0]["messages"][0]["content"]
    assert system_message == "Be nice."
