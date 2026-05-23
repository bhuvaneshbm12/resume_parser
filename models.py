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
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

parsed_fields = Table(
    "parsed_fields",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("resume_id", UUID(as_uuid=True), ForeignKey("resumes.id"), nullable=False),
    Column("name", Text, nullable=False),
    Column("email", Text, nullable=False),
    Column("phone", Text, nullable=False),
    Column("location", Text, nullable=False),
    Column("linkedin", Text, nullable=False),
    Column("github", Text, nullable=False),
    Column("summary", Text, nullable=False),
    Column("target_role", Text, nullable=False),
    Column("years_experience", Text, nullable=False),
    Column("ats_keyword_match_score", Text, nullable=False),
    Column("experience_level", Text, nullable=False),
    Column("domain_classification", Text, nullable=False),
    Column("skills", JSONB, nullable=False),
    Column("experience", JSONB, nullable=False),
    Column("education", JSONB, nullable=False),
    Column("projects", JSONB, nullable=False),
    Column("certifications", JSONB, nullable=False),
    Column("awards", JSONB, nullable=False),
    Column("languages", JSONB, nullable=False),
    Column("identity", JSONB, nullable=False),
    Column("education_history", JSONB, nullable=False),
    Column("skills_grouped", JSONB, nullable=False),
    Column("positions_of_responsibility", JSONB, nullable=False),
    Column("extracurriculars", JSONB, nullable=False),
    Column("missing_fields", JSONB, nullable=False),
    Column("contact_card", JSONB, nullable=False),
    Column("role_timeline", JSONB, nullable=False),
    Column("parser_flags", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
