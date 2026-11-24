"""Helpers shared by the outbox publisher and the transaction worker."""
import asyncio
import signal


def install_stop_handler(stop: asyncio.Event) -> None:
    """Set the stop event on SIGTERM and SIGINT, so the process can finish the
    current message and exit cleanly (Kubernetes sends SIGTERM)."""
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            # Windows event loops do not support add_signal_handler
            signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop.set))
