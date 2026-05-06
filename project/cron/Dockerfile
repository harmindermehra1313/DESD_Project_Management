FROM python:3.12-slim

<<<<<<< HEAD
# Install cron
RUN apt-get update && apt-get install -y cron
=======
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
>>>>>>> 3e77b523377b434b2111b7871fa3173c202d3a64

# Set working directory
WORKDIR /code

<<<<<<< HEAD
# Copy your project code
COPY . /code
=======
# Copy requirements first for better Docker layer caching
COPY requirements.txt /code/
>>>>>>> 3e77b523377b434b2111b7871fa3173c202d3a64

# Install Python dependencies
RUN pip install -r requirements.txt

<<<<<<< HEAD
=======
# Copy project code
COPY . /code/

>>>>>>> 3e77b523377b434b2111b7871fa3173c202d3a64
# Copy the cron schedule file
COPY cron/crontab.txt /etc/cron.d/brfn-cron

# Give cron permission to read it
RUN chmod 0644 /etc/cron.d/brfn-cron

# Register the cron job
RUN crontab /etc/cron.d/brfn-cron

<<<<<<< HEAD
# Run cron in the foreground (so Docker keeps the container alive)
=======
# Run cron in the foreground so Docker keeps the container alive
>>>>>>> 3e77b523377b434b2111b7871fa3173c202d3a64
CMD ["cron", "-f"]