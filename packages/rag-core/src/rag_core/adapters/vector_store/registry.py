import importlib
from typing import ClassVar

from rag_core.adapters.vector_store.config import VectorDBProviderType
from rag_core.adapters.vector_store.interface import VectorStoreProvider


class VectorStoreRegistry:
    """Registry for vector store providers."""

    _PROVIDER_MODULES: ClassVar[dict[VectorDBProviderType, str]] = {
        VectorDBProviderType.QDRANT: "app_vector_store.providers.qdrant",
    }

    _PROVIDER_CLASSES: ClassVar[dict[VectorDBProviderType, str]] = {
        VectorDBProviderType.QDRANT: "QdrantProvider",
    }

    @classmethod
    def get_provider_cls(cls, provider: VectorDBProviderType | str) -> type[VectorStoreProvider]:
        try:
            provider_enum = VectorDBProviderType(provider)
        except ValueError as exc:
            raise ValueError(f"Unsupported Vector Store provider: {provider}") from exc

        if provider_enum not in cls._PROVIDER_MODULES:
            raise ValueError(f"Vector Store provider for kind '{provider_enum}' is not registered.")

        module_path = cls._PROVIDER_MODULES[provider_enum]
        class_name = cls._PROVIDER_CLASSES[provider_enum]

        module = importlib.import_module(module_path)
        return getattr(module, class_name)
