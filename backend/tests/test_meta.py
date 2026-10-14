def test_languages_include_the_regional_language(client):
    body = client.get("/api/v1/meta/languages").json()
    assert [lang["code"] for lang in body] == ["en", "hi", "ta"]
    assert body[2]["label"] == "தமிழ்"
    assert body[2]["english_label"] == "Tamil"


def test_states_mark_only_the_covered_state(client):
    body = client.get("/api/v1/meta/states").json()
    assert len(body) == 36
    covered = [s["code"] for s in body if s["covered"]]
    assert covered == ["TN"]


def test_health_reports_vector_store_not_used_with_stubs(client):
    body = client.get("/api/v1/health").json()
    assert body["vector_store"] == "not_used"
    assert body["status"] == "ok"


def test_health_is_degraded_when_vector_store_is_down(client, settings):
    settings.USE_STUBS = False
    settings.QDRANT_URL = "http://127.0.0.1:9"  # nothing listens here
    settings.HEALTH_CHECK_TIMEOUT_SECONDS = 0.2
    body = client.get("/api/v1/health").json()
    assert body["vector_store"] == "unreachable"
    assert body["status"] == "degraded"
