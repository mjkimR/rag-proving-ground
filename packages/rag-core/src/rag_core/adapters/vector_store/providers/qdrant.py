from typing import Any

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from rag_core.adapters.vector_store.interface import VectorStoreProvider, import_error_handler
from rag_core.ai.models import get_embedding_model


class QdrantSettings(BaseSettings):
    url: str = Field(default="http://localhost:6333", description="Qdrant server URL")
    api_key: SecretStr | None = Field(default=None, description="API key for Qdrant authentication")
    model_config = SettingsConfigDict(env_prefix="VECTOR_DB_QDRANT_")


class QdrantProvider(VectorStoreProvider):
    @classmethod
    def from_env(cls) -> VectorStoreProvider:
        with import_error_handler("qdrant"):
            from qdrant_client import QdrantClient
        config = QdrantSettings()  # type: ignore
        api_key = config.api_key.get_secret_value() if config.api_key else None
        client = QdrantClient(url=config.url, api_key=api_key)
        return QdrantProvider(client)

    def close(self) -> None:
        if self.client:
            self.client.close()

    async def check_health(self) -> bool:
        if not self.client:
            return False
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False

    async def create_vector_store(self, collection_name: str, model_name: str) -> Any:
        with import_error_handler("qdrant"):
            from langchain_qdrant import QdrantVectorStore
            from qdrant_client.http import models as conf
            from qdrant_client.http.exceptions import ApiException

        embedding_model = get_embedding_model(model_name)

        if not self.client.collection_exists(collection_name=collection_name):
            try:
                dummy_embedding = embedding_model.embed_query("dummy")
                dimension = len(dummy_embedding)
            except Exception as exc:
                raise RuntimeError(f"Failed to retrieve embedding dimension for '{model_name}': {exc}") from exc

            try:
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=conf.VectorParams(size=dimension, distance=conf.Distance.COSINE),
                )
                # Create payload index on metadata.knowledge_id as partition key
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name="metadata.knowledge_id",
                    field_schema=conf.PayloadSchemaType.KEYWORD,
                )
            except ApiException as e:
                if "exists" in str(e):
                    pass
                else:
                    raise e

        return QdrantVectorStore(
            client=self.client,
            collection_name=collection_name,
            embedding=embedding_model,
        )
