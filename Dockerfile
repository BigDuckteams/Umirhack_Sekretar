# Онлайн-деканат в контейнере: Tesseract + русский язык + веб-интерфейс.
# Образ собран по описанию, но в среде разработки не собирался (там не было Docker-сборки) — при проблемах смотрите README.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng tesseract-ocr-osd libglib2.0-0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# в контейнере слушаем все интерфейсы; редактирование типов документов и Положения из веб-интерфейса по умолчанию выключено
ENV DEKANAT_SERVER_HOST=0.0.0.0 \
    DEKANAT_SERVER_ALLOW_EDIT=false \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "-m", "dekanat", "serve", "--host", "0.0.0.0", "--port", "8000"]
