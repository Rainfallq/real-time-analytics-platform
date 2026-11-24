"""Tests of retry with backoff and the circuit breaker."""
import pytest

from app.core.resilience import CircuitBreaker, CircuitOpenError, retry_async


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


async def _no_sleep(_):
    return None


class TestRetry:
    async def test_succeeds_after_failures(self):
        calls = {"n": 0}

        async def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("boom")
            return "ok"

        assert await retry_async(flaky, attempts=3, sleep=_no_sleep) == "ok"
        assert calls["n"] == 3

    async def test_raises_after_last_attempt(self):
        calls = {"n": 0}

        async def always_fails():
            calls["n"] += 1
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await retry_async(always_fails, attempts=3, sleep=_no_sleep)
        assert calls["n"] == 3

    async def test_delay_doubles_and_is_capped(self):
        delays = []

        async def record(d):
            delays.append(d)

        async def always_fails():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await retry_async(always_fails, attempts=5, base_delay=1, max_delay=3, jitter=False, sleep=record)
        assert delays == [1, 2, 3, 3]

    async def test_open_circuit_is_not_retried(self):
        calls = {"n": 0}

        async def rejected():
            calls["n"] += 1
            raise CircuitOpenError("open")

        with pytest.raises(CircuitOpenError):
            await retry_async(rejected, attempts=5, sleep=_no_sleep)
        assert calls["n"] == 1


class TestCircuitBreaker:
    async def test_opens_after_threshold(self):
        breaker = CircuitBreaker("t1", failure_threshold=3, reset_timeout=10, clock=FakeClock())

        async def fail():
            raise RuntimeError("down")

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await breaker.call(fail)
        assert breaker.state == CircuitBreaker.OPEN
        with pytest.raises(CircuitOpenError):
            await breaker.call(fail)

    async def test_half_open_then_closes_on_success(self):
        clock = FakeClock()
        breaker = CircuitBreaker("t2", failure_threshold=1, reset_timeout=10, clock=clock)

        async def fail():
            raise RuntimeError("down")

        async def ok():
            return "fine"

        with pytest.raises(RuntimeError):
            await breaker.call(fail)
        assert breaker.state == CircuitBreaker.OPEN
        clock.t = 11
        assert breaker.state == CircuitBreaker.HALF_OPEN
        assert await breaker.call(ok) == "fine"
        assert breaker.state == CircuitBreaker.CLOSED

    async def test_half_open_failure_reopens(self):
        clock = FakeClock()
        breaker = CircuitBreaker("t3", failure_threshold=1, reset_timeout=10, clock=clock)

        async def fail():
            raise RuntimeError("down")

        with pytest.raises(RuntimeError):
            await breaker.call(fail)
        clock.t = 11
        with pytest.raises(RuntimeError):
            await breaker.call(fail)
        assert breaker.state == CircuitBreaker.OPEN

    async def test_success_resets_failure_count(self):
        breaker = CircuitBreaker("t4", failure_threshold=3, reset_timeout=10, clock=FakeClock())

        async def fail():
            raise RuntimeError("down")

        async def ok():
            return 1

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(fail)
        await breaker.call(ok)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(fail)
        assert breaker.state == CircuitBreaker.CLOSED
