FROM python:3.12-slim

#set enviroment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

#set work directory
WORKDIR /code

#install dependencies
COPY requirements.txt /code/
RUN pip install --no-cache-dir -r requirements.txt

#copy project
COPY . /code/