from typing import Any, get_args

import pytest
from app_layer_base.base.models.mixin import Base
from app_layer_base.base.repos.base import BaseRepository
from httpx import AsyncClient
from polyfactory.factories.pydantic_factory import ModelFactory
from pydantic import BaseModel
from rag_core.embeddings import KnowledgeEmbeddingConfig
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures import factory as ft
from tests.utils.fastapi import resolve_dependency


class KnowledgeEmbeddingConfigFactory(ModelFactory):
    __model__ = KnowledgeEmbeddingConfig

    use_colpali = False


def get_model_factory[T: BaseModel](model_class: type[T], _use_default: bool = False) -> type[ModelFactory]:
    """Get the corresponding ModelFactory for a given Pydantic model class."""
    from app.features.history.job_process_histories.schemas import JobProcessHistoryCreate

    model_factory: dict[type[BaseModel], type[ModelFactory]] = {
        JobProcessHistoryCreate: ft.JobProcessHistoryCreateFactory,
        KnowledgeEmbeddingConfig: KnowledgeEmbeddingConfigFactory,
    }

    factory_class = model_factory.get(model_class)
    if factory_class is None:
        return ModelFactory.create_factory(model_class, __use_defaults__=_use_default)  # type: ignore

    if _use_default:
        return factory_class.create_factory(model_class, __use_defaults__=True)  # type: ignore[return-value]

    return factory_class


@pytest.fixture
def make():
    """Pydantic model factory fixture.

    Usage: make(User, name="test")
    - model_class: Pydantic model class to create
    - _use_default: whether to use default values defined in the model (default: False)
    - kwargs: fields to override in the factory
    """

    def _make[T: BaseModel](model_class: type[T], _use_default: bool = False, **kwargs: Any) -> T:
        factory = get_model_factory(model_class, _use_default)
        return factory.build(**kwargs)

    return _make


@pytest.fixture
def make_batch():
    """Pydantic model batch factory fixture.

    Usage: make_batch(User, 3, name="test")
    - model_class: Pydantic model class to create
    - _size: number of models to create (default: 3)
    - _use_default: whether to use default values defined in the model (default: False)
    - kwargs: fields to override in the factory
    """

    def _make_batch[T: BaseModel](
        model_class: type[T], _size: int = 3, _use_default: bool = False, **kwargs: Any
    ) -> list[T]:
        factory = get_model_factory(model_class, _use_default)
        return factory.batch(size=_size, **kwargs)

    return _make_batch


def _find_generic_args(repo_class: type[BaseRepository]) -> type[BaseModel]:
    """Extract generic type arguments from a BaseRepository subclass."""
    if not issubclass(repo_class, BaseRepository):
        raise ValueError(f"{repo_class.__name__} is not a subclass of BaseRepository.")
    if not hasattr(repo_class, "__orig_bases__"):
        raise ValueError(f"{repo_class.__name__} does not have __orig_bases__ attribute.")
    orig_bases = repo_class.__orig_bases__  # type: ignore
    generic_args = get_args(orig_bases[0])
    create_schema_type = generic_args[1]
    return create_schema_type


@pytest.fixture
def make_db(session: AsyncSession):
    """SQLAlchemy model factory fixture. (with repo creation)

    Usage: await make_db(UserRepository, name="test")
    - repo_class_or_instance: repo class or instance to use for creating the model (e.g., UserRepository)
    - _build_kwargs: extra keyword arguments passed to factory.build()
    - _create_kwargs: extra keyword arguments passed to repo.create()
    - _use_default: whether to use default values defined in the schema (default: False)
    - kwargs: fields to override in the factory (used for build only)

    Returns the created SQLAlchemy model instance after saving to the database.
    """

    async def _make_db(
        repo_class_or_instance: type[BaseRepository] | BaseRepository,
        _build_kwargs: dict[str, Any] | None = None,
        _create_kwargs: dict[str, Any] | None = None,
        _use_default: bool = False,
        **kwargs: Any,
    ) -> Base:
        if not isinstance(repo_class_or_instance, type):
            repo_class = type(repo_class_or_instance)
            repo = repo_class_or_instance
        else:
            repo_class = repo_class_or_instance
            repo = resolve_dependency(repo_class_or_instance)
        create_schema_type = _find_generic_args(repo_class)
        factory = get_model_factory(create_schema_type, _use_default)
        data = factory.build(**{**kwargs, **(_build_kwargs or {})})
        result = await repo.create(session, data, **{**kwargs, **(_create_kwargs or {})})
        await session.commit()
        return result

    return _make_db


@pytest.fixture
def make_db_batch(session: AsyncSession):
    """SQLAlchemy model batch factory fixture. (with repo creation)

    Usage: await make_db_batch(UserRepository, 3)
    - repo_class_or_instance: Repo class or instance to use for creating the models (e.g., UserRepository)
    - _size: number of models to create (default: 3)
    - _build_kwargs: extra keyword arguments passed to factory.batch()
    - _create_kwargs: extra keyword arguments passed to repo.create()
    - _use_default: whether to use default values defined in the schema (default: False)
    - kwargs: fields to override in the factory (used for build only)

    Returns a list of created SQLAlchemy model instances after saving to the database.
    """

    async def _make_db_batch(
        repo_class_or_instance: BaseRepository | type[BaseRepository],
        _size: int = 3,
        _build_kwargs: dict[str, Any] | None = None,
        _create_kwargs: dict[str, Any] | None = None,
        _use_default: bool = False,
        **kwargs: Any,
    ) -> list[Base]:
        if not isinstance(repo_class_or_instance, type):
            repo_class = type(repo_class_or_instance)
            repo = repo_class_or_instance
        else:
            repo_class = repo_class_or_instance
            repo = resolve_dependency(repo_class_or_instance)
        create_schema_type = _find_generic_args(repo_class)
        factory = get_model_factory(create_schema_type, _use_default)
        data_list = factory.batch(size=_size, **{**kwargs, **(_build_kwargs or {})})
        results = []
        for data in data_list:
            results.append(await repo.create(session, data, **{**kwargs, **(_create_kwargs or {})}))
        await session.commit()
        return results

    return _make_db_batch


@pytest.fixture
def make_api(client: AsyncClient):
    """API model factory fixture.

    Usage: await make_api("/users/", UserCreate, name="test")
    - endpoint: API endpoint to create the model
    - model_class: Pydantic model class for the request body
    - _use_default: whether to use default values defined in the model (default: False)
    - kwargs: fields to override in the factory
    """

    async def _make_api[T: BaseModel](
        endpoint: str, model_class: type[T], _use_default: bool = False, **kwargs: Any
    ) -> T:
        factory = get_model_factory(model_class, _use_default)
        data = factory.build(**kwargs)
        response = await client.post(endpoint, json=data.model_dump())
        response.raise_for_status()
        return model_class.model_validate(response.json())

    return _make_api


@pytest.fixture
def make_api_batch(client: AsyncClient):
    """API model batch factory fixture.

    Usage: await make_api_batch("/users/batch", UserCreate, 3, name="test")
    - endpoint: API endpoint to create the models
    - model_class: Pydantic model class for the request body
    - _size: number of models to create (default: 3)
    - _use_default: whether to use default values defined in the model (default: False)
    - kwargs: fields to override in the factory
    """

    async def _make_api_batch[T: BaseModel](
        endpoint: str, model_class: type[T], _size: int = 3, _use_default: bool = False, **kwargs: Any
    ) -> list[T]:
        factory = get_model_factory(model_class, _use_default)
        data_list = factory.batch(size=_size, **kwargs)
        payload = [data.model_dump() for data in data_list]
        response = await client.post(endpoint, json=payload)
        response.raise_for_status()
        return [model_class.model_validate(item) for item in response.json()]

    return _make_api_batch
