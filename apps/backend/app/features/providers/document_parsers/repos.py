from app.features.providers.document_parsers.models import DocumentParser
from app.features.providers.document_parsers.schemas import DocumentParserCreate, DocumentParserPatch, DocumentParserPut
from app_layer_base.base.repos.base import BaseRepository


class DocumentParserRepository(
    BaseRepository[DocumentParser, DocumentParserCreate, DocumentParserPut, DocumentParserPatch]
):
    model = DocumentParser
