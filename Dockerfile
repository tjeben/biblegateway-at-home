FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir google-genai

# Hent bible.db fra privat repo (krever GITHUB_TOKEN ved build).
# Lagt før COPY . . så laget caches mellom kodeendringer.
ARG GITHUB_TOKEN
RUN test -n "$GITHUB_TOKEN" || (echo "GITHUB_TOKEN build-arg mangler" && exit 1) \
    && curl -fSL -H "Authorization: Bearer $GITHUB_TOKEN" \
       -H "Accept: application/vnd.github.raw" \
       -o bible.db \
       https://api.github.com/repos/tobiashellerslien/bible.db/contents/bible.db?ref=main \
    && [ -s bible.db ] || (echo "bible.db nedlasting feilet" && exit 1)

COPY . .
ENV SERVER_MODE=production
EXPOSE 8421
CMD ["python", "server.py"]
