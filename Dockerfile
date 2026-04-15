FROM python:3.12-slim

WORKDIR /app

COPY bible_versions/ ./bible_versions/
COPY index.html ./
COPY server.py ./

ENV HOST=0.0.0.0
ENV PORT=8421

EXPOSE 8421

CMD ["python", "server.py"]
