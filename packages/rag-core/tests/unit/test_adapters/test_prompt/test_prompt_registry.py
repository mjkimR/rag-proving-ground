from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml
from rag_core.adapters.prompt.factory import PromptFactory
from rag_core.adapters.prompt.instance import get_prompt, invalidate_prompt_cache
from rag_core.adapters.prompt.providers import register_default_prompt_providers
from rag_core.adapters.prompt.providers.langfuse import LangfusePromptProvider
from rag_core.adapters.prompt.providers.s3 import S3PromptProvider
from rag_core.adapters.prompt.registry import PromptProviderRegistry


@pytest.fixture(autouse=True)
def mock_storage_client(mocker) -> AsyncMock:
    # Globally mock S3 get_storage_client to avoid initialization error
    mock_storage = mocker.AsyncMock()
    mocker.patch("rag_core.adapters.prompt.providers.s3.get_storage_client", return_value=mock_storage)
    return mock_storage


@pytest.fixture
def temp_fallback_dir(tmp_path) -> Path:
    fallback = tmp_path / "fallback"
    fallback.mkdir()
    return fallback


def test_registry_and_factory() -> None:
    # Ensure default providers are registered
    register_default_prompt_providers()

    # Test listing and retrieving registered providers
    providers = PromptProviderRegistry.list_providers()
    assert "s3" in providers
    assert "langfuse" in providers

    s3_provider = PromptFactory.create_provider("s3")
    assert isinstance(s3_provider, S3PromptProvider)

    lf_provider = PromptFactory.create_provider("langfuse")
    assert isinstance(lf_provider, LangfusePromptProvider)


async def test_fallback_logic(temp_fallback_dir) -> None:
    # Write yaml, yml and txt fallback files
    yaml_data = {"template": "Hello {name} from YAML"}
    yaml_file = temp_fallback_dir / "test_prompt.yaml"
    yaml_file.write_text(yaml.dump(yaml_data), encoding="utf-8")

    yml_data = {"template": "Hello {name} from YML"}
    yml_file = temp_fallback_dir / "yml_prompt.yml"
    yml_file.write_text(yaml.dump(yml_data), encoding="utf-8")

    txt_content = "Hello {name} from TXT"
    txt_file = temp_fallback_dir / "text_prompt.txt"
    txt_file.write_text(txt_content, encoding="utf-8")

    provider = S3PromptProvider(bucket="prompts", fallback_dir=str(temp_fallback_dir))

    # Test loading YAML fallback
    res_yaml = provider._get_fallback_prompt("test_prompt")
    assert res_yaml == yaml_data

    # Test loading YML fallback
    res_yml = provider._get_fallback_prompt("yml_prompt")
    assert res_yml == yml_data

    # Test loading TXT fallback
    res_txt = provider._get_fallback_prompt("text_prompt")
    assert res_txt == txt_content

    # Test missing prompt fallback raising FileNotFoundError
    with pytest.raises(FileNotFoundError):
        provider._get_fallback_prompt("non_existent_prompt")


async def test_s3_prompt_provider(mock_storage_client, temp_fallback_dir) -> None:
    provider = S3PromptProvider(bucket="prompts", fallback_dir=str(temp_fallback_dir))

    # 1. Success case: Download YAML from S3
    yaml_data = {"system": "You are a helpful assistant"}
    mock_storage_client.download_file.return_value = yaml.dump(yaml_data).encode("utf-8")

    res = await provider.get_prompt("my_prompt")
    assert res == yaml_data
    mock_storage_client.download_file.assert_called_with("prompts", "my_prompt.yaml")

    # 2. Success case: Download YML from S3 (when YAML is not found)
    async def side_effect_yml(bucket, key):
        if key.endswith(".yaml"):
            raise FileNotFoundError("Mock S3 file not found")
        return yaml.dump({"template": "Hello YML S3"}).encode("utf-8")

    mock_storage_client.download_file.side_effect = side_effect_yml
    res_yml = await provider.get_prompt("my_yml_prompt")
    assert res_yml == {"template": "Hello YML S3"}

    # 3. Success case: Download TXT from S3 (when YAML and YML are not found or fail)
    async def side_effect_txt(bucket, key):
        if key.endswith(".yaml") or key.endswith(".yml"):
            raise FileNotFoundError("Mock S3 file not found")
        return b"Hello TXT S3"

    mock_storage_client.download_file.side_effect = side_effect_txt

    res_txt = await provider.get_prompt("my_prompt")
    assert res_txt == "Hello TXT S3"

    # 4. Fail case: S3 download fails, fallback is used
    mock_storage_client.download_file.side_effect = Exception("S3 Error")
    # write fallback file
    (temp_fallback_dir / "fallback_prompt.txt").write_text("Fallback content", encoding="utf-8")

    res_fallback = await provider.get_prompt("fallback_prompt")
    assert res_fallback == "Fallback content"


async def test_langfuse_prompt_provider(mocker, temp_fallback_dir) -> None:
    # Mock Langfuse Client
    mock_lf_client = MagicMock()
    mocker.patch("rag_core.adapters.prompt.providers.langfuse.Langfuse", return_value=mock_lf_client)

    provider = LangfusePromptProvider(
        fallback_dir=str(temp_fallback_dir),
        public_key="pk-test",
        secret_key="sk-test",
        host="http://localhost:3000",
    )

    # 1. Success case: call get_prompt with integer version
    mock_prompt_obj = MagicMock()
    mock_lf_client.get_prompt.return_value = mock_prompt_obj

    res = await provider.get_prompt("name", version=2)
    assert res == mock_prompt_obj
    mock_lf_client.get_prompt.assert_called_with("name", version=2)

    # 2. Success case: call get_prompt with string label ("production")
    res_label = await provider.get_prompt("name", version="production")
    assert res_label == mock_prompt_obj
    mock_lf_client.get_prompt.assert_called_with("name", label="production")

    # 3. Success case: call with string version that is numeric (e.g. "3")
    res_str_digit = await provider.get_prompt("name", version="3")
    assert res_str_digit == mock_prompt_obj
    mock_lf_client.get_prompt.assert_called_with("name", version=3)

    # 4. Fail case: Langfuse client error, fallback used
    mock_lf_client.get_prompt.side_effect = Exception("Langfuse Timeout")
    (temp_fallback_dir / "lf_fallback.yaml").write_text("template: 'LF YAML'", encoding="utf-8")

    res_fallback = await provider.get_prompt("lf_fallback")
    assert res_fallback == {"template": "LF YAML"}


async def test_instance_get_prompt_caching(mocker, mock_storage_client, temp_fallback_dir) -> None:
    # Setup settings to use S3 and a mock fallback dir
    mocker.patch(
        "rag_core.adapters.prompt.instance.get_prompt_settings",
        return_value=MagicMock(
            provider="s3", s3_bucket="prompts", cache_ttl_seconds=10, fallback_dir=str(temp_fallback_dir)
        ),
    )

    # Clean the caching singleton instance to re-initialize with mock settings
    mocker.patch("rag_core.adapters.prompt.instance._provider_instance", None)
    invalidate_prompt_cache()

    mock_storage_client.download_file.return_value = b"Hello cached world!"

    # First call: downloads file
    res1 = await get_prompt("cached_prompt")
    assert res1 == "Hello cached world!"
    assert mock_storage_client.download_file.call_count == 1

    # Second call: cached, download_file not called again
    res2 = await get_prompt("cached_prompt")
    assert res2 == "Hello cached world!"
    assert mock_storage_client.download_file.call_count == 1

    # Invalidate cache, then third call: downloads file again
    invalidate_prompt_cache()
    res3 = await get_prompt("cached_prompt")
    assert res3 == "Hello cached world!"
    assert mock_storage_client.download_file.call_count == 2
