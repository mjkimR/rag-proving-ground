import json
from pathlib import Path

import pytest
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


@pytest.fixture(
    params=get_datasets_parsed_paths("docling") or [None],
    ids=lambda p: p.parent.parent.parent.name if p else "no_dataset",
)
def docling_dataset_document(request) -> ParsedDocument:
    path = request.param
    if path is None:
        pytest.skip("No parsed dataset files found in datasets/pdfs for docling")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return ParsedDocument.model_validate(data)
