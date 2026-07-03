"""API test fixture'ları."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from tenderiq_api.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    """FastAPI test istemcisi."""
    with TestClient(create_app()) as test_client:
        yield test_client
