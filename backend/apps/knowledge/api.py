from ninja import Query, Router

from config.errors import ApiError, ErrorOut

from .models import Document
from .schemas import DocType, DocumentOut

router = Router()


@router.get("", response=list[DocumentOut], summary="Knowledge-base documents")
async def list_documents(
    request,
    state: str | None = Query(None, description='A state code or "central".'),
    doc_type: DocType | None = Query(None, alias="type", description="Document type."),
    language: str | None = Query(None),
    include_retired: bool = Query(False, description="Also return retired versions."),
):
    """The public documents the assistant searches, for the Law library page."""
    queryset = Document.objects.all()
    if state:
        queryset = queryset.filter(state=state.upper() if state != "central" else state)
    if doc_type:
        queryset = queryset.filter(doc_type=doc_type)
    if language:
        queryset = queryset.filter(language=language)
    if not include_retired:
        queryset = queryset.filter(status=Document.Status.ACTIVE)
    return [doc async for doc in queryset]


@router.get("/{document_id}", response={200: DocumentOut, 404: ErrorOut}, summary="One document")
async def get_document(request, document_id: str):
    try:
        return await Document.objects.aget(pk=document_id)
    except Document.DoesNotExist as exc:
        raise ApiError(404, "document_not_found", "That document was not found.") from exc
