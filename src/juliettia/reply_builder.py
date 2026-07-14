from __future__ import annotations

import base64
import re
from email.message import EmailMessage
from email.utils import parseaddr

from juliettia.email_parser import ParsedEmail

_RE_PREFIX_RE = re.compile(r"^re\s*:\s*", re.IGNORECASE)


def build_reply_subject(original_subject: str) -> str:
    if _RE_PREFIX_RE.match(original_subject):
        return original_subject
    return f"Re: {original_subject}"


def build_references(original: ParsedEmail) -> str | None:
    if not original.rfc_message_id:
        return original.references
    if original.references:
        return f"{original.references} {original.rfc_message_id}"
    return original.rfc_message_id


def build_quoted_body(original: ParsedEmail, reply_text: str) -> str:
    sender_name, sender_addr = parseaddr(original.sender)
    attribution = sender_name or sender_addr or "the original sender"
    quoted_lines = "\n".join(
        f"> {line}" for line in original.body.splitlines()
    )
    header = f"On {original.date}, {attribution} wrote:" if original.date else f"{attribution} wrote:"
    return f"{reply_text}\n\n{header}\n{quoted_lines}"


def resolve_reply_address(original: ParsedEmail) -> str:
    """Return the address a reply should be sent to.

    Prefers the ``Reply-To`` header over ``From``: transactional relays (e.g.
    Brevo's contact-form forwarding) commonly send ``From`` a relay domain
    like ``*.brevosend.com`` while ``Reply-To`` carries the real submitter's
    address, mirroring what Gmail's own Reply button targets.
    """
    _, reply_to_addr = parseaddr(original.reply_to or "")
    if reply_to_addr:
        return reply_to_addr

    _, sender_addr = parseaddr(original.sender)
    if not sender_addr:
        raise ValueError(f"Could not parse a recipient address from: {original.sender!r}")
    return sender_addr


def build_mime_reply(original: ParsedEmail, reply_text: str) -> str:
    reply_addr = resolve_reply_address(original)

    message = EmailMessage()
    message["To"] = reply_addr
    message["Subject"] = build_reply_subject(original.subject)

    if original.rfc_message_id:
        message["In-Reply-To"] = original.rfc_message_id

    references = build_references(original)
    if references:
        message["References"] = references

    message.set_content(build_quoted_body(original, reply_text))

    raw_bytes = message.as_bytes()
    return base64.urlsafe_b64encode(raw_bytes).decode("ascii")
