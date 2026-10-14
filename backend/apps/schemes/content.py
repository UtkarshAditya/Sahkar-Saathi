from functools import cache

import yaml
from django.conf import settings

from .schemas import SchemeDetailOut, SchemesFile


@cache
def load_schemes() -> dict[str, SchemeDetailOut]:
    """Read and validate data/schemes.yaml once per process. Raises on invalid content,
    which the test suite and CI catch before a deploy."""
    path = settings.CONTENT_DIR / "schemes.yaml"
    with path.open(encoding="utf-8") as f:
        content = SchemesFile.model_validate(yaml.safe_load(f))
    return {scheme.slug: scheme for scheme in content.schemes}
