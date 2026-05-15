import json
import uuid
from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from PyPDF2 import PdfReader
from asyncpg import Connection

from database import get_connection
from workers.tasks import parse_resume_task


router = APIRouter()


def decode_jsonb(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


def extract_pdf_text(contents: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(contents))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not extract text from PDF",
        ) from exc


@router.post("/parse", status_code=status.HTTP_202_ACCEPTED)
async def parse_resume(
    file: UploadFile | None = File(None),
    connection: Connection = Depends(get_connection),
) -> dict[str, str]:
    if file is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="no file provided",
        )

    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF uploads are supported",
        )

    contents = await file.read()
    raw_text = extract_pdf_text(contents)
    if len(raw_text) < 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="the PDF could not be read",
        )

    resume_id = uuid.uuid4()
    await connection.execute(
        """
        INSERT INTO resumes (id, filename, raw_text, status)
        VALUES ($1, $2, $3, $4)
        """,
        resume_id,
        file.filename or "resume.pdf",
        raw_text,
        "pending",
    )

    parse_resume_task.delay(str(resume_id))
    return {"task_id": str(resume_id)}


@router.get("/results/{task_id}")
async def get_results(
    task_id: uuid.UUID,
    connection: Connection = Depends(get_connection),
) -> dict:
    resume = await connection.fetchrow(
        "SELECT status FROM resumes WHERE id = $1",
        task_id,
    )

    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")

    if resume["status"] != "done":
        return {"status": resume["status"]}

    row = await connection.fetchrow(
        """
        SELECT
            r.status,
            p.name,
            p.email,
            p.skills,
            p.experience,
            p.education
        FROM resumes r
        JOIN parsed_fields p ON p.resume_id = r.id
        WHERE r.id = $1
        """,
        task_id,
    )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parsed fields not found",
        )

    return {
        "status": row["status"],
        "name": row["name"],
        "email": row["email"],
        "skills": decode_jsonb(row["skills"]),
        "experience": decode_jsonb(row["experience"]),
        "education": decode_jsonb(row["education"]),
    }
