from functools import cache

import yaml
from django.conf import settings

from .schemas import LessonsOut


@cache
def load_lessons(language: str) -> LessonsOut:
    """Lessons in ``language`` (data/lessons.<code>.yaml), falling back to English
    (data/lessons.yaml). Validated once per process; invalid content raises."""
    translated = settings.CONTENT_DIR / f"lessons.{language}.yaml"
    path = translated if translated.exists() else settings.CONTENT_DIR / "lessons.yaml"
    with path.open(encoding="utf-8") as f:
        return LessonsOut.model_validate(yaml.safe_load(f))
