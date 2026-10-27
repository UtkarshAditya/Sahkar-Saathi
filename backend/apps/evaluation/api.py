from ninja import Router
from ninja.security import django_auth

from config.errors import ApiError, ErrorOut

from .sample import sample_summary
from .schemas import EvalSummaryOut
from .summary import real_summary

# Staff only: Django session login (the same one as /admin/), then an is_staff check.
router = Router(auth=django_auth)


@router.get(
    "/latest",
    response={200: EvalSummaryOut, 401: ErrorOut, 403: ErrorOut},
    summary="Latest evaluation run (staff only)",
)
def latest(request):
    """Hit rate, faithfulness, correct refusals, failed questions and recent runs.

    Log in at /admin/ first; the browser then sends the session cookie. Returns sample
    numbers (``is_sample: true``) until the eval runner saves real runs.
    """
    # The docstring above is the frozen OpenAPI description: do not reword it.
    if not request.auth.is_staff:
        raise ApiError(403, "staff_only", "This page is for staff only.")
    return real_summary() or sample_summary()
