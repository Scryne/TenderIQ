"""Worker task testleri (broker gerektirmez — doğrudan çağrı)."""

from __future__ import annotations

from tenderiq_worker.tasks.system import ping


def test_ping_returns_pong() -> None:
    assert ping() == "pong"
