<<<<<<< Updated upstream
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import StreamingResponse
=======
from fastapi import APIRouter, UploadFile, File, Depends
>>>>>>> Stashed changes
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from minio import Minio
from minio.error import S3Error
from app.config import settings
from app.database import get_db
from app.models import PDFMetadata, ProcessingStatus
<<<<<<< Updated upstream
from app.models.user import User
from app.schemas import ApiResponse
from app.dependencies import get_current_user
from worker.tasks import process_pdf
=======
from app.schemas import ApiResponse
from worker.tasks import process_pdf   # ✅ IMPORTANT
>>>>>>> Stashed changes
import uuid

router = APIRouter(prefix="/documents", tags=["Documents"])

minio_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=False
)

def ensure_bucket_exists():
    if not minio_client.bucket_exists(settings.minio_bucket):
        minio_client.make_bucket(settings.minio_bucket)

<<<<<<< Updated upstream

async def cleanup_orphaned_file(object_key: str):
    try:
        minio_client.remove_object(settings.minio_bucket, object_key)
    except:
        pass


=======
# -------------------------
# UPLOAD PDFs
# -------------------------
>>>>>>> Stashed changes
@router.post("/upload")
async def upload_documents(
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload PDF files, persist metadata, and enqueue processing."""
    ensure_bucket_exists()
<<<<<<< Updated upstream

    results = []
    errors = []
    uploaded_keys: List[str] = []

    for file in files:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            errors.append({"filename": file.filename or "unknown", "error": "Only PDF files are allowed"})
            continue

=======
    uploaded = []

    for file in files:
>>>>>>> Stashed changes
        object_key = f"{uuid.uuid4()}_{file.filename}"

        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)

<<<<<<< Updated upstream
            minio_client.put_object(
                settings.minio_bucket,
                object_key,
                file.file,
                length=file_size,
                content_type="application/pdf",
            )
            uploaded_keys.append(object_key)
=======
        minio_client.put_object(
            settings.minio_bucket,
            object_key,
            file.file,
            length=size,
            content_type="application/pdf",
        )
>>>>>>> Stashed changes

        pdf = PDFMetadata(
            filename=file.filename,
            object_key=object_key,
            file_size=size,
            status=ProcessingStatus.PENDING,
git         )

        db.add(pdf)
        await db.flush()

<<<<<<< Updated upstream
            # Trigger async processing pipeline
            process_pdf.delay(str(pdf.id), object_key)

            results.append({
                "id": str(pdf.id),
                "filename": pdf.filename,
                "object_key": object_key,
                "file_size": file_size,
                "status": pdf.status.value.lower(),
            })

        except Exception as e:
            # Best-effort cleanup if any step fails
            await cleanup_orphaned_file(object_key)
            errors.append({"filename": file.filename, "error": str(e)})
=======
        # 🔥 THIS IS THE MISSING LINE (CHUNKING STARTS HERE)
        process_pdf.delay(str(pdf.id), object_key)

        uploaded.append({
            "id": str(pdf.id),
            "filename": pdf.filename,
            "status": pdf.status.value,
        })
>>>>>>> Stashed changes

    try:
        await db.commit()
    except Exception as e:
        # Roll back DB and storage on commit failure
        for key in uploaded_keys:
            await cleanup_orphaned_file(key)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return ApiResponse(
<<<<<<< Updated upstream
        success=len(results) > 0,
        data={
            "uploaded": results,
            "errors": errors,
            "total_uploaded": len(results),
            "total_errors": len(errors),
        },
        message=f"Uploaded {len(results)} file(s)" + (f", {len(errors)} failed" if errors else ""),
    )


@router.get("")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50,
):
    """List documents uploaded by the current user."""
    result = await db.execute(
        select(PDFMetadata)
        .where(PDFMetadata.uploaded_by == current_user.id)
        .order_by(PDFMetadata.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    documents = result.scalars().all()

    return ApiResponse(
        success=True,
        data={
            "documents": [
                {
                    "id": str(doc.id),
                    "filename": doc.filename,
                    "file_size": doc.file_size,
                    "page_count": doc.page_count,
                    "status": doc.status.value.lower(),
                    "created_at": doc.created_at.isoformat(),
                }
                for doc in documents
            ],
            "total": len(documents),
        },
        message=None,
    )


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific document by ID. Only owner can access."""
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")

    result = await db.execute(
        select(PDFMetadata).where(
            PDFMetadata.id == doc_uuid,
            PDFMetadata.uploaded_by == current_user.id,
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return ApiResponse(
        success=True,
        data={
            "id": str(document.id),
            "filename": document.filename,
            "object_key": document.object_key,
            "file_size": document.file_size,
            "page_count": document.page_count,
            "status": document.status.value.lower(),
            "error_message": document.error_message,
            "created_at": document.created_at.isoformat(),
            "updated_at": document.updated_at.isoformat(),
        },
        message=None,
    )


@router.get("/{document_id}/status")
async def get_document_status(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return processing/embedding status for a document."""
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")

    result = await db.execute(
        select(PDFMetadata).where(
            PDFMetadata.id == doc_uuid,
            PDFMetadata.uploaded_by == current_user.id,
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    progress = 100 if document.status in {ProcessingStatus.COMPLETED} else 0

    return ApiResponse(
        success=True,
        data={
            "id": str(document.id),
            "status": document.status.value.lower(),
            "progress": progress,
            "message": document.error_message,
        },
    )


@router.get("/{document_id}/file")
async def get_document_file(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream the original PDF file from MinIO."""
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")

    result = await db.execute(
        select(PDFMetadata).where(
            PDFMetadata.id == doc_uuid,
            PDFMetadata.uploaded_by == current_user.id,
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        obj = minio_client.get_object(settings.minio_bucket, document.object_key)
    except S3Error as exc:  # pragma: no cover - passthrough errors
        raise HTTPException(status_code=500, detail=str(exc))

    return StreamingResponse(obj.stream(32 * 1024), media_type="application/pdf")


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a document from storage and database. Only owner can delete."""
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")

    result = await db.execute(
        select(PDFMetadata).where(
            PDFMetadata.id == doc_uuid,
            PDFMetadata.uploaded_by == current_user.id,
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        minio_client.remove_object(settings.minio_bucket, document.object_key)
    except S3Error:
        pass

    await db.delete(document)
    await db.commit()

    return ApiResponse(
        success=True,
        data=None,
        message="Document deleted successfully",
=======
        success=True,
        data={"documents": uploaded},
        message="Uploaded successfully"
    )

# -------------------------
# LIST DOCUMENTS (NO AUTH)
# -------------------------
@router.get("")
async def list_documents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PDFMetadata).order_by(PDFMetadata.created_at.desc())
    )
    docs = result.scalars().all()

    return ApiResponse(
        success=True,
        data={
            "documents": [
                {
                    "id": str(d.id),
                    "filename": d.filename,
                    "file_size": d.file_size,
                    "status": d.status.value,
                    "created_at": d.created_at.isoformat(),
                }
                for d in docs
            ]
        },
        message=None
>>>>>>> Stashed changes
    )
