from __future__ import annotations

from mistralai.client import Mistral

from juliettia.email_parser import ParsedEmail


def build_user_message(email: ParsedEmail) -> str:
    return (
        f"From: {email.sender}\n"
        f"Subject: {email.subject}\n\n"
        f"{email.body}"
    )


def generate_reply(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    email: ParsedEmail,
) -> str:
    client = Mistral(api_key=api_key)

    response = client.chat.complete(
        model=model,
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
    return (content or "").strip()
