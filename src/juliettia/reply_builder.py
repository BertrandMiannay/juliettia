from __future__ import annotations

import base64
import html
import re
from email.message import EmailMessage
from email.utils import parseaddr

import markdown

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


def _attribution_header(original: ParsedEmail) -> str:
    sender_name, sender_addr = parseaddr(original.sender)
    attribution = sender_name or sender_addr or "the original sender"
    if original.date:
        return f"On {original.date}, {attribution} wrote:"
    return f"{attribution} wrote:"


def build_quoted_body(original: ParsedEmail, reply_text: str) -> str:
    quoted_lines = "\n".join(
        f"> {line}" for line in original.body.splitlines()
    )
    header = _attribution_header(original)
    return f"{reply_text}\n\n{header}\n{quoted_lines}"


def build_html_body(original: ParsedEmail, reply_text: str) -> str:
    reply_html = markdown.markdown(reply_text)
    header = html.escape(_attribution_header(original))
    quoted_html = html.escape(original.body).replace("\n", "<br>\n")
    return (
        f"{reply_html}\n"
        f"<p>{header}</p>\n"
        '<blockquote style="margin:0 0 0 .8ex;border-left:1px solid #ccc;'
        f'padding-left:1ex">{quoted_html}</blockquote>'
    )


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


def build_mime_reply(
    original: ParsedEmail,
    reply_text: str,
    *,
    reply_addr_override: str | None = None,
) -> str:
    reply_addr = reply_addr_override or resolve_reply_address(original)

    message = EmailMessage()
    message["To"] = reply_addr
    message["Subject"] = build_reply_subject(original.subject)

    if original.rfc_message_id:
        message["In-Reply-To"] = original.rfc_message_id

    references = build_references(original)
    if references:
        message["References"] = references

    message.set_content(build_quoted_body(original, reply_text))
    message.add_alternative(build_html_body(original, reply_text), subtype="html")

    raw_bytes = message.as_bytes()
    return base64.urlsafe_b64encode(raw_bytes).decode("ascii")
