from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

from juliettia.config import Config

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/gmail.compose",
]


def run_auth_flow(config: Config) -> None:
    """Interactive, browser-based OAuth flow. Must be run on the host, not in Docker."""
    if not config.gmail_client_secret_path.is_file():
        raise FileNotFoundError(
            f"Gmail client secret file not found: {config.gmail_client_secret_path}"
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(config.gmail_client_secret_path), SCOPES
    )
    creds = flow.run_local_server(port=0)

    config.gmail_token_path.parent.mkdir(parents=True, exist_ok=True)
    config.gmail_token_path.write_text(creds.to_json(), encoding="utf-8")
    logger.info("Gmail token written to %s", config.gmail_token_path)


def get_credentials(token_path: Path) -> Credentials:
    if not token_path.is_file():
        raise FileNotFoundError(
            f"Gmail token not found at {token_path}. "
            "Run the script with --auth-only on the host first."
        )

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError as exc:
            raise RuntimeError(
                "Failed to refresh Gmail token; re-run with --auth-only."
            ) from exc
        token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    raise RuntimeError(
        "Gmail credentials are invalid and cannot be refreshed; "
        "re-run with --auth-only."
    )


def build_service(creds: Credentials) -> Resource:
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def ensure_label(service: Resource, label_name: str) -> str:
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    for label in labels:
        if label["name"] == label_name:
            return label["id"]

    created = (
        service.users()
        .labels()
        .create(
            userId="me",
            body={
                "name": label_name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        )
        .execute()
    )
    logger.info("Created Gmail label %r", label_name)
    return created["id"]


def search_unprocessed_message_ids(
    service: Resource, recipient_email: str, processed_label_name: str
) -> list[str]:
    query = f"to:{recipient_email} is:unread -label:{processed_label_name}"
    message_ids: list[str] = []
    page_token: str | None = None

    while True:
        response = (
            service.users()
            .messages()
            .list(userId="me", q=query, pageToken=page_token)
            .execute()
        )
        message_ids.extend(m["id"] for m in response.get("messages", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return message_ids


def get_message(service: Resource, message_id: str) -> dict[str, Any]:
    return (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )


def thread_has_draft(service: Resource, thread_id: str) -> bool:
    thread = (
        service.users()
        .threads()
        .get(userId="me", id=thread_id, format="minimal")
        .execute()
    )
    for message in thread.get("messages", []):
        if "DRAFT" in message.get("labelIds", []):
            return True
    return False


def create_draft(service: Resource, raw_message: str, thread_id: str) -> str:
    draft = (
        service.users()
        .drafts()
        .create(
            userId="me",
            body={"message": {"raw": raw_message, "threadId": thread_id}},
        )
        .execute()
    )
    return draft["id"]


def apply_label(service: Resource, message_id: str, label_id: str) -> None:
    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"addLabelIds": [label_id]},
    ).execute()
