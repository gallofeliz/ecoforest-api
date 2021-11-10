FROM python:3.8-alpine3.12

RUN pip install retrying requests

WORKDIR /app

ADD app.py .

USER nobody

CMD python -u ./app.py
