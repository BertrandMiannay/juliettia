from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any


@dataclass(frozen=True)
class ParsedEmail:
    gmail_id: str
    thread_id: str
    subject: str
    sender: str
    rfc_message_id: str | None
    references: str | None
    date: str | None
    body: str


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in ("script", "style"):
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self._chunks.append(data.strip())

    def text(self) -> str:
        return "\n".join(self._chunks)


def _strip_html(html: str) -> str:
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    text = extractor.text()
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _decode_part_data(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _iter_parts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    parts = [payload]
    for sub_part in payload.get("parts", []) or []:
        parts.extend(_iter_parts(sub_part))
    return parts


def extract_body(payload: dict[str, Any]) -> str:
    all_parts = _iter_parts(payload)

    for part in all_parts:
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data")
            if data:
                return _decode_part_data(data).strip()

    for part in all_parts:
        if part.get("mimeType") == "text/html":
            data = part.get("body", {}).get("data")
            if data:
                return _strip_html(_decode_part_data(data))

    return ""


def _get_header(headers: list[dict[str, str]], name: str) -> str | None:
    name_lower = name.lower()
    for header in headers:
        if header.get("name", "").lower() == name_lower:
            return header.get("value")
    return None


def parse_message(message: dict[str, Any]) -> ParsedEmail:
    payload = message.get("payload", {})
    headers = payload.get("headers", []) or []

    return ParsedEmail(
        gmail_id=message["id"],
        thread_id=message["threadId"],
        subject=_get_header(headers, "Subject") or "(no subject)",
        sender=_get_header(headers, "From") or "",
        rfc_message_id=_get_header(headers, "Message-ID"),
        references=_get_header(headers, "References"),
        date=_get_header(headers, "Date"),
        body=extract_body(payload),
    )
