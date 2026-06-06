FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Africa/Douala

RUN apt-get update && apt-get install -y --no-install-recommends cron ca-certificates curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scraper_utils.py .
COPY mainscrape.py .
COPY techdeal_scrape.py .
COPY djoolah_scrape.py .
COPY kmerphone_scrape.py .
COPY nkclmarket_scrape.py .

RUN mkdir -p /app/output

COPY Crontab.txt /etc/cron.d/scraper-cron
RUN chmod 0644 /etc/cron.d/scraper-cron && crontab /etc/cron.d/scraper-cron && touch /app/output/scraper.log

HEALTHCHECK --interval=60s --timeout=10s --start-period=5s --retries=3 CMD pgrep cron > /dev/null || exit 1

CMD ["cron", "-f"]
