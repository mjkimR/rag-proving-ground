from pathlib import Path

from app_layer_base.base.usecases.base import BaseUseCase
from loguru import logger
from rag_core.adapters.prompt.config import get_prompt_settings

from app.features.providers.prompts.schemas import FallbackTemplateInfo


class ListFallbackTemplatesUseCase(BaseUseCase):
    async def execute(self) -> list[FallbackTemplateInfo]:
        settings = get_prompt_settings()
        if not settings.fallback_dir:
            return []

        fallback_path = Path(settings.fallback_dir)
        if not fallback_path.exists() or not fallback_path.is_dir():
            logger.warning(f"Fallback directory {fallback_path} does not exist or is not a directory.")
            return []

        templates = []
        for file_path in fallback_path.iterdir():
            if file_path.is_file() and file_path.suffix in [".yaml", ".yml", ".txt"]:
                try:
                    content = file_path.read_text(encoding="utf-8")
                    templates.append(
                        FallbackTemplateInfo(
                            name=file_path.stem,
                            format=file_path.suffix.lstrip("."),
                            content=content,
                        )
                    )
                except Exception as file_err:
                    logger.error(f"Failed to read prompt template file {file_path}: {file_err}")

        # Sort templates by name for UI consistency
        templates.sort(key=lambda t: t.name)
        return templates
