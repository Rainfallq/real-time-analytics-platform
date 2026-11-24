"""Pure ASGI middleware that records request counts and latency.

Labels use the route template (for example /api/v1/transactions/{transaction_id})
and not the raw path, so the number of time series stays small.
"""
import time

from starlette.routing import Match

from app.core.metrics import HTTP_REQUEST_DURATION, HTTP_REQUESTS_TOTAL


def _route_template(app, scope) -> str:
    route = scope.get("route")
    path = getattr(route, "path", None)
    if path:
        return path
    for r in getattr(app, "routes", []):
        match, _ = r.matches(scope)
        if match == Match.FULL:
            return getattr(r, "path", "unmatched")
    return "unmatched"


class PrometheusMiddleware:
    def __init__(self, app, router=None, skip_paths: tuple = ("/metrics",)) -> None:
        self.app = app
        self.skip_paths = skip_paths
        self._router_app = router

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] in self.skip_paths:
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status_holder = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.perf_counter() - start
            route = _route_template(self._router_app, scope)
            method = scope.get("method", "GET")
            HTTP_REQUESTS_TOTAL.labels(method, route, str(status_holder["code"])).inc()
            HTTP_REQUEST_DURATION.labels(method, route).observe(duration)
