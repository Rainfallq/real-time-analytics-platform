"""Retry with backoff and a small circuit breaker.

Used by the outbox publisher (publishing to the broker) and by the worker
(processing and dead-letter publishing).
"""
import asyncio
import logging
import random
import time
from typing import Awaitable, Callable, Tuple, Type, TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")


class CircuitOpenError(RuntimeError):
    """Raised when a call is rejected because the circuit breaker is open."""


class CircuitBreaker:
    """Closed -> open after N failures in a row -> half-open after a timeout.

    In the half-open state one trial call is allowed. If it succeeds the breaker
    closes again, if it fails the breaker opens for another timeout period.
    """

    CLOSED, HALF_OPEN, OPEN = 0, 1, 2

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        reset_timeout: float = 15.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._clock = clock
        self._failures = 0
        self._opened_at = 0.0
        self._state = self.CLOSED
        self._publish_state()

    @property
    def state(self) -> int:
        if self._state == self.OPEN and self._clock() - self._opened_at >= self.reset_timeout:
            self._set_state(self.HALF_OPEN)
        return self._state

    def _set_state(self, state: int) -> None:
        if state != self._state:
            logger.warning("Circuit breaker %s: %s -> %s", self.name, self._state, state)
        self._state = state
        self._publish_state()

    def _publish_state(self) -> None:
        try:
            from app.core.metrics import CIRCUIT_BREAKER_STATE
            CIRCUIT_BREAKER_STATE.labels(self.name).set(self._state)
        except Exception:  # metrics must never break the logic
            pass

    def allow(self) -> bool:
        return self.state != self.OPEN

    def record_success(self) -> None:
        self._failures = 0
        self._set_state(self.CLOSED)

    def record_failure(self) -> None:
        self._failures += 1
        if self._state == self.HALF_OPEN or self._failures >= self.failure_threshold:
            self._opened_at = self._clock()
            self._set_state(self.OPEN)

    async def call(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        if not self.allow():
            raise CircuitOpenError(f"circuit '{self.name}' is open")
        try:
            result = await func(*args, **kwargs)
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result


async def retry_async(
    func: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.2,
    max_delay: float = 5.0,
    jitter: bool = True,
    retry_on: Tuple[Type[BaseException], ...] = (Exception,),
    no_retry_on: Tuple[Type[BaseException], ...] = (CircuitOpenError,),
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    """Call func until it succeeds or the attempts are used.

    The delay doubles after every failure (exponential backoff) and a random
    part is added, so many clients do not retry at the same moment.
    """
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await func()
        except no_retry_on:
            raise
        except retry_on as exc:
            last_exc = exc
            if attempt == attempts:
                break
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            if jitter:
                delay = random.uniform(delay / 2, delay)
            logger.warning("Attempt %d/%d failed: %s. Retry in %.2fs", attempt, attempts, exc, delay)
            await sleep(delay)
    assert last_exc is not None
    raise last_exc
