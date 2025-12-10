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
    """Ensure the MinIO bucket exists, create if it doesn't."""
    try:
        if not minio_client.bucket_exists(settings.minio_bucket):
            minio_client.make_bucket(settings.minio_bucket)
    except S3Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize storage: {str(e)}"
        )


async def cleanup_orphaned_file(object_key: str):
    """Remove file from MinIO if database insert fails."""
    try:
        minio_client.remove_object(settings.minio_bucket, object_key)
    except S3Error:
        pass  # Best effort cleanup


@router.post("/upload")
async def upload_pdfs(
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload PDF files to storage and save metadata. Requires authentication."""
    ensure_bucket_exists()
    
    results = []
    errors = []
    uploaded_keys = []  # Track uploaded files for potential rollback

    for file in files:
        # Validate file type
        if not file.filename or not file.filename.lower().endswith('.pdf'):
            errors.append({
                "filename": file.filename or "unknown",
                "error": "Only PDF files are allowed"
            })
            continue
        
        object_key = f"{uuid.uuid4()}_{file.filename}"
        
        try:
            # Get file size
            file.file.seek(0, 2)  # Seek to end
            file_size = file.file.tell()
            file.file.seek(0)  # Reset to beginning

            # Upload to MinIO
            minio_client.put_object(
                settings.minio_bucket,
                object_key,
                file.file,
                length=file_size,
                content_type="application/pdf",
            )
            uploaded_keys.append(object_key)

            # Create database record using SQLAlchemy model
            # Link to authenticated user
            pdf_record = PDFMetadata(
                filename=file.filename,
                object_key=object_key,
                file_size=file_size,
                status=ProcessingStatus.PENDING,
                uploaded_by=current_user.id,
            )
            db.add(pdf_record)
            await db.flush()  # Get the ID

            results.append({
                "id": str(pdf_record.id),
                "filename": file.filename,
                "object_key": object_key,
                "file_size": file_size,
                "status": pdf_record.status.value,
            })
            
        except S3Error as e:
            errors.append({
                "filename": file.filename,
                "error": f"Storage error: {str(e)}"
            })
        except Exception as e:
            # If DB insert fails after MinIO upload, cleanup the orphaned file
            if object_key in uploaded_keys:
                await cleanup_orphaned_file(object_key)
                uploaded_keys.remove(object_key)
            errors.append({
                "filename": file.filename,
                "error": str(e)
            })

    # Commit all successful records
    try:
        await db.commit()
    except Exception as e:
        # If commit fails, cleanup all uploaded files
        for key in uploaded_keys:
            await cleanup_orphaned_file(key)
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )

    return ApiResponse(
        success=len(results) > 0,
        data={
            "uploaded": results,
            "errors": errors,
            "total_uploaded": len(results),
            "total_errors": len(errors),
        },
        message=f"Uploaded {len(results)} file(s)" + (f", {len(errors)} failed" if errors else "")
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
                    "status": doc.status.value,
                    "created_at": doc.created_at.isoformat(),
                }
                for doc in documents
            ],
            "total": len(documents),
        },
        message=None
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
            PDFMetadata.uploaded_by == current_user.id
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
            "status": document.status.value,
            "error_message": document.error_message,
            "created_at": document.created_at.isoformat(),
            "updated_at": document.updated_at.isoformat(),
        },
        message=None
    )


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
            PDFMetadata.uploaded_by == current_user.id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete from MinIO first
    try:
        minio_client.remove_object(settings.minio_bucket, document.object_key)
    except S3Error:
        pass  # Object might already be deleted
    
    # Delete from database
    await db.delete(document)
    await db.commit()
    
    return ApiResponse(
        success=True,
        data=None,
        message="Document deleted successfully"
    )
