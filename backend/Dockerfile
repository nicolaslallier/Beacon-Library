# Multistage Dockerfile for beacon-library backend (Python/Poetry)
FROM python:3.11-slim as base

# Set environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# -- Dependencies for Poetry + build
RUN apt-get update && apt-get install -y curl gcc git && rm -rf /var/lib/apt/lists/*

# -- Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# -- Install python dependencies (cache layer)
COPY backend/pyproject.toml backend/poetry.lock ./
RUN poetry install --only main --no-root

# -- Copy backend code
COPY backend /app

# -- Install dev dependencies if needed
ARG DEV=0
RUN if [ "$DEV" = "1" ]; then poetry install --no-root; fi

# -- Final image for production
FROM base as prod
ENV DEV=0
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# -- Development image (optional, enables hot-reload)
FROM base as dev
ENV DEV=1
RUN poetry install --no-root
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
