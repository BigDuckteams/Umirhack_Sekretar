FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-rus && rm -rf /var/lib/apt/lists/*
WORKDIR /srv/app
COPY pyproject.toml README.md ./
COPY app ./app
COPY data ./data
RUN pip install .
RUN useradd --create-home --uid 10001 appuser && mkdir -p /srv/app/artifacts && chown -R appuser:appuser /srv/app
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
