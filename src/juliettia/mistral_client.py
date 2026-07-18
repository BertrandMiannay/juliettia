from __future__ import annotations

import json
from dataclasses import dataclass

from mistralai.client import Mistral

from juliettia.email_parser import ParsedEmail

_JSON_FORMAT_INSTRUCTIONS = (
    "\n\n# Format de sortie\n"
    "Réponds uniquement avec un objet JSON valide (sans markdown, sans texte hors JSON), "
    "avec exactement ces clés :\n"
    '- "reply_text" : la réponse rédigée, dans la même langue que le mail reçu.\n'
    '- "classification" : une chaîne décrivant la nature du message, par exemple '
    '"legitimate", "spam" ou "other".\n'
    '- "redirect_to" : une adresse email vers laquelle rediriger la demande si elle '
    "ne concerne pas le club ou nécessite un autre interlocuteur, sinon null."
)


@dataclass(frozen=True)
class GeneratedReply:
    reply_text: str
    classification: str
    redirect_to: str | None


def build_user_message(email: ParsedEmail) -> str:
    return (
        f"From: {email.sender}\n"
        f"Subject: {email.subject}\n\n"
        f"{email.body}"
    )


def _parse_generated_reply(content: str) -> GeneratedReply:
    fallback = GeneratedReply(reply_text=content, classification="legitimate", redirect_to=None)

    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return fallback

    if not isinstance(data, dict):
        return fallback

    reply_text = str(data.get("reply_text") or "").strip()
    if not reply_text:
        return fallback

    classification = str(data.get("classification") or "").strip() or "legitimate"

    redirect_to_raw = data.get("redirect_to")
    redirect_to = str(redirect_to_raw).strip() or None if redirect_to_raw else None

    return GeneratedReply(
        reply_text=reply_text,
        classification=classification,
        redirect_to=redirect_to,
    )


def generate_reply(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    email: ParsedEmail,
) -> GeneratedReply:
    client = Mistral(api_key=api_key)

    response = client.chat.complete(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt + _JSON_FORMAT_INSTRUCTIONS},
            {"role": "user", "content": build_user_message(email)},
        ],
    )

    content = response.choices[0].message.content
    if isinstance(content, list):
        content = "".join(
            chunk.text for chunk in content if hasattr(chunk, "text")
        )
    content = (content or "").strip()

    return _parse_generated_reply(content)
