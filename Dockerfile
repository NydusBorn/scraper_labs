FROM ghcr.io/astral-sh/uv:debian-slim

WORKDIR /app

COPY ./pyproject.toml /app

RUN uv sync -U

COPY . /app

ENV INTERMEDIATE_DATASET_DIR "/intermediate"
ENV REVIEWS_DB "/app/reviews.db"
ENV PYTHONPATH "/app"

ENTRYPOINT uv run Server/serve.py 