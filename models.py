import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    MetaData,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID


metadata = MetaData()

resumes = Table(
    "resumes",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("filename", Text, nullable=False),
    Column("raw_text", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

parsed_fields = Table(
    "parsed_fields",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("resume_id", UUID(as_uuid=True), ForeignKey("resumes.id"), nullable=False),
    Column("name", Text, nullable=False),
    Column("email", Text, nullable=False),
    Column("skills", JSONB, nullable=False),
    Column("experience", JSONB, nullable=False),
    Column("education", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
