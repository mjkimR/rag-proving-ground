from app_file_storage import get_storage_client
from app_layer_base.base.usecases.base import BaseUseCase


class ListKnowledgeBasesUseCase(BaseUseCase):
    async def execute(self) -> list[str]:
        """Scan storage under 'knowledge/' and return a list of unique knowledge base names."""
        storage_client = get_storage_client()
        prefixes = set()
        try:
            async for file_path in storage_client.list_files("knowledge/"):
                # file_path looks like "knowledge/{knowledge_name}/{file_md5}/{filename}"
                parts = file_path.split("/")
                if len(parts) >= 2:
                    prefixes.add(parts[1])
        except Exception:
            pass
        return sorted(list(prefixes))
