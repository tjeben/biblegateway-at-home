FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir google-genai
COPY . .
ENV SERVER_MODE=production
EXPOSE 8421
CMD ["python", "server.py"]
