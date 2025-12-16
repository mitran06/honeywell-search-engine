import uuid
from enum import Enum
from sqlalchemy import Integer, Text, ForeignKey, Boolean, String, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
from sqlalchemy import text


class ChunkType(str, Enum):
    """Chunk hierarchy type for parent-child chunking strategy."""
    PARENT = "PARENT"   # Large context chunks (500+ words) for display/reranking
    CHILD = "CHILD"     # Small chunks (100-150 words) for vector search


class PDFChunk(Base):
    __tablename__ = "pdf_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    pdf_metadata_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pdf_metadata.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Parent-child relationship: child chunks link to their parent
    parent_chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pdf_chunks.id", ondelete="CASCADE"),
        nullable=True,  # NULL for parent chunks
        index=True
    )

    chunk_type: Mapped[ChunkType] = mapped_column(
        SQLEnum(ChunkType),
        default=ChunkType.CHILD,
        nullable=False
    )

    page_num: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    # For parents: sequential index of parent chunk
    # For children: index within the parent
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    chunk_text: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    length_chars: Mapped[int] = mapped_column(
        Integer,
        nullable=True
    )

    # Accurate token count using model tokenizer
    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=True
    )

    embedded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false")
    )
