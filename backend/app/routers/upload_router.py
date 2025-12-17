from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Response
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


# --------------------------------------------------------------------------------
#  UPLOAD PDFs
# --------------------------------------------------------------------------------
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

            # Validate size
            if file_size > settings.max_upload_size:
                errors.append({
                    "filename": file.filename,
                    "error": f"File too large. Max size is {settings.max_upload_size // (1024 * 1024)}MB"
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
                status=ProcessingStatus.PENDING,
                uploaded_by=current_user.id,
            )
            db.add(pdf_record)
            await db.flush()  # Get ID

            # Trigger background processing
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

    # Commit DB changes
    try:
        await db.commit()
    except Exception as e:
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


# --------------------------------------------------------------------------------
#  LIST PDFs
# --------------------------------------------------------------------------------
@router.get("")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50,
):
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
                    "object_key": doc.object_key,
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


# --------------------------------------------------------------------------------
#  GET PDF METADATA
# --------------------------------------------------------------------------------
@router.get("/{document_id}")
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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


# --------------------------------------------------------------------------------
#  DOWNLOAD RAW PDF FILE
# --------------------------------------------------------------------------------
@router.get("/{document_id}/file")
async def get_document_file(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the raw PDF file bytes so the React viewer can display it.
    """

    # Validate UUID
    try:
        doc_uuid = uuid.UUID(document_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    # Fetch DB metadata
    result = await db.execute(
        select(PDFMetadata)
        .where(
            PDFMetadata.id == doc_uuid,
            PDFMetadata.uploaded_by == current_user.id
        )
    )
    metadata = result.scalar_one_or_none()

    if not metadata:
        raise HTTPException(status_code=404, detail="Document not found")

    object_key = metadata.object_key
    if not object_key:
        raise HTTPException(status_code=500, detail="Missing object key")

    # Fetch PDF from MinIO
    try:
        response = minio_client.get_object(settings.minio_bucket, object_key)
        pdf_bytes = response.read()
        response.close()
        response.release_conn()
    except Exception as e:
        print("MinIO fetch error:", e)
        raise HTTPException(status_code=500, detail="Failed to fetch PDF file from storage")

    # Return actual PDF
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename=\"{metadata.filename}\"'
        }
    )


# --------------------------------------------------------------------------------
#  DELETE PDF
# --------------------------------------------------------------------------------
@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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

    # Delete from MinIO
    try:
        minio_client.remove_object(settings.minio_bucket, doc.object_key)
    except:
        pass

    # Delete from DB
    await db.delete(doc)
    await db.commit()

    return ApiResponse(success=True, message="Document deleted")
# --------------------------------------------------------------------------------
#  DELETE ALL PDFs (USER-SCOPED)
# --------------------------------------------------------------------------------
@router.delete("")
async def delete_all_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Fetch all user documents
    result = await db.execute(
        select(PDFMetadata)
        .where(PDFMetadata.uploaded_by == current_user.id)
    )
    docs = result.scalars().all()

    if not docs:
        return ApiResponse(success=True, message="No documents to delete")

    object_keys = [doc.object_key for doc in docs]

    # 1. Delete files from MinIO (best-effort)
    for key in object_keys:
        try:
            minio_client.remove_object(settings.minio_bucket, key)
        except Exception:
            pass

    # 2. Delete DB rows (chunks are already FK-linked)
    for doc in docs:
        await db.delete(doc)

    await db.commit()

    return ApiResponse(
        success=True,
        message=f"Deleted {len(docs)} document(s)"
    )

