import json

import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _db_and_clean_cache(db):
    """Every test may use the database, and starts with empty rate-limit counters."""
    cache.clear()
    yield
    cache.clear()


def post_json(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")
