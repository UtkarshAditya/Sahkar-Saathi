"""The frozen contract: openapi.json must match the code, and cover every endpoint."""

import json
from pathlib import Path

from django.conf import settings
from django.core.management import call_command

COMMITTED = Path(settings.BASE_DIR) / "openapi.json"

EXPECTED_OPERATIONS = {
    ("get", "/api/v1/health"),
    ("get", "/api/v1/meta/languages"),
    ("get", "/api/v1/meta/states"),
    ("post", "/api/v1/chat/ask"),
    ("post", "/api/v1/speech/transcribe"),
    ("post", "/api/v1/speech/synthesize"),
    ("post", "/api/v1/feedback"),
    ("get", "/api/v1/grievance/categories"),
    ("post", "/api/v1/grievance/guide"),
    ("get", "/api/v1/schemes"),
    ("get", "/api/v1/schemes/{slug}"),
    ("get", "/api/v1/lessons"),
    ("get", "/api/v1/documents"),
    ("get", "/api/v1/documents/{document_id}"),
    ("get", "/api/v1/eval/latest"),
}


def _export(tmp_path) -> dict:
    out = tmp_path / "openapi.json"
    call_command("export_openapi_schema", api="config.api.api", output=str(out), indent=2)
    return json.loads(out.read_text(encoding="utf-8"))


def test_committed_openapi_json_is_up_to_date(tmp_path):
    exported = _export(tmp_path)
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    assert exported == committed, (
        "openapi.json is out of date. Run: python manage.py export_openapi_schema "
        "--api config.api.api --output openapi.json --indent 2"
    )


def test_contract_covers_every_endpoint(tmp_path):
    paths = _export(tmp_path)["paths"]
    operations = {(method, path) for path, ops in paths.items() for method in ops}
    assert operations == EXPECTED_OPERATIONS


def test_every_error_response_uses_the_error_shape(tmp_path):
    schema = _export(tmp_path)
    for path, ops in schema["paths"].items():
        for method, op in ops.items():
            for status, response in op["responses"].items():
                if int(status) >= 400:
                    ref = response["content"]["application/json"]["schema"]["$ref"]
                    assert ref.endswith("/ErrorOut"), f"{method.upper()} {path} {status}"
