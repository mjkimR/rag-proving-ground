from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .local import LocalStorageProvider
    from .s3 import S3StorageProvider

__all__ = ["LocalStorageProvider", "S3StorageProvider", "register_default_providers"]

_lazy_imports: dict[str, str] = {
    "LocalStorageProvider": ".local",
    "S3StorageProvider": ".s3",
}


def __getattr__(name: str):
    if name in _lazy_imports:
        import importlib

        module = importlib.import_module(_lazy_imports[name], package=__name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_DEFAULTS_REGISTERED = False


def register_default_providers() -> None:
    global _DEFAULTS_REGISTERED
    if _DEFAULTS_REGISTERED:
        return

    from rag_core.adapters.file_storage.config import FileProviderType
    from rag_core.adapters.file_storage.providers.local import LocalStorageProvider
    from rag_core.adapters.file_storage.providers.s3 import S3StorageProvider
    from rag_core.adapters.file_storage.registry import FileStorageRegistry

    FileStorageRegistry.register(FileProviderType.LOCAL, LocalStorageProvider)
    FileStorageRegistry.register(FileProviderType.S3, S3StorageProvider)
    _DEFAULTS_REGISTERED = True
