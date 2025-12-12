from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from minio import Minio
from minio.error import S3Error
from app.config import settings
from app.database import get_db
from app.models import PDFMetadata, ProcessingStatus
from app.models.user import User
from app.schemas import ApiResponse
from app.dependencies import get_current_user
from worker.tasks import process_pdf
import uuid

router = APIRouter(prefix="/documents", tags=["Documents"])


# Initialize MinIO client
minio_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=False
)


def ensure_bucket_exists():
    """Ensure the MinIO bucket exists. Create if needed."""
    try:
        if not minio_client.bucket_exists(settings.minio_bucket):
            minio_client.make_bucket(settings.minio_bucket)
    except S3Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize MinIO bucket: {str(e)}"
        )


async def cleanup_orphaned_file(object_key: str):
    """Remove uploaded file if later DB operations fail."""
    try:
        minio_client.remove_object(settings.minio_bucket, object_key)
    except:
        pass  # best effort


@router.post("/upload")
async def upload_documents(
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ensure_bucket_exists()

    results = []
    errors = []
    uploaded_keys = []  # rollback safety

    for file in files:

        # Validate PDF
        if not file.filename.lower().endswith(".pdf"):
            errors.append({"filename": file.filename, "error": "Only PDF files allowed"})
            continue

        object_key = f"{uuid.uuid4()}_{file.filename}"

        try:
            # Determine file size
            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(0)

            # Validate file size
            if file_size > settings.max_upload_size:
                errors.append({
                    "filename": file.filename,
                    "error": f"File too large. Maximum size is {settings.max_upload_size // (1024 * 1024)}MB"
                })
                continue

            # Upload to MinIO
            minio_client.put_object(
                settings.minio_bucket,
                object_key,
                file.file,
                length=file_size,
                content_type="application/pdf",
            )
            uploaded_keys.append(object_key)

            # Create DB record
            pdf_record = PDFMetadata(
                filename=file.filename,
                object_key=object_key,
                file_size=file_size,
                status=ProcessingStatus.PENDING,   # ALWAYS uppercase enum
                uploaded_by=current_user.id,
            )
            db.add(pdf_record)
            await db.flush()  # must flush to get ID

            # Trigger Celery async task
            process_pdf.delay(str(pdf_record.id), object_key)

            results.append({
                "id": str(pdf_record.id),
                "filename": file.filename,
                "object_key": object_key,
                "file_size": file_size,
                "status": pdf_record.status.value,
            })

        except Exception as e:

            if object_key in uploaded_keys:
                await cleanup_orphaned_file(object_key)

            errors.append({"filename": file.filename, "error": str(e)})

    # Commit successful DB inserts
    try:
        await db.commit()
    except Exception as e:

        # DB commit failed → remove every uploaded MinIO file
        for key in uploaded_keys:
            await cleanup_orphaned_file(key)

        raise HTTPException(
            status_code=500,
            detail=f"Database error during commit: {str(e)}"
        )

    return ApiResponse(
        success=True,
        data={
            "uploaded": results,
            "errors": errors,
            "total_uploaded": len(results),
            "total_errors": len(errors),
        },
        message=f"Uploaded {len(results)} file(s)"
    )


@router.get("")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50,
):
    """List all documents uploaded by the user."""
    result = await db.execute(
        select(PDFMetadata)
        .where(PDFMetadata.uploaded_by == current_user.id)
        .order_by(PDFMetadata.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    docs = result.scalars().all()

    return ApiResponse(
        success=True,
        data={
            "documents": [
                {
                    "id": str(doc.id),
                    "filename": doc.filename,
                    "file_size": doc.file_size,
                    "page_count": doc.page_count,
                    "status": doc.status.value,
                    "error_message": doc.error_message,
                    "created_at": doc.created_at.isoformat(),
                }
                for doc in docs
            ],
            "total": len(docs)
        }
    )


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetch metadata of a single document."""
    try:
        doc_uuid = uuid.UUID(document_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    result = await db.execute(
        select(PDFMetadata)
        .where(
            PDFMetadata.id == doc_uuid,
            PDFMetadata.uploaded_by == current_user.id,
        )
    )

    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return ApiResponse(
        success=True,
        data={
            "id": str(doc.id),
            "filename": doc.filename,
            "object_key": doc.object_key,
            "file_size": doc.file_size,
            "page_count": doc.page_count,
            "status": doc.status.value,
            "error_message": doc.error_message,
            "created_at": doc.created_at.isoformat(),
            "updated_at": doc.updated_at.isoformat(),
        },
    )


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete PDF from MinIO + metadata row from DB."""
    try:
        doc_uuid = uuid.UUID(document_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    result = await db.execute(
        select(PDFMetadata)
        .where(
            PDFMetadata.id == doc_uuid,
            PDFMetadata.uploaded_by == current_user.id
        )
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete MinIO object
    try:
        minio_client.remove_object(settings.minio_bucket, doc.object_key)
    except:
        pass

    # Delete DB entry
    await db.delete(doc)
    await db.commit()

    return ApiResponse(success=True, message="Document deleted")
