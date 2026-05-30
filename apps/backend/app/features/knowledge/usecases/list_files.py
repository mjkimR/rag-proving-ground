import json

from app_file_storage import get_storage_client
from app_layer_base.base.usecases.base import BaseUseCase


class ListKnowledgeFilesUseCase(BaseUseCase):
    async def execute(self, knowledge_name: str) -> list[dict]:
        """Scan storage under 'knowledge/{knowledge_name}/' and return a list of document details."""
        storage_client = get_storage_client()
        prefix = f"knowledge/{knowledge_name}/"
        files_map = {}

        try:
            async for file_path in storage_client.list_files(prefix):
                parts = file_path.split("/")
                if len(parts) < 4:
                    continue
                file_md5 = parts[2]
                filename = parts[3]

                if file_md5 not in files_map:
                    files_map[file_md5] = {
                        "md5_hash": file_md5,
                        "filename": "",
                        "original_file_path": "",
                        "parsed_data_path": "",
                        "element_count": 0,
                        "size_bytes": 0,
                    }

                if filename == "parsed_data.json":
                    files_map[file_md5]["parsed_data_path"] = file_path
                    try:
                        meta = await storage_client.get_file_metadata(file_path)
                        files_map[file_md5]["size_bytes"] += meta.get("size", 0)

                        data = await storage_client.download_file(file_path)
                        parsed_doc = json.loads(data.decode("utf-8"))
                        files_map[file_md5]["element_count"] = len(parsed_doc.get("elements", []))
                    except Exception:
                        pass
                else:
                    files_map[file_md5]["filename"] = filename
                    files_map[file_md5]["original_file_path"] = file_path
                    try:
                        meta = await storage_client.get_file_metadata(file_path)
                        files_map[file_md5]["size_bytes"] += meta.get("size", 0)
                    except Exception:
                        pass
        except Exception:
            pass

        result = []
        for info in files_map.values():
            if not info["filename"]:
                info["filename"] = "unknown_file"
            result.append(info)

        return result
