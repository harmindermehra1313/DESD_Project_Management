FROM python:3.12-slim

#set enviroment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

#set work directory
WORKDIR /code

#install dependencies
COPY requirements.txt /code/
RUN pip install --no-cache-dir -r requirements.txt

#copy project
COPY . /code/