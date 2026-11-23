# scripts/benchmark.py
import asyncio
import httpx
import time
import statistics
from uuid import uuid4
from datetime import datetime, timezone

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiNmFmYTBkZC1lNjIwLTRiMGYtOTY3ZC1iYmFiMWM3M2IzOWEiLCJleHAiOjE3NzkwMDg1MDAsInR5cGUiOiJhY2Nlc3MifQ.8SP6A774kMTTqIRpsTzn86lYCWKS4P77WStIImehV0U"
async def get_token():
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/api/v1/auth/login", json={
            "email": "amir.sagingaliyev@gmail.com",
            "password": "rainfallontop1"
        })
        assert response.status_code == 200, (
            f"Login failed! Status: {response.status_code}, Body: {response.text}"
        )
        return response.json()["access_token"]

async def single_ingest(client: httpx.AsyncClient, token: str) -> float:
    clean_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "transaction_id": f"txn_{uuid4().hex[:12]}",
        "amount": "150.00",
        "currency": "USD",
        "transaction_type": "PAYMENT",
        "customer_id": str(uuid4()),
        "payment_method": "CARD",
        "transaction_time": clean_time,
    }
    if not hasattr(single_ingest, "checked"):
        print(f"\n[DEBUG] Токен, отправляемый скриптом: Bearer {token[:20]}...{token[-20:]}")
        single_ingest.checked = True
    start = time.perf_counter()
    response = await client.post(
        f"{BASE_URL}/api/v1/transactions/ingest",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert response.status_code == 202, f"Unexpected: {response.status_code}. Details: {response.text}"
    return elapsed_ms



async def run_benchmark(n_requests: int = 100):
    token = await get_token()
    latencies = []

    async with httpx.AsyncClient(timeout=30) as client:
        # Прогрев — первые запросы всегда медленнее
        print("Warming up...")
        for _ in range(5):
            await single_ingest(client, token)

        # Основной тест
        print(f"Running {n_requests} requests...")
        for i in range(n_requests):
            ms = await single_ingest(client, token)
            latencies.append(ms)
            if (i + 1) % 20 == 0:
                print(f"  {i + 1}/{n_requests} done...")

    latencies.sort()
    print(f"\n{'='*40}")
    print(f"Results ({n_requests} requests):")
    print(f"  Min:    {min(latencies):.1f}ms")
    print(f"  Median: {statistics.median(latencies):.1f}ms")
    print(f"  p95:    {latencies[int(len(latencies) * 0.95)]:.1f}ms")
    print(f"  p99:    {latencies[int(len(latencies) * 0.99)]:.1f}ms")
    print(f"  Max:    {max(latencies):.1f}ms")
    print(f"  Mean:   {statistics.mean(latencies):.1f}ms")
    print(f"{'='*40}")

    # Проверка целевых показателей из ТЗ
    p99 = latencies[int(len(latencies) * 0.99)]
    p95 = latencies[int(len(latencies) * 0.95)]
    print(f"\nTargets:")
    print(f"  p95 < 100ms: {'✅' if p95 < 100 else '❌'} ({p95:.1f}ms)")
    print(f"  p99 < 150ms: {'✅' if p99 < 150 else '❌'} ({p99:.1f}ms)")

asyncio.run(run_benchmark(100))