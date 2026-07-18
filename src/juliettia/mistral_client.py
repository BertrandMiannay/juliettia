from __future__ import annotations

from mistralai.client import Mistral
from mistralai.extra import response_format_from_pydantic_model
from pydantic import BaseModel, Field, ValidationError, field_validator

from juliettia.email_parser import ParsedEmail


class GeneratedReply(BaseModel):
    reply_text: str = Field(
        description="La réponse rédigée, dans la même langue que le mail reçu."
    )
    classification: str = Field(
        default="legitimate",
        description=(
            "Une chaîne décrivant la nature du message, par exemple "
            '"legitimate", "spam" ou "other".'
        ),
    )
    redirect_to: str | None = Field(
        default=None,
        description=(
            "Une adresse email vers laquelle rediriger la demande si elle ne "
            "concerne pas le club ou nécessite un autre interlocuteur, sinon null."
        ),
    )

    @field_validator("reply_text", mode="before")
    @classmethod
    def _require_non_empty_reply_text(cls, value: object) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("reply_text must not be empty")
        return text

    @field_validator("classification", mode="before")
    @classmethod
    def _default_classification(cls, value: object) -> str:
        return str(value or "").strip() or "legitimate"

    @field_validator("redirect_to", mode="before")
    @classmethod
    def _normalize_redirect_to(cls, value: object) -> str | None:
        if not value:
            return None
        return str(value).strip() or None


_RESPONSE_FORMAT = response_format_from_pydantic_model(GeneratedReply)


def build_user_message(email: ParsedEmail) -> str:
    return (
        f"From: {email.sender}\n"
        f"Subject: {email.subject}\n\n"
        f"{email.body}"
    )


def _parse_generated_reply(content: str) -> GeneratedReply:
    try:
        return GeneratedReply.model_validate_json(content)
    except ValidationError:
        return GeneratedReply.model_construct(
            reply_text=content, classification="legitimate", redirect_to=None
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
        response_format=_RESPONSE_FORMAT,
        messages=[
            {"role": "system", "content": system_prompt},
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
