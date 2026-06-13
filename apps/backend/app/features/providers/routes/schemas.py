from pydantic import BaseModel, Field


class ProviderOptions(BaseModel):
    embedding_models: list[str] = Field(description="List of available embedding models")
    llm_models: list[str] = Field(description="List of available LLM models")
    reranker_models: list[str] = Field(description="List of available reranker models")
    parser_providers: list[str] = Field(description="List of available parser providers")
    sparse_embedding_models: list[str] = Field(description="List of available sparse embedding models")
