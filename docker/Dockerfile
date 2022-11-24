FROM python:3.9-slim

WORKDIR /web

COPY ./docker/requirements-freeze.txt requirements.txt

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc-dev locales locales-all \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove gcc libc-dev

ENV LC_ALL cs_CZ
ENV LANG cs_CZ
ENV LANGUAGE cs_CZ

COPY . .

EXPOSE 5099

CMD ["gunicorn", "--conf", "./docker/gunicorn.conf.py", "--bind", "0.0.0.0:5099", "app:app"]
