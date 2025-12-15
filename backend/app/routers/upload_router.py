from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from minio import Minio
from minio.error import S3Error
from app.config import settings
from app.database import get_db
from app.models import PDFMetadata, ProcessingStatus
from app.models.user import User
from app.dependencies import get_current_user
from worker.tasks import process_pdf
import uuid
from typing import List

router = APIRouter(prefix="/documents", tags=["Documents"])

# -------------------------
# MinIO client
# -------------------------
minio_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=False
)


def ensure_bucket_exists():
    try:
        if not minio_client.bucket_exists(settings.minio_bucket):
            minio_client.make_bucket(settings.minio_bucket)
    except S3Error as e:
        raise HTTPException(status_code=500, detail=str(e))


async def cleanup_orphaned_file(object_key: str):
    try:
        minio_client.remove_object(settings.minio_bucket, object_key)
    except:
        pass


# ============================
# UPLOAD PDF  ✅ (unchanged logic)
# ============================
@router.post("/upload")
async def upload_pdfs(
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_bucket_exists()

    results = []
    errors = []

    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            errors.append({"filename": file.filename, "error": "Only PDF files allowed"})
            continue

        object_key = f"{uuid.uuid4()}_{file.filename}"

        try:
            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(0)

            minio_client.put_object(
                settings.minio_bucket,
                object_key,
                file.file,
                length=file_size,
                content_type="application/pdf",
            )

            pdf = PDFMetadata(
                filename=file.filename,
                object_key=object_key,
                file_size=file_size,
                status=ProcessingStatus.PENDING,
                uploaded_by=current_user.id,
            )

            db.add(pdf)
            await db.flush()

            # 🔥 trigger pipeline
            process_pdf.delay(str(pdf.id), object_key)

            results.append({
                "id": str(pdf.id),
                "filename": pdf.filename,
                "status": pdf.status.value,
            })

        except Exception as e:
            await cleanup_orphaned_file(object_key)
            errors.append({"filename": file.filename, "error": str(e)})

    await db.commit()

    return {
        "uploaded": results,
        "errors": errors
    }


# ============================
# ✅ LIST DOCUMENTS (CRITICAL FIX)
# ============================
@router.get("/")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(PDFMetadata)
        .where(PDFMetadata.uploaded_by == current_user.id)
        .order_by(PDFMetadata.created_at.desc())
    )

    pdfs = result.scalars().all()

    # 🚨 FRONTEND EXPECTS ARRAY — RETURN ARRAY ONLY
    return [
        {
            "id": str(pdf.id),
            "filename": pdf.filename,
            "file_size": pdf.file_size,
            "status": pdf.status.value,
            "created_at": pdf.created_at.isoformat(),
        }
        for pdf in pdfs
    ]
