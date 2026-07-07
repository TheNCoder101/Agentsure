import os
import tempfile
from collections.abc import Iterator

# Must be set before app modules import: signing needs the key, the store
# needs an isolated database.
os.environ.setdefault("SIGNING_KEY", "test-signing-key-not-for-production")
os.environ["VG_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

import pytest
from fastapi.testclient import TestClient

from app.main import app

GROUNDED_SOURCE = (
    "Revenue for the third quarter increased 12% year over year to $4.1M, "
    "driven by enterprise renewals. The board approved a $9M share buyback program."
)


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def api_key(client: TestClient) -> str:
    response = client.post("/keys", json={"email": "dev@example.com"})
    assert response.status_code == 201
    key: str = response.json()["api_key"]
    return key
