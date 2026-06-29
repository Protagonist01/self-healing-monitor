import time
from fastapi import FastAPI
import uvicorn
from prometheus_client import Gauge, Counter, make_asgi_app

app = FastAPI(title="Leaky Service")
memory_leak_holder = []
SERVICE_NAME = "leaky_service"

MEMORY_GAUGE = Gauge(
    "container_memory_working_set_bytes",
    "Demo memory working set bytes by container.",
    ["container"]
)
REQUEST_COUNTER = Counter(
    "http_requests_total",
    "Demo HTTP requests by service and status.",
    ["service", "status"]
)

app.mount("/metrics", make_asgi_app())

def update_memory_metric():
    MEMORY_GAUGE.labels(container=SERVICE_NAME).set(len(memory_leak_holder) * 5 * 1024 * 1024)

@app.get("/")
def read_root():
    update_memory_metric()
    REQUEST_COUNTER.labels(service=SERVICE_NAME, status="200").inc()
    return {"status": "ok", "leaked_blocks": len(memory_leak_holder)}

@app.get("/leak")
def trigger_leak():
    # Append 5MB of random data to memory
    global memory_leak_holder
    large_block = "X" * (5 * 1024 * 1024)
    memory_leak_holder.append(large_block)
    update_memory_metric()
    REQUEST_COUNTER.labels(service=SERVICE_NAME, status="200").inc()
    return {"message": "Leaked 5MB", "total_blocks": len(memory_leak_holder)}

@app.get("/health")
def health():
    update_memory_metric()
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
