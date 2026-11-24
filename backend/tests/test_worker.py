"""Tests of the worker decision logic with fake dependencies."""
import pytest
from sqlalchemy.exc import OperationalError

from workers.transaction_worker import DEAD_LETTERED, PROCESSED, handle_record


async def _no_sleep(_):
    return None


def make_dlq():
    sent = []

    async def send_dlq(value, exc):
        sent.append((value, str(exc)))

    return sent, send_dlq


class TestHandleRecord:
    async def test_success(self):
        sent, send_dlq = make_dlq()

        async def process(v):
            return None

        assert await handle_record({"a": 1}, process=process, send_dlq=send_dlq, sleep=_no_sleep) == PROCESSED
        assert sent == []

    async def test_malformed_message_goes_to_dlq_without_retry(self):
        sent, send_dlq = make_dlq()
        calls = {"n": 0}

        async def process(v):
            calls["n"] += 1
            raise ValueError("no transaction_db_id")

        assert await handle_record({}, process=process, send_dlq=send_dlq, sleep=_no_sleep) == DEAD_LETTERED
        assert calls["n"] == 1
        assert len(sent) == 1

    async def test_permanent_error_retried_then_dead_lettered(self):
        sent, send_dlq = make_dlq()
        calls = {"n": 0}

        async def process(v):
            calls["n"] += 1
            raise RuntimeError("bug")

        result = await handle_record({"x": 1}, process=process, send_dlq=send_dlq, max_attempts=3, sleep=_no_sleep)
        assert result == DEAD_LETTERED
        assert calls["n"] == 3
        assert len(sent) == 1

    async def test_transient_error_is_retried_until_it_works(self):
        sent, send_dlq = make_dlq()
        calls = {"n": 0}

        async def process(v):
            calls["n"] += 1
            if calls["n"] <= 10:
                raise OperationalError("SELECT 1", {}, Exception("connection refused"))

        result = await handle_record({"x": 1}, process=process, send_dlq=send_dlq, max_attempts=3, sleep=_no_sleep)
        assert result == PROCESSED
        assert calls["n"] == 11  # far more than max_attempts: outage does not dead-letter good messages
        assert sent == []

    async def test_dlq_failure_is_raised_so_offset_is_not_committed(self):
        async def process(v):
            raise ValueError("bad")

        async def broken_dlq(value, exc):
            raise ConnectionError("broker down")

        with pytest.raises(ConnectionError):
            await handle_record({}, process=process, send_dlq=broken_dlq, sleep=_no_sleep)
