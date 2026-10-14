import pytest
from django.core.management import call_command

URL = "/api/v1/documents"


@pytest.fixture(autouse=True)
def sample_documents(db):
    call_command("loaddata", "sample_documents", verbosity=0)


def test_lists_active_documents_only_by_default(client):
    body = client.get(URL).json()
    assert len(body) == 8
    assert all(d["status"] == "active" for d in body)
    assert all(d["source_url"] is None for d in body), "no unverified links"


def test_include_retired(client):
    body = client.get(f"{URL}?include_retired=true").json()
    assert len(body) == 9


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("state=TN", {"doc-tn-act", "doc-tn-rules"}),
        ("state=tn", {"doc-tn-act", "doc-tn-rules"}),
        ("language=ta", {"doc-tn-rules"}),
        ("type=model-bylaws", {"doc-model-bylaws-en", "doc-model-bylaws-hi"}),
        ("state=central&type=rules", {"doc-mscs-rules"}),
    ],
)
def test_filters(client, query, expected):
    assert {d["id"] for d in client.get(f"{URL}?{query}").json()} == expected


def test_unknown_type_is_422(client):
    res = client.get(f"{URL}?type=novel")
    assert res.status_code == 422
    assert res.json()["code"] == "validation_error"


def test_get_one_document(client):
    body = client.get(f"{URL}/doc-tn-act").json()
    assert body["title"] == "Tamil Nadu Co-operative Societies Act, 1983"
    assert body["published_date"] == "2024-03-01"


def test_unknown_document_is_404(client):
    res = client.get(f"{URL}/nope")
    assert res.status_code == 404
    assert res.json()["code"] == "document_not_found"
