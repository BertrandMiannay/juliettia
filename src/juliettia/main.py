from __future__ import annotations

import argparse
import logging
import sys

from juliettia import gmail_client, mistral_client
from juliettia.config import Config, ConfigError, load_config
from juliettia.email_parser import parse_message
from juliettia.logging_utils import setup_logging
from juliettia.reply_builder import build_mime_reply

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="juliettia",
        description="AI agent that drafts Gmail replies using the Mistral API.",
    )
    parser.add_argument(
        "--auth-only",
        action="store_true",
        help=(
            "Run the interactive Gmail OAuth flow (opens a browser) and exit. "
            "Must be run on the host, not inside Docker."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Fetch matching emails and generate replies via Mistral, but skip "
            "draft creation and labeling. Overrides the DRY_RUN env var."
        ),
    )
    return parser.parse_args(argv)


def run_auth_only(config: Config) -> int:
    gmail_client.run_auth_flow(config)
    return 0


def process_message(
    service, config: Config, label_id: str, message_id: str, dry_run: bool
) -> bool:
    message = gmail_client.get_message(service, message_id)
    email = parse_message(message)

    if gmail_client.thread_has_draft(service, email.thread_id):
        logger.info(
            "Skipping message %s: a draft already exists in thread %s",
            email.gmail_id,
            email.thread_id,
        )
        return True

    reply_text = mistral_client.generate_reply(
        api_key=config.mistral_api_key,
        model=config.mistral_model,
        system_prompt=config.reply_instructions,
        email=email,
    )

    if dry_run:
        logger.info(
            "[DRY RUN] Would draft reply to %s (subject=%r):\n%s",
            email.sender,
            email.subject,
            reply_text,
        )
        return True

    raw_reply = build_mime_reply(email, reply_text)
    gmail_client.create_draft(service, raw_reply, email.thread_id)
    gmail_client.apply_label(service, email.gmail_id, label_id)
    logger.info("Created draft reply for message %s from %s", email.gmail_id, email.sender)
    return True


def run(config: Config, dry_run: bool) -> int:
    creds = gmail_client.get_credentials(config.gmail_token_path)
    service = gmail_client.build_service(creds)

    label_id = gmail_client.ensure_label(service, config.processed_label_name)

    message_ids = gmail_client.search_unprocessed_message_ids(
        service,
        config.target_recipient_email,
        config.processed_label_name,
        config.sender_domain_filter,
    )
    logger.info("Found %d message(s) to process", len(message_ids))

    succeeded = 0
    failed = 0
    for message_id in message_ids:
        try:
            process_message(service, config, label_id, message_id, dry_run)
            succeeded += 1
        except Exception:
            failed += 1
            logger.exception("Failed to process message %s", message_id)

    logger.info(
        "Run complete: processed=%d succeeded=%d failed=%d",
        len(message_ids),
        succeeded,
        failed,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        if args.auth_only:
            config = load_config(strict=False)
            setup_logging(config.log_level)
            return run_auth_only(config)

        config = load_config(strict=True)
        setup_logging(config.log_level)
        dry_run = args.dry_run or config.dry_run
        return run(config, dry_run)
    except ConfigError as exc:
        logging.basicConfig(level=logging.ERROR)
        logger.error("Configuration error: %s", exc)
        return 1
    except Exception:
        logging.basicConfig(level=logging.ERROR)
        logger.exception("Run-level failure")
        return 1


if __name__ == "__main__":
    sys.exit(main())
