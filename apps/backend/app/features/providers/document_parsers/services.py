from typing import Annotated

from app.features.providers.document_parsers.models import DocumentParser
from app.features.providers.document_parsers.repos import DocumentParserRepository
from app.features.providers.document_parsers.schemas import DocumentParserCreate, DocumentParserPatch, DocumentParserPut
from app_layer_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
    BaseUpdateServiceMixin,
)
from fastapi import Depends


class DocumentParserContextKwargs(BaseContextKwargs):
    pass


class DocumentParserService(
    BaseCreateServiceMixin[DocumentParserRepository, DocumentParser, DocumentParserCreate, DocumentParserContextKwargs],
    BaseGetMultiServiceMixin[DocumentParserRepository, DocumentParser, DocumentParserContextKwargs],
    BaseGetServiceMixin[DocumentParserRepository, DocumentParser, DocumentParserContextKwargs],
    BaseUpdateServiceMixin[
        DocumentParserRepository, DocumentParser, DocumentParserPut, DocumentParserPatch, DocumentParserContextKwargs
    ],
    BaseDeleteServiceMixin[DocumentParserRepository, DocumentParser, DocumentParserContextKwargs],
):
    def __init__(self, repo: Annotated[DocumentParserRepository, Depends()]):
        self._repo = repo

    @property
    def repo(self) -> DocumentParserRepository:
        return self._repo

    @property
    def context_model(self):
        return DocumentParserContextKwargs
