FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY flaky.py .

EXPOSE 8081
CMD ["python", "flaky.py"]
