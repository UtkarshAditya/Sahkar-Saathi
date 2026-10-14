"""Options for the shared language and state selectors."""

from django.conf import settings
from ninja import Field, Router, Schema

router = Router()

# States and union territories, with short codes. Mirrors src/data/options.ts.
STATES: list[tuple[str, str]] = [
    ("AN", "Andaman and Nicobar Islands"),
    ("AP", "Andhra Pradesh"),
    ("AR", "Arunachal Pradesh"),
    ("AS", "Assam"),
    ("BR", "Bihar"),
    ("CH", "Chandigarh"),
    ("CT", "Chhattisgarh"),
    ("DH", "Dadra and Nagar Haveli and Daman and Diu"),
    ("DL", "Delhi"),
    ("GA", "Goa"),
    ("GJ", "Gujarat"),
    ("HR", "Haryana"),
    ("HP", "Himachal Pradesh"),
    ("JK", "Jammu and Kashmir"),
    ("JH", "Jharkhand"),
    ("KA", "Karnataka"),
    ("KL", "Kerala"),
    ("LA", "Ladakh"),
    ("LD", "Lakshadweep"),
    ("MP", "Madhya Pradesh"),
    ("MH", "Maharashtra"),
    ("MN", "Manipur"),
    ("ML", "Meghalaya"),
    ("MZ", "Mizoram"),
    ("NL", "Nagaland"),
    ("OD", "Odisha"),
    ("PY", "Puducherry"),
    ("PB", "Punjab"),
    ("RJ", "Rajasthan"),
    ("SK", "Sikkim"),
    ("TN", "Tamil Nadu"),
    ("TG", "Telangana"),
    ("TR", "Tripura"),
    ("UP", "Uttar Pradesh"),
    ("UK", "Uttarakhand"),
    ("WB", "West Bengal"),
]
STATE_CODES = {code for code, _ in STATES}


class LanguageOut(Schema):
    code: str = Field(..., description="Short ISO code, e.g. en, hi, ta.")
    label: str = Field(..., description="Name in its own script.")
    english_label: str


class StateOut(Schema):
    code: str
    name: str
    covered: bool = Field(..., description="True if this state's Act is in the knowledge base.")


@router.get("/languages", response=list[LanguageOut], summary="Supported languages")
def languages(request):
    return [
        LanguageOut(code="en", label="English", english_label="English"),
        LanguageOut(code="hi", label="हिन्दी", english_label="Hindi"),
        LanguageOut(
            code=settings.REGIONAL_LANGUAGE_CODE,
            label=settings.REGIONAL_LANGUAGE_LABEL,
            english_label=settings.REGIONAL_LANGUAGE_ENGLISH_NAME,
        ),
    ]


@router.get("/states", response=list[StateOut], summary="States and union territories")
def states(request):
    covered = settings.COVERED_STATE_CODE
    return [StateOut(code=code, name=name, covered=code == covered) for code, name in STATES]
