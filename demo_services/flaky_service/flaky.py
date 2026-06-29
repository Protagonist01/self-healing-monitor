import random
from fastapi import FastAPI, Response, status
import uvicorn
from prometheus_client import Counter, make_asgi_app

app = FastAPI(title="Flaky Service")
error_rate = 0.0  # 0% to 1.0 (100%) error rate
SERVICE_NAME = "flaky_service"
REQUEST_COUNTER = Counter(
    "http_requests_total",
    "Demo HTTP requests by service and status.",
    ["service", "status"]
)

app.mount("/metrics", make_asgi_app())

@app.get("/")
def read_root(response: Response):
    global error_rate
    if random.random() < error_rate:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        REQUEST_COUNTER.labels(service=SERVICE_NAME, status="500").inc()
        return {"status": "error", "message": "Internal Server Error"}
    REQUEST_COUNTER.labels(service=SERVICE_NAME, status="200").inc()
    return {"status": "ok"}

@app.get("/toggle_error")
def toggle_error(rate: float = 0.5):
    global error_rate
    error_rate = rate
    REQUEST_COUNTER.labels(service=SERVICE_NAME, status="200").inc()
    return {"message": f"Error rate set to {rate * 100}%"}

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081)
