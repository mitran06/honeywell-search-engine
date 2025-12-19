import uuid
from sqlalchemy import Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
from sqlalchemy import text


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

    page_num: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

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