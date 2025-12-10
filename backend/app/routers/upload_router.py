from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from minio import Minio
from app.config import settings
from app.database import get_db
import uuid

router = APIRouter(prefix="/api/upload", tags=["Upload"])

minio_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=False
)

@router.post("/")
async def upload_pdfs(
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    results = []

    for file in files:
        object_key = f"{uuid.uuid4()}_{file.filename}"

        # Upload to MinIO
        minio_client.put_object(
            settings.minio_bucket,
            object_key,
            file.file,
            length=-1,
            part_size=10 * 1024 * 1024,
        )

        # Insert into database
        await db.execute(
            text("""
                INSERT INTO pdf_metadata (filename, object_key)
                VALUES (:filename, :object_key)
            """),
            {"filename": file.filename, "object_key": object_key},
        )

        results.append({
            "filename": file.filename,
            "stored_as": object_key,
        })

    return {"success": True, "files": results}
