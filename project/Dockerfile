FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    ninja-build \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /code

# Install dependencies
COPY requirements.txt /code/

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy project
COPY . /code/
