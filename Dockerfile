FROM python:slim-bookworm
ENV PYTHONDONTWRITEBYTECODE 1 \
    PYTHONUNBUFFERED 1
RUN mkdir /code
WORKDIR /code
COPY requirements.txt /code/
RUN apt-get update && apt-get -y install libpq-dev gcc
RUN pip install -r requirements.txt
COPY . /code/
WORKDIR /code/home/
