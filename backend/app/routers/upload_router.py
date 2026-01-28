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
from app.services.qdrant.qdrant_client import delete_pdf_vectors
import uuid

router = APIRouter(prefix="/documents", tags=["Documents"])

# ------------------------------------------------------------------------------
# MinIO client
# ------------------------------------------------------------------------------
minio_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=False,
)


def ensure_bucket_exists():
    try:
        if not minio_client.bucket_exists(settings.minio_bucket):
            minio_client.make_bucket(settings.minio_bucket)
    except S3Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize MinIO bucket: {str(e)}",
        )


async def cleanup_orphaned_file(object_key: str):
    try:
        minio_client.remove_object(settings.minio_bucket, object_key)
    except:
        pass


# ------------------------------------------------------------------------------
# UPLOAD PDFs
# ------------------------------------------------------------------------------
@router.post("/upload")
async def upload_documents(
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_bucket_exists()

    results = []
    errors = []
    uploaded_keys = []

    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            errors.append({"filename": file.filename, "error": "Only PDF files allowed"})
            continue

        object_key = f"{uuid.uuid4()}_{file.filename}"

        try:
            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(0)

            if file_size > settings.max_upload_size:
                errors.append({
                    "filename": file.filename,
                    "error": "File too large",
                })
                continue

            minio_client.put_object(
                settings.minio_bucket,
                object_key,
                file.file,
                length=file_size,
                content_type="application/pdf",
            )
            uploaded_keys.append(object_key)

            pdf_record = PDFMetadata(
                filename=file.filename,
                object_key=object_key,
                file_size=file_size,
                status=ProcessingStatus.PENDING,
                uploaded_by=current_user.id,
            )
            db.add(pdf_record)
            await db.flush()

            process_pdf.delay(str(pdf_record.id), object_key)

            results.append({
                "id": str(pdf_record.id),
                "filename": file.filename,
                "file_size": file_size,
                "status": pdf_record.status.value,
            })

        except Exception as e:
            if object_key in uploaded_keys:
                await cleanup_orphaned_file(object_key)
            errors.append({"filename": file.filename, "error": str(e)})

    try:
        await db.commit()
    except Exception as e:
        for key in uploaded_keys:
            await cleanup_orphaned_file(key)
        raise HTTPException(status_code=500, detail=str(e))

    return ApiResponse(
        success=True,
        data={
            "uploaded": results,
            "errors": errors,
        },
        message=f"Uploaded {len(results)} file(s)",
    )


# ------------------------------------------------------------------------------
# LIST DOCUMENTS
# ------------------------------------------------------------------------------
@router.get("")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(PDFMetadata)
        .where(PDFMetadata.uploaded_by == current_user.id)
        .order_by(PDFMetadata.created_at.desc())
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
            ]
        },
    )


# ------------------------------------------------------------------------------
# GET SINGLE DOCUMENT METADATA
# ------------------------------------------------------------------------------
@router.get("/{document_id}")
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        doc_uuid = uuid.UUID(document_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    result = await db.execute(
        select(PDFMetadata).where(
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


# ------------------------------------------------------------------------------
# DOWNLOAD PDF FILE
# ------------------------------------------------------------------------------
@router.get("/{document_id}/file")
async def get_document_file(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        doc_uuid = uuid.UUID(document_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    result = await db.execute(
        select(PDFMetadata).where(
            PDFMetadata.id == doc_uuid,
            PDFMetadata.uploaded_by == current_user.id,
        )
    )

    metadata = result.scalar_one_or_none()
    if not metadata:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        response = minio_client.get_object(settings.minio_bucket, metadata.object_key)
        pdf_bytes = response.read()
        response.close()
        response.release_conn()
    except:
        raise HTTPException(status_code=500, detail="Failed to fetch PDF")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{metadata.filename}"'
        },
    )


# ------------------------------------------------------------------------------
# DELETE SINGLE DOCUMENT (MinIO + Qdrant + DB)
# ------------------------------------------------------------------------------
@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        doc_uuid = uuid.UUID(document_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    result = await db.execute(
        select(PDFMetadata).where(
            PDFMetadata.id == doc_uuid,
            PDFMetadata.uploaded_by == current_user.id,
        )
    )

    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        delete_pdf_vectors(str(doc.id))
    except Exception as e:
        print("Qdrant cleanup failed:", e)

    try:
        minio_client.remove_object(settings.minio_bucket, doc.object_key)
    except:
        pass

    await db.delete(doc)
    await db.commit()

    return ApiResponse(success=True, message="Document deleted")


# ------------------------------------------------------------------------------
# DELETE ALL DOCUMENTS (USER)
# ------------------------------------------------------------------------------
@router.delete("")
async def delete_all_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(PDFMetadata).where(PDFMetadata.uploaded_by == current_user.id)
    )
    docs = result.scalars().all()

    for doc in docs:
        try:
            delete_pdf_vectors(str(doc.id))
        except Exception as e:
            print("Qdrant cleanup failed:", e)

        try:
            minio_client.remove_object(settings.minio_bucket, doc.object_key)
        except:
            pass

        await db.delete(doc)

    await db.commit()

    return ApiResponse(
        success=True,
        message=f"Deleted {len(docs)} document(s)",
    )
