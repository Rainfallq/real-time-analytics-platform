"""Tests of the probes and the metrics endpoint."""


class TestOps:
    async def test_alive(self, client):
        response = await client.get("/alive")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}

    async def test_ready_with_database(self, client):
        response = await client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}

    async def test_metrics_exposes_http_series(self, client, auth_headers):
        await client.get("/health")
        response = await client.get("/metrics")
        assert response.status_code == 200
        assert "http_requests_total" in response.text
        assert "http_request_duration_seconds_bucket" in response.text

    async def test_route_template_is_used_as_label(self, client, auth_headers):
        await client.get("/api/v1/transactions/does-not-exist-1", headers=auth_headers)
        await client.get("/api/v1/transactions/does-not-exist-2", headers=auth_headers)
        text = (await client.get("/metrics")).text
        assert 'route="/api/v1/transactions/{transaction_id}"' in text
        assert "does-not-exist-1" not in text
