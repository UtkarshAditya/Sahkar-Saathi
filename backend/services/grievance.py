"""Grievance guide backed by data/forums.yaml (role C). Plain Python, no Django imports.

Implements GrievanceGuide from services/types.py. It never files anything and never invents
a contact detail, deadline or fee:

- The forum, its helpline numbers and website come only from forums.yaml, with the source
  and date the file records. Where the file has no route for a category, the guide says so
  and points to the configured general contact instead.
- Steps and the documents checklist are general advice without time limits or amounts.
- The draft is a template with [placeholders] for the member's own details.

Categories are found by keywords in the member's own words. English words are used, plus
a few machine-written Hindi and Tamil ones that need review by a fluent speaker.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .types import Contact, GrievanceCategory, GrievanceResult

FORUMS_FILE = Path(__file__).parent / "data" / "forums.yaml"
OTHER = "other"

# The forum ids in forums.yaml that serve each category, the first being the main one.
# forums.yaml has routes for crop insurance only; the cooperative categories have none yet.
FORUMS_BY_CATEGORY: dict[str, tuple[str, ...]] = {
    "crop-insurance": ("krph_helpline", "ncip_portal_grievance", "state_agriculture_department"),
}

# (category, keywords). The category whose keywords match most wins; ties go to the first.
# Hindi and Tamil keywords: machine-written, needs review by a fluent speaker.
_CATEGORIES: list[tuple[GrievanceCategory, tuple[str, ...]]] = [
    (
        GrievanceCategory(
            "deposit-refund",
            "Deposit or share money not returned",
            "The society has not refunded a deposit, share capital or dividend.",
        ),
        ("deposit", "refund", "share", "dividend", "money back"),
    ),
    (
        GrievanceCategory(
            "membership",
            "Membership refused or removed",
            "You were refused membership or removed without a proper reason.",
        ),
        ("membership", "expelled", "removed", "refused"),
    ),
    (
        GrievanceCategory(
            "election",
            "Election of the board",
            "Concerns about how a board election was announced or conducted.",
        ),
        ("election", "vote", "board", "director"),
    ),
    (
        GrievanceCategory(
            "records",
            "Accounts or records not shared",
            "You asked to see accounts, audit reports or minutes and were refused.",
        ),
        ("accounts", "audit", "records", "minutes", "balance sheet"),
    ),
    (
        GrievanceCategory(
            "loan",
            "Loan or dues dispute",
            "Disagreement about a loan, interest charged or dues recovered.",
        ),
        ("loan", "interest", "dues", "recovery", "kcc"),
    ),
    (
        GrievanceCategory(
            "crop-insurance",
            "Crop insurance claim",
            "A PMFBY claim was delayed, rejected or wrongly calculated.",
        ),
        ("crop", "insurance", "pmfby", "bima", "fasal", "बीमा", "फसल", "காப்பீடு", "பயிர்"),
    ),
    (
        GrievanceCategory(
            OTHER,
            "Something else",
            "A problem that does not fit the other categories.",
        ),
        (),
    ),
]
_BY_ID = {category.id: category for category, _ in _CATEGORIES}

_CHECKLIST = [
    "Proof of membership or enrolment (pass book, share certificate or policy)",
    "Copy of your earlier letter or complaint, with its date",
    "Receipts, statements or notices related to the problem",
    "Any reply received",
    "Identity proof (show only, do not leave originals)",
]


@dataclass(frozen=True)
class Forum:
    id: str
    name: str
    description: str
    source_url: str
    as_of: str
    contact_number: str | None = None
    alternative_number: str | None = None
    whatsapp_bot: str | None = None
    website: str | None = None


def load_forums(path: Path = FORUMS_FILE) -> dict[str, Forum]:
    """Read and validate forums.yaml. Every forum needs a source and a date; raises
    ValueError otherwise, so unverified contact details can never be served."""
    with path.open(encoding="utf-8") as handle:
        content = yaml.safe_load(handle) or {}
    forums: dict[str, Forum] = {}
    for item in content.get("forums") or []:
        for required in ("id", "name", "description", "source_url", "as_of"):
            if not item.get(required):
                raise ValueError(f"forums.yaml: forum {item.get('id', '?')!r} needs {required!r}")
        forum = Forum(
            id=str(item["id"]),
            name=str(item["name"]),
            description=str(item["description"]),
            source_url=str(item["source_url"]),
            as_of=str(item["as_of"]),
            contact_number=_text(item.get("contact_number")),
            alternative_number=_text(item.get("alternative_number")),
            whatsapp_bot=_text(item.get("whatsapp_bot")),
            website=_text(item.get("website")),
        )
        if forum.id in forums:
            raise ValueError(f"forums.yaml: forum id {forum.id!r} appears twice")
        forums[forum.id] = forum
    return forums


def _text(value: object) -> str | None:
    return str(value).strip() or None if value is not None else None


def _contact_sentence(forum: Forum) -> str:
    """The contact details the file records for this forum, and only those."""
    parts = []
    if forum.contact_number:
        parts.append(f"Helpline: {forum.contact_number}")
    if forum.alternative_number:
        parts.append(f"alternative helpline: {forum.alternative_number}")
    if forum.whatsapp_bot:
        parts.append(f"WhatsApp: {forum.whatsapp_bot}")
    if forum.website:
        parts.append(f"website: {forum.website}")
    if not parts:
        return "No helpline number or website is recorded for this forum."
    sentence = "; ".join(parts)
    return sentence[0].upper() + sentence[1:] + "."


class ForumsGrievanceGuide:
    """Keyword category detection, forum details from forums.yaml, a template draft."""

    def __init__(self, forums: dict[str, Forum], contact: Contact) -> None:
        self.forums = forums
        self.contact = contact  # the general contact, for categories with no recorded forum
        for category_id, forum_ids in FORUMS_BY_CATEGORY.items():
            missing = [f for f in forum_ids if f not in forums]
            if missing:
                raise ValueError(f"forums.yaml has no forum {missing} (used by {category_id!r})")

    def categories(self) -> list[GrievanceCategory]:
        return [category for category, _ in _CATEGORIES]

    async def guide(
        self,
        description: str,
        *,
        state: str | None,
        language: str,
        category_hint: str | None = None,
    ) -> GrievanceResult:
        category = self._detect(description, category_hint)
        forums = [self.forums[f] for f in FORUMS_BY_CATEGORY.get(category.id, ())]
        state_text = state or "[Your state]"
        body = description.strip() or "[Describe the problem in your own words]"
        if forums:
            return self._with_forums(category, forums, body, state_text)
        return self._without_forums(category, body, state_text)

    # --- Category detection -------------------------------------------------------------

    @staticmethod
    def _detect(description: str, hint: str | None) -> GrievanceCategory:
        if hint in _BY_ID:  # an unknown hint is ignored; the API rejects it before this
            return _BY_ID[hint]
        text = description.casefold()
        best, best_hits = _BY_ID[OTHER], 0
        for category, keywords in _CATEGORIES:
            hits = sum(keyword in text for keyword in keywords)
            if hits > best_hits:
                best, best_hits = category, hits
        return best

    # --- A category with forums in forums.yaml ------------------------------------------

    def _with_forums(
        self, category: GrievanceCategory, forums: list[Forum], body: str, state_text: str
    ) -> GrievanceResult:
        main, *others = forums
        note = (
            f"{_contact_sentence(main)} Source: {main.source_url} (as of {main.as_of}). "
            "No time limit or fee for this route is recorded in our data."
        )
        steps = [
            "Keep your policy or enrolment details, the date and way you reported the loss, "
            "and any acknowledgement or complaint number.",
            f"Register your grievance with {main.name}. Its details are under Where to complain.",
            *(f"Also available: {other.name}. {other.description}" for other in others),
            "Keep the complaint number you receive and follow up with it.",
        ]
        escalation = others[-1].name if others else main.name
        draft = (
            f"To,\n{escalation}\n{state_text}\n\n"
            f"Subject: Complaint regarding {category.label.lower()}\n\n"
            "Respected Sir/Madam,\n\n"
            "I am a farmer insured under the scheme, from [village/taluk], "
            f"{state_text}, with policy or application number [policy number].\n\n"
            f"{body}\n\n"
            "I reported this on [date] but have not received a resolution. I request you to "
            "look into this matter and take appropriate action.\n\n"
            "Copies of the relevant documents are enclosed.\n\n"
            "Yours faithfully,\n[Your name]\n[Address]\n[Date]"
        )
        return GrievanceResult(
            category=category,
            forum=main.name,
            forum_note=note,
            steps=steps,
            documents_needed=list(_CHECKLIST),
            draft_text=draft,
            is_demo=False,
        )

    # --- A category with no forum in forums.yaml ----------------------------------------

    def _without_forums(
        self, category: GrievanceCategory, body: str, state_text: str
    ) -> GrievanceResult:
        note = (
            "The complaint route for this kind of problem is not recorded in our data yet, "
            f"so no authority, time limit or fee is given. {self.contact.detail}"
        )
        steps = [
            "Write to the secretary or board of your society first, and keep a dated copy.",
            "Wait for a reply for a reasonable period, and note the date if there is no response.",
            "Ask your district cooperative office which authority handles this kind of "
            "complaint. That route, and any time limit or fee, is not available in our data yet.",
            "Attach copies (never originals) of the documents in the checklist.",
            "Keep the acknowledgement or receipt number and follow up if needed.",
        ]
        draft = (
            "To,\n[Name of the authority: confirm with your district cooperative office]\n"
            f"{state_text}\n\n"
            f"Subject: Complaint regarding {category.label.lower()}\n\n"
            "Respected Sir/Madam,\n\n"
            "I am a member of [name of cooperative society], [village/taluk], "
            f"{state_text}, with membership number [membership number].\n\n"
            f"{body}\n\n"
            "I first raised this with the society on [date] but have not received a "
            "resolution. I request you to look into this matter and take appropriate "
            "action.\n\n"
            "Copies of the relevant documents are enclosed.\n\n"
            "Yours faithfully,\n[Your name]\n[Address]\n[Date]"
        )
        return GrievanceResult(
            category=category,
            forum=self.contact.label,
            forum_note=note,
            steps=steps,
            documents_needed=list(_CHECKLIST),
            draft_text=draft,
            is_demo=True,
        )
