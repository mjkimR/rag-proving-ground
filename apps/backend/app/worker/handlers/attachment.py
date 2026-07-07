from uuid import UUID

from app_file_storage import get_storage_client
from app_layer_base.core.database.transaction import AsyncTransaction
from loguru import logger

from app.features.storage.file_attachments.processors import (
    AudioTranscriptionProcessor,
    ImageVisionProcessor,
    TempKbDocumentProcessor,
)
from app.features.storage.session_file_attachments.models import SessionFileAttachment
from app.worker.broker import broker


@broker.task(task_name="process_file_attachment")
async def process_file_attachment(session_file_attachment_id: UUID) -> dict:
    logger.info(f"Worker received process_file_attachment task for {session_file_attachment_id}")

    # 1. Fetch SessionFileAttachment and FileAttachment details
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    async with AsyncTransaction() as session:
        stmt = (
            select(SessionFileAttachment)
            .where(SessionFileAttachment.id == session_file_attachment_id)
            .options(selectinload(SessionFileAttachment.file_attachment))
        )
        result = await session.execute(stmt)
        session_file = result.scalars().first()

        if not session_file:
            logger.error(f"SessionFileAttachment {session_file_attachment_id} not found.")
            return {"status": "FAILED", "error": f"SessionFileAttachment {session_file_attachment_id} not found."}

        # Check if already completed
        if session_file.status == "COMPLETED":
            logger.info(f"SessionFileAttachment {session_file_attachment_id} is already completed. Skipping.")
            return dict(session_file.processed_metadata or {})

        # Mark as PROCESSING
        session_file.status = "PROCESSING"
        session_file.error_message = None
        await session.flush()

        file_attachment = session_file.file_attachment
        sha256 = file_attachment.sha256
        filename = file_attachment.filename
        mime_type = file_attachment.mime_type
        storage_path = file_attachment.storage_path
        purpose = session_file.purpose

    # 2. Download file content from MinIO
    storage_client = get_storage_client()
    try:
        raw_file_bytes = await storage_client.download_file(storage_path)
    except Exception as exc:
        logger.error(f"Failed to download attachment {storage_path} from storage: {exc}")
        async with AsyncTransaction() as session:
            db_session_file = await session.get(SessionFileAttachment, session_file_attachment_id)
            if db_session_file:
                db_session_file.status = "FAILED"
                db_session_file.error_message = f"Storage download failed: {exc}"
        raise exc

    # 3. Select and execute processor
    if purpose == "temp_kb":
        processor = TempKbDocumentProcessor()
    elif purpose == "vision":
        processor = ImageVisionProcessor()
    elif purpose == "audio":
        processor = AudioTranscriptionProcessor()
    else:
        # Default processor to context: succeed immediately
        logger.info(
            f"Unhandled purpose '{purpose}' for attachment {session_file_attachment_id}. Succeeding with raw info."
        )
        processor = None

    try:
        if processor:
            processed_metadata = await processor.process(
                session_file_attachment_id=session_file_attachment_id,
                raw_file_bytes=raw_file_bytes,
                filename=filename,
                mime_type=mime_type,
                sha256=sha256,
            )
        else:
            processed_metadata = {
                "message": f"Attachment processed successfully as raw purpose: '{purpose}'.",
                "storage_path": storage_path,
            }

        async with AsyncTransaction() as session:
            db_session_file = await session.get(SessionFileAttachment, session_file_attachment_id)
            if db_session_file:
                db_session_file.status = "COMPLETED"
                db_session_file.processed_metadata = processed_metadata
                await session.flush()
        return processed_metadata

    except Exception as exc:
        logger.error(f"Processing failed for SessionFileAttachment {session_file_attachment_id}: {exc}")
        async with AsyncTransaction() as session:
            db_session_file = await session.get(SessionFileAttachment, session_file_attachment_id)
            if db_session_file:
                db_session_file.status = "FAILED"
                db_session_file.error_message = f"Processing failed: {exc}"
                await session.flush()
        raise exc
