FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir google-genai
# Hent bible.db (91 MB) FØR koden kopieres så laget caches mellom kodeendringer.
RUN curl -fSL -o bible.db https://github.com/tobiashellerslien/bible-search/raw/main/bible.db \
    && [ -s bible.db ] || (echo "bible.db nedlasting feilet" && exit 1)
COPY . .
ENV SERVER_MODE=production
EXPOSE 8421
CMD ["python", "server.py"]
