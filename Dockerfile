FROM python:3.12-slim
WORKDIR /app
COPY . .
ENV SERVER_MODE=production
EXPOSE 8421
CMD ["python", "server.py"]
