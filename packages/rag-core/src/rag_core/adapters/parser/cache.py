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

    async def store_file(self, parser_input: ParserInput, parsing_config_hash: str) -> str:
        if parser_input.content is None:
            raise ValueError("Parser cache requires file content.")

        content_hash = hashlib.sha256(parser_input.content).hexdigest()

        meta: dict[str, Any] = {
            "content_hash": content_hash,
            "hash_algorithm": "sha256",
            "filename": parser_input.filename,
            "content_type": parser_input.content_type,
            "metadata": parser_input.metadata,
            "extension": self._extension(parser_input.filename),
        }
        await self._client.upload_file(
            self._meta_key(content_hash, parsing_config_hash),
            json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
        )

        return content_hash

    async def get_result(
        self,
        content_hash: str,
        parsing_config_hash: str,
    ) -> dict[str, Any] | None:
        key = self._result_key(content_hash, parsing_config_hash)
        if not await self._client.file_exists(key):
            return None

        data = await self._client.download_file(key)
        return json.loads(data.decode("utf-8"))

    async def store_result(
        self,
        content_hash: str,
        parsing_config_hash: str,
        result: dict[str, Any],
        *,
        provider: str,
        parse_duration_sec: float | None = None,
    ) -> None:
        key = self._result_key(content_hash, parsing_config_hash)
        await self._client.upload_file(
            key,
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
        )
        meta_updates: dict[str, Any] = {"converted_at": datetime.now(UTC).isoformat()}
        if parse_duration_sec is not None:
            meta_updates["parse_durations"] = {provider: parse_duration_sec}
        await self._update_meta(content_hash, parsing_config_hash, meta_updates)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _meta_key(self, content_hash: str, parsing_config_hash: str) -> str:
        return f"{self._prefix}/{content_hash}/{parsing_config_hash}/meta.json"

    def _result_key(self, content_hash: str, parsing_config_hash: str) -> str:
        return f"{self._prefix}/{content_hash}/{parsing_config_hash}/parsed_data.json"

    async def _update_meta(self, content_hash: str, parsing_config_hash: str, values: dict[str, Any]) -> None:
        key = self._meta_key(content_hash, parsing_config_hash)
        if not await self._client.file_exists(key):
            return

        data = await self._client.download_file(key)
        meta = json.loads(data.decode("utf-8"))

        # Merge dictionary values recursively to prevent overwriting whole sub-dicts (e.g. parse_durations)
        for k, v in values.items():
            if isinstance(v, dict) and k in meta and isinstance(meta[k], dict):
                meta[k].update(v)
            else:
                meta[k] = v

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
