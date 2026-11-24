"""Prometheus metrics shared by the API, the outbox publisher and the worker."""
from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total", "HTTP requests", ["method", "route", "status_code"]
)
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
TRANSACTIONS_INGESTED_TOTAL = Counter(
    "transactions_ingested_total", "Transactions accepted by the API", ["mode"]
)

DB_POOL_SIZE = Gauge("db_pool_size", "Configured size of the database pool")
DB_POOL_CHECKED_OUT = Gauge("db_pool_checked_out", "Connections currently in use")

OUTBOX_PENDING = Gauge("outbox_pending_events", "Outbox rows waiting for publication")
OUTBOX_PUBLISHED_TOTAL = Counter("outbox_published_total", "Outbox messages published")
OUTBOX_PUBLISH_FAILURES_TOTAL = Counter(
    "outbox_publish_failures_total", "Failed publishing attempts"
)
OUTBOX_PUBLISH_DURATION = Histogram(
    "outbox_publish_duration_seconds",
    "Time to publish one outbox message and mark it as published",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

WORKER_PROCESSED_TOTAL = Counter("worker_processed_total", "Messages processed by the worker")
WORKER_FAILURES_TOTAL = Counter("worker_failures_total", "Failed processing attempts")
DLQ_MESSAGES_TOTAL = Counter("dlq_messages_total", "Messages sent to the dead-letter topic")
CONSUMER_LAG_MESSAGES = Gauge("consumer_lag_messages", "Messages not yet read by the worker")
PIPELINE_LAG_SECONDS = Histogram(
    "pipeline_end_to_end_seconds",
    "Time from ingested_at to processed_at",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 30, 60, 120),
)

CIRCUIT_BREAKER_STATE = Gauge(
    "circuit_breaker_state", "0 closed, 1 half-open, 2 open", ["name"]
)
