# juliettia

AI agent for automated email replies. It reads Gmail messages addressed to a
configured recipient, generates a reply with the Mistral API using a
configurable prompt, and creates a Gmail **draft** in the right thread. It
never sends automatically — every reply is left as a draft for you to review.

The script is a one-shot batch job: each run scans unread, unprocessed
matching emails and exits. It's meant to be triggered periodically by an
external scheduler (cron, or a platform routine), not run as a daemon.

## How it works

1. Authenticate to Gmail via OAuth2 (read-only + labels + compose scopes).
2. Search for unread emails addressed to `TARGET_RECIPIENT_EMAIL` that don't
   already have the `AI-Processed` label (optionally restricted to senders on
   `SENDER_DOMAIN_FILTER`).
3. For each match: parse the email, call the Mistral API with your configured
   prompt, build a threaded MIME reply, create it as a Gmail draft, and apply
   the `AI-Processed` label.
4. Emails that already have a draft in their thread are skipped, and a failed
   email doesn't stop the batch — it's simply retried on the next run.

## Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/)
- A Google Cloud project with the Gmail API enabled and an OAuth 2.0 Client
  ID of type **Desktop app** (download as `client_secret.json`)
- A [Mistral API key](https://console.mistral.ai/)
- Docker, if you want to run it containerized

## Setup

### 1. Install dependencies

```bash
poetry install
```

### 2. Configure

```bash
cp .env.example .env
```

Fill in `.env`:

| Variable | Description |
|---|---|
| `MISTRAL_API_KEY` | Your Mistral API key |
| `MISTRAL_MODEL` | Model name (default: `mistral-large-latest`) |
| `TARGET_RECIPIENT_EMAIL` | Only emails addressed to this address are processed |
| `SENDER_DOMAIN_FILTER` | Optional. If set, only emails sent from this domain are processed (e.g. `brevosend.com` for a Brevo contact-form relay) |
| `GMAIL_CLIENT_SECRET_PATH` | Path to the downloaded OAuth client secret JSON |
| `GMAIL_TOKEN_PATH` | Where the OAuth token is stored after first auth |
| `REPLY_PROMPT_PATH` | Path to the instruction prompt given to Mistral |
| `PROCESSED_LABEL_NAME` | Gmail label used to mark processed emails (default: `AI-Processed`) |
| `LOG_LEVEL` | Python logging level (default: `INFO`) |
| `DRY_RUN` | If `true`, generate replies but skip draft creation/labeling |

Place your downloaded OAuth client secret at `credentials/client_secret.json`
(the `credentials/` directory is gitignored). Edit `prompts/reply_instructions.txt`
to customize how replies are written (tone, persona, constraints, etc.).

### 3. First-time Gmail authorization (on the host, not in Docker)

Gmail's OAuth flow opens a browser, which doesn't work inside a container.
Run this once, directly on your machine:

```bash
poetry run juliettia --auth-only
```

This opens a browser for consent and writes `credentials/token.json`. All
later runs (including in Docker) reuse and auto-refresh this token — no
further browser interaction is needed unless you delete the token or change
the requested scopes.

### 4. Try a dry run

```bash
poetry run juliettia --dry-run
```

This performs the real Gmail search and the real Mistral call, but skips
draft creation and labeling — it just logs what it would have drafted. Use
it to validate connectivity and iterate on the prompt without creating
drafts.

### 5. Run for real

```bash
poetry run juliettia
```

## Running with Docker

Build the image:

```bash
docker build -t juliettia .
```

Run one batch (the container exits after one pass, like the script itself):

```bash
docker run --rm \
  --env-file .env \
  -v "$(pwd)/credentials:/app/credentials" \
  juliettia
```

The `credentials/` volume mount is required: it lets the container read
`client_secret.json`/`token.json` and write back the refreshed token so you
don't have to re-authenticate on every run. Secrets are only ever passed at
runtime (`--env-file`, volume mount) — never baked into the image.

`--auth-only` must be run on the host beforehand (see step 3); it will not
work inside the container since there's no browser available.

A `docker-compose.yml` is provided as a convenience wrapper for the same
invocation:

```bash
docker compose run --rm juliettia
```

Note this project is **not** meant to run as a long-lived service — don't
`docker compose up` it.

## Scheduling

Trigger the container periodically with a host cron entry, for example every
5 minutes:

```cron
*/5 * * * * cd /path/to/juliettia && docker run --rm --env-file .env -v "$(pwd)/credentials:/app/credentials" juliettia >> /var/log/juliettia.log 2>&1
```

Or point your scheduler/routine system at the same `docker run` (or
`docker compose run --rm juliettia`) command.

## Development

```bash
poetry install
poetry run pytest
poetry run ruff check .
```

Unit tests cover email parsing and MIME reply construction using fixture
data — no live Gmail or Mistral credentials are needed to run them.
