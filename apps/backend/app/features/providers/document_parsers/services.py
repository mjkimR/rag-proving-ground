from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from app_layer_base.base.repos.base import PrimaryKeyType
from app_layer_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
    BaseUpdateServiceMixin,
)
from app_layer_base.base.services.hooks import CreateHook, Operation, UpdateHook
from fastapi import Depends
from pydantic import BaseModel

from app.features.providers.document_parsers.models import DocumentParser
from app.features.providers.document_parsers.repos import DocumentParserRepository
from app.features.providers.document_parsers.schemas import DocumentParserCreate, DocumentParserPatch, DocumentParserPut


class DocumentParserContextKwargs(BaseContextKwargs):
    pass


class DocumentParserDefaultFlagHook(
    CreateHook[DocumentParser, DocumentParserContextKwargs],
    UpdateHook[DocumentParser, DocumentParserContextKwargs],
):
    """Keeps at most one default parser: writing ``is_default=True`` clears the previous default first."""

    def __init__(self, repo: DocumentParserRepository):
        self.repo = repo

    @asynccontextmanager
    async def create_context(self, op: Operation[DocumentParserContextKwargs], data: BaseModel) -> AsyncIterator[None]:
        if getattr(data, "is_default", False):
            await self.repo.clear_default(op.session)
        yield

    @asynccontextmanager
    async def update_context(
        self,
        op: Operation[DocumentParserContextKwargs],
        pk: PrimaryKeyType,
        data: BaseModel,
        partial: bool = True,
    ) -> AsyncIterator[None]:
        if getattr(data, "is_default", None):
            await self.repo.clear_default(op.session)
        yield


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
        self.hooks = (DocumentParserDefaultFlagHook(repo),)

    @property
    def repo(self) -> DocumentParserRepository:
        return self._repo

    @property
    def context_model(self):
        return DocumentParserContextKwargs
