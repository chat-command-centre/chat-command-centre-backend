FROM python:3.12-slim-bullseye  # Changed from 'python:3.12-slim-buster' to 'python:3.12-slim-bullseye'

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry

# Copy pyproject.toml and poetry.lock to install dependencies
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Copy the rest of the backend code
COPY . .

# Expose port
EXPOSE 8000

# Start the Uvicorn server
CMD ["uvicorn", "command_centre_python.core.server:app", "--host", "0.0.0.0", "--port", "8000"]