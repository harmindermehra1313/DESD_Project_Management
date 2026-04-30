FROM python:3.12-slim

# Install cron
RUN apt-get update && apt-get install -y cron

# Set working directory
WORKDIR /code

# Copy your project code
COPY . /code

# Install Python dependencies
RUN pip install -r requirements.txt

# Copy the cron schedule file
COPY cron/crontab.txt /etc/cron.d/brfn-cron

# Give cron permission to read it
RUN chmod 0644 /etc/cron.d/brfn-cron

# Register the cron job
RUN crontab /etc/cron.d/brfn-cron

# Run cron in the foreground (so Docker keeps the container alive)
CMD ["cron", "-f"]