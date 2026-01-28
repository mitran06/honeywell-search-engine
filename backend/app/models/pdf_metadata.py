import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import String, DateTime, Integer, Text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base



class ProcessingStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PDFMetadata(Base):
    __tablename__ = "pdf_metadata"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    object_key: Mapped[str] = mapped_column(
        String(500),
        unique=True,
        nullable=False,
    )
    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
    )
    page_count: Mapped[int] = mapped_column(
        nullable=True,
    )
    status: Mapped[ProcessingStatus] = mapped_column(
        SQLEnum(ProcessingStatus),
        default=ProcessingStatus.PENDING,
        nullable=False,
    )
    error_message: Mapped[str] = mapped_column(
        Text,
        nullable=True,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,  # Optional: link to user who uploaded
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )