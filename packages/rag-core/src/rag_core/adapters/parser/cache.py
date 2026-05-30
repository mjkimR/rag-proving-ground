import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app_file_storage import FileStorageClient

from rag_core.adapters.parser.interface import ParserInput


class ParserCache:
    """FileStorageClient-backed cache for parser inputs and provider results."""

    _DEFAULT_PREFIX = "parser_cache"

    def __init__(self, client: FileStorageClient, *, prefix: str | None = None) -> None:
        self._client = client
        self._prefix = prefix or self._DEFAULT_PREFIX

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def store_file(self, parser_input: ParserInput) -> str:
        if parser_input.content is None:
            raise ValueError("Parser cache requires file content.")

        md5_hash = hashlib.md5(parser_input.content).hexdigest()

        meta: dict[str, Any] = {
            "md5_hash": md5_hash,
            "filename": parser_input.filename,
            "content_type": parser_input.content_type,
            "metadata": parser_input.metadata,
            "extension": self._extension(parser_input.filename),
        }
        await self._client.upload_file(
            self._meta_key(md5_hash),
            json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
        )

        file_key = f"{self._prefix}/{md5_hash}/{self._filename(parser_input.filename)}"
        await self._client.upload_file(file_key, parser_input.content)

        return md5_hash

    async def get_result(
        self,
        md5_hash: str,
        provider: str,
        *,
        schema_version: str | None = None,
    ) -> dict[str, Any] | None:
        key = self._result_key(md5_hash, provider, schema_version=schema_version)
        if not await self._client.file_exists(key):
            return None

        data = await self._client.download_file(key)
        return json.loads(data.decode("utf-8"))

    async def store_result(
        self,
        md5_hash: str,
        provider: str,
        result: dict[str, Any],
        *,
        schema_version: str | None = None,
    ) -> None:
        key = self._result_key(md5_hash, provider, schema_version=schema_version)
        await self._client.upload_file(
            key,
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
        )
        await self._update_meta(md5_hash, {"converted_at": datetime.now(UTC).isoformat()})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _meta_key(self, md5_hash: str) -> str:
        return f"{self._prefix}/{md5_hash}/meta.json"

    def _result_key(self, md5_hash: str, provider: str, *, schema_version: str | None = None) -> str:
        name = provider
        if schema_version:
            name = f"{provider}-{self._safe_filename_part(schema_version)}"
        return f"{self._prefix}/{md5_hash}/{name}.json"

    async def _update_meta(self, md5_hash: str, values: dict[str, Any]) -> None:
        key = self._meta_key(md5_hash)
        if not await self._client.file_exists(key):
            return

        data = await self._client.download_file(key)
        meta = json.loads(data.decode("utf-8"))
        meta.update(values)
        await self._client.upload_file(
            key,
            json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
        )

    def _extension(self, filename: str | None) -> str:
        if not filename:
            return ""
        return Path(filename).suffix

    def _filename(self, filename: str | None) -> str:
        if not filename:
            return "original"
        return Path(filename).name

    def _safe_filename_part(self, value: str) -> str:
        return "".join(character if character.isalnum() or character in "._-" else "_" for character in value)
