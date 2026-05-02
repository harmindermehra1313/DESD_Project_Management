FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    build-essential \
    gcc \
    g++ \
    make \
    cmake \
    ninja-build \
    libpq-dev \
    libopenblas-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /code

# Install dependencies
COPY requirements.txt /code/

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy project
COPY . /code/

# Register cron schedule
COPY cron/crontab.txt /etc/cron.d/brfn-cron
RUN chmod 0644 /etc/cron.d/brfn-cron
RUN crontab /etc/cron.d/brfn-cron