FROM python:3.12-slim

# Czech text is handled in Python, not by the C library: the app no longer calls
# locale.setlocale(), so the image needs neither locales nor locales-all.
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # The ORIS response cache is written at runtime. It lives outside /web/data
    # so that the data directory can be mounted read-only if desired.
    BZL_ORIS_CACHE_DIR=/var/cache/bzl

WORKDIR /web

# pandas, numpy and the rest all ship manylinux wheels, so no compiler is needed.
COPY ./docker/requirements-freeze.txt requirements.txt
RUN python -m pip install --no-cache-dir uv \
    && uv pip install --no-cache-dir --system -r requirements.txt \
    && python -m pip uninstall -y uv

COPY . .

# Run as an unprivileged user. It owns only the cache directory: nothing writes
# to /web at runtime, so the application cannot modify its own code or data.
# (PYTHONDONTWRITEBYTECODE above keeps Python from trying to drop .pyc files there.)
RUN useradd --create-home --uid 10001 bzl \
    && mkdir -p "$BZL_ORIS_CACHE_DIR" \
    && chown -R bzl:bzl "$BZL_ORIS_CACHE_DIR"
USER bzl

EXPOSE 5099

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5099/news', timeout=4)"

CMD ["gunicorn", "--conf", "./docker/gunicorn.conf.py", "--bind", "0.0.0.0:5099", "app:app"]
