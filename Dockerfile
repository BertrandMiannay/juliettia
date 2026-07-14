FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=false \
    POETRY_NO_INTERACTION=1

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock README.md ./
RUN poetry install --no-root --only main --no-cache

COPY src/ ./src/
COPY prompts/ ./prompts/
RUN poetry install --only main --no-cache

ENTRYPOINT ["poetry", "run", "juliettia"]
