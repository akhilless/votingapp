FROM python:3.11.2-alpine3.17
EXPOSE 8000
EXPOSE 22
RUN adduser -h /home/votingapp -s /bin/sh -D votingapp;

COPY requirements.txt .
COPY docker_entrypoint.sh .

RUN pip install --upgrade pip; \
    pip install -r requirements.txt;