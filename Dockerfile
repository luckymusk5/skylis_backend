FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Africa/Douala

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY insert_products.py .

RUN mkdir -p /app/data

EXPOSE 8001

HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=5 CMD curl -f http://localhost:8001/health || exit 1

CMD ["python", "insert_products.py"]
