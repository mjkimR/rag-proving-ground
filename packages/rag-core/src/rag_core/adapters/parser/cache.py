import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rag_core.adapters.parser.interface import ParserInput


class ParserCache:
    """File-backed cache for parser inputs and provider results."""

    def __init__(self, cache_dir: Path | str | None = None) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else self._default_cache_dir()

    def store_file(self, parser_input: ParserInput) -> str:
        if parser_input.content is None:
            raise ValueError("Parser cache requires file content.")

        md5_hash = hashlib.md5(parser_input.content).hexdigest()
        entry_dir = self.cache_dir / md5_hash
        entry_dir.mkdir(parents=True, exist_ok=True)

        metadata_path = entry_dir / "meta.json"
        metadata_path.write_text(
            json.dumps(
                {
                    "md5_hash": md5_hash,
                    "filename": parser_input.filename,
                    "content_type": parser_input.content_type,
                    "metadata": parser_input.metadata,
                    "extension": self._extension(parser_input.filename),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        file_path = entry_dir / self._filename(parser_input.filename)
        file_path.write_bytes(parser_input.content)
        return md5_hash

    def get_result(self, md5_hash: str, provider: str, *, schema_version: str | None = None) -> dict[str, Any] | None:
        result_path = self._result_path(md5_hash, provider, schema_version=schema_version)
        if not result_path.exists():
            return None

        return json.loads(result_path.read_text(encoding="utf-8"))

    def store_result(
        self,
        md5_hash: str,
        provider: str,
        result: dict[str, Any],
        *,
        schema_version: str | None = None,
    ) -> None:
        result_path = self._result_path(md5_hash, provider, schema_version=schema_version)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = result_path.with_suffix(f"{result_path.suffix}.tmp")
        temp_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        shutil.move(temp_path, result_path)
        self._update_meta(md5_hash, {"converted_at": datetime.now(UTC).isoformat()})

    def _result_path(self, md5_hash: str, provider: str, *, schema_version: str | None = None) -> Path:
        name = provider
        if schema_version:
            name = f"{provider}-{self._safe_filename_part(schema_version)}"
        return self.cache_dir / md5_hash / f"{name}.json"

    def _default_cache_dir(self) -> Path:
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / "pyproject.toml").exists():
                return parent / ".integrations" / "parser_cache"
        return Path.cwd() / ".integrations" / "parser_cache"

    def _extension(self, filename: str | None) -> str:
        if not filename:
            return ""
        return Path(filename).suffix

    def _filename(self, filename: str | None) -> str:
        if not filename:
            return "original"
        return Path(filename).name

    def _update_meta(self, md5_hash: str, values: dict[str, Any]) -> None:
        metadata_path = self.cache_dir / md5_hash / "meta.json"
        if not metadata_path.exists():
            return

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata.update(values)
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _safe_filename_part(self, value: str) -> str:
        return "".join(character if character.isalnum() or character in "._-" else "_" for character in value)
