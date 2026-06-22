from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from app.features.knowledge.synonyms.repos import SynonymMapRepository
from httpx import AsyncClient

from tests.utils import assert_status_code

pytestmark = pytest.mark.real_commit


async def test_synonyms_crud_lifecycle(
    client: AsyncClient,
    make_db: Callable[..., Awaitable[Any]],
) -> None:
    # 1. Create a synonym entry in DB using make_db fixture
    synonym_1 = await make_db(
        SynonymMapRepository,
        keyword="m-rag",
        synonyms=["modular rag", "모듈형 rag"],
        description="Modular RAG architecture abbreviation",
    )
    assert synonym_1.keyword == "m-rag"
    assert synonym_1.synonyms == ["modular rag", "모듈형 rag"]

    # 2. GET all synonyms (listing)
    list_response = await client.get("/api/v1/synonyms")
    assert_status_code(list_response, 200)
    data = list_response.json()
    assert "items" in data
    assert any(item["id"] == str(synonym_1.id) for item in data["items"])

    # 3. POST - Create another synonym map
    post_payload = {
        "keyword": "llm",
        "synonyms": ["large language model", "거대 언어 모델"],
        "description": "Large Language Model description",
    }
    post_response = await client.post("/api/v1/synonyms", json=post_payload)
    assert_status_code(post_response, 201)
    post_data = post_response.json()
    assert post_data["keyword"] == "llm"
    assert post_data["synonyms"] == ["large language model", "거대 언어 모델"]
    created_id = post_data["id"]

    # 4. GET by ID
    get_by_id_response = await client.get(f"/api/v1/synonyms/{created_id}")
    assert_status_code(get_by_id_response, 200)
    assert get_by_id_response.json()["keyword"] == "llm"

    # 5. PATCH - Update the synonyms
    patch_payload = {
        "synonyms": ["large language model", "거대 언어 모델", "대형 언어 모델"],
        "description": "Updated description",
    }
    patch_response = await client.patch(f"/api/v1/synonyms/{created_id}", json=patch_payload)
    assert_status_code(patch_response, 200)
    patch_data = patch_response.json()
    assert patch_data["synonyms"] == ["large language model", "거대 언어 모델", "대형 언어 모델"]
    assert patch_data["description"] == "Updated description"

    # 6. DELETE
    delete_response = await client.delete(f"/api/v1/synonyms/{created_id}")
    assert_status_code(delete_response, 200)
    assert delete_response.json()["success"] is True

    # 7. GET by ID after delete should return 404
    get_after_delete = await client.get(f"/api/v1/synonyms/{created_id}")
    assert_status_code(get_after_delete, 404)


async def test_synonyms_search_filter(
    client: AsyncClient,
    make_db: Callable[..., Awaitable[Any]],
) -> None:
    # Create distinct synonym maps
    await make_db(
        SynonymMapRepository,
        keyword="fastapi",
        synonyms=["fast-api", "web framework"],
        description="High performance web framework",
    )
    await make_db(
        SynonymMapRepository,
        keyword="pytorch",
        synonyms=["torch", "deep learning framework"],
        description="ML framework by Meta",
    )
    await make_db(
        SynonymMapRepository,
        keyword="needle",
        synonyms=["torch"],
        description="GPU math lib",
    )

    # 1. Search by keyword
    response = await client.get("/api/v1/synonyms", params={"search": "fastapi"})
    assert_status_code(response, 200)
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["keyword"] == "fastapi"

    # 2. Search by synonyms
    response = await client.get("/api/v1/synonyms", params={"search": "deep learning"})
    assert_status_code(response, 200)
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["keyword"] == "pytorch"

    # 3. Search by description
    response = await client.get("/api/v1/synonyms", params={"search": "High performance"})
    assert_status_code(response, 200)
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["keyword"] == "fastapi"

    # 4. Search with no matches
    response = await client.get("/api/v1/synonyms", params={"search": "nonexistent"})
    assert_status_code(response, 200)
    data = response.json()
    assert len(data["items"]) == 0

    # 5. Search should not match substrings inside a serialized JSON representation
    response = await client.get("/api/v1/synonyms", params={"search": "or"})
    assert_status_code(response, 200)
    data = response.json()
    assert all(item["keyword"] != "needle" for item in data["items"])
