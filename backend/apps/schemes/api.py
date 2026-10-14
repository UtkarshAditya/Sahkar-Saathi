from ninja import Query, Router

from config.errors import ApiError, ErrorOut

from .content import load_schemes
from .schemas import SchemeCategory, SchemeDetailOut, SchemeOut

router = Router()


@router.get("", response=list[SchemeOut], summary="Scheme cards")
def list_schemes(request, category: SchemeCategory | None = Query(None)):
    """Structured scheme cards with source and date, for the Schemes page."""
    schemes = load_schemes().values()
    return [
        SchemeOut(**s.model_dump(exclude={"facts"}))
        for s in schemes
        if category is None or s.category == category
    ]


@router.get("/{slug}", response={200: SchemeDetailOut, 404: ErrorOut}, summary="One scheme")
def get_scheme(request, slug: str):
    """One scheme with its guide facts. ``pmfby`` powers the Crop insurance guide."""
    scheme = load_schemes().get(slug)
    if scheme is None:
        raise ApiError(404, "scheme_not_found", "That scheme was not found.")
    return scheme
