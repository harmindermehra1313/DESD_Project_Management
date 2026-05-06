FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install cron and build tools required by implicit
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \    
    build-essential \
    cmake \
    ninja-build \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /code

# Copy requirements first for better Docker layer caching
COPY requirements.txt /code/

# Install Python dependencies
RUN pip install -r requirements.txt

# Copy project code
COPY . /code/

# Copy the cron schedule file
COPY cron/crontab.txt /etc/cron.d/brfn-cron

# Give cron permission to read it
RUN chmod 0644 /etc/cron.d/brfn-cron

# Register the cron job
RUN crontab /etc/cron.d/brfn-cron

# Run cron in the foreground so Docker keeps the container alive
CMD ["cron", "-f"]