FROM python:alpine

RUN pip install retrying requests

WORKDIR /app

ADD app.py .

CMD ./app.py
