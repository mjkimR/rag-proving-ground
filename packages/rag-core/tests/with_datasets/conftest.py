import json
from pathlib import Path

import pytest
from rag_core.adapters.parser import SUPPORTED_PDF_PROVIDERS
from rag_core.parsers.schemas import ParsedDocument


def find_workspace_root() -> Path:
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "justfile").exists():
            return current
        current = current.parent
    raise RuntimeError("Workspace root not found.")


DATASETS_PDFS_DIR = find_workspace_root() / "datasets" / "pdfs"


def get_datasets_parsed_paths(provider: str) -> list[Path]:
    try:
        pdf_dir = DATASETS_PDFS_DIR
        if not pdf_dir.exists():
            return []
        return sorted(list(pdf_dir.glob(f"*/{provider}/*/parsed_data.json")))
    except Exception:
        return []


def load_parsed_document(path: Path | None, provider: str) -> ParsedDocument:
    if path is None:
        pytest.skip(f"No parsed dataset files found in datasets/pdfs for {provider}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return ParsedDocument.model_validate(data)


@pytest.fixture(
    params=get_datasets_parsed_paths("docling") or [None],
    ids=lambda p: p.parent.parent.parent.name if p else "no_dataset",
)
def docling_dataset_document(request) -> ParsedDocument:
    return load_parsed_document(request.param, "docling")


# Extensible general dataset document fixture parameterized across all providers
def _get_all_provider_paths() -> list[tuple[str, Path]]:
    paths = []
    providers = SUPPORTED_PDF_PROVIDERS
    for provider in providers:
        for path in get_datasets_parsed_paths(provider):
            paths.append((provider, path))
    return paths


@pytest.fixture(
    params=_get_all_provider_paths() or [None],
    ids=lambda p: f"{p[0]}:{p[1].parent.parent.parent.name}" if p else "no_dataset",
)
def any_dataset_document(request) -> ParsedDocument:
    if request.param is None:
        pytest.skip("No parsed dataset files found in datasets/pdfs for any provider")
    provider, path = request.param
    return load_parsed_document(path, provider)


@pytest.fixture
def critical_snippets() -> dict[str, list[str]]:
    from with_datasets.constants import CRITICAL_SNIPPETS

    return CRITICAL_SNIPPETS
