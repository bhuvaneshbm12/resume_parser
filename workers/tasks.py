import asyncio
import json
import logging
import os
import uuid

import asyncpg
import httpx
from celery import Celery
from celery.exceptions import SoftTimeLimitExceeded
from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import ValidationError

from schemas import ParsedResume


load_dotenv()

logger = logging.getLogger(__name__)
celery_app = Celery("resume_parser")
celery_app.config_from_object("workers.celery_config")

DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

SYSTEM_PROMPT = (
    "You are a resume parser. Extract structured data from the resume text provided. "
    "Return ONLY valid JSON with no explanation, no markdown, no backticks."
)

class GeminiRateLimitError(Exception):
    pass


class GeminiAPITimeoutError(Exception):
    pass


class GeminiServerError(Exception):
    pass


class gemini:
    RateLimitError = GeminiRateLimitError
    APITimeoutError = GeminiAPITimeoutError
    ServerError = GeminiServerError


USER_PROMPT = (
    "Extract this resume into a structured resume-parser JSON object. Return these "
    "top-level keys: name, email, phone, location, linkedin, github, summary, skills, "
    "experience, education, projects, certifications, awards, languages, identity, "
    "education_history, skills_grouped, positions_of_responsibility, extracurriculars, "
    "target_role, years_experience, ats_keyword_match_score, experience_level, "
    "domain_classification, missing_fields, contact_card, role_timeline, parser_flags.\n\n"
    "Rules:\n"
    "- Capture every visible resume detail in the closest matching field.\n"
    "- Do not invent facts. Use empty strings or empty arrays when data is missing.\n"
    "- identity must include name, student_id, institution, degree, stream, cgpa, graduation_year.\n"
    "- education_history must include school, board, score, year, and level for each listed level.\n"
    "- skills_grouped must include languages, frameworks_libraries, tools_platforms, soft_skills, proficiency_levels, ml_dl_frameworks, mlops_cloud_devops, data_viz, apis_web, other.\n"
    "- experience items must include company, role, duration, start_date, end_date, location, responsibilities, quantified_impact, employment_type, tech_stack, description.\n"
    "- education items must include institution, degree, field_of_study, year, start_year, end_year, score, board_university, achievements_honors, relevant_courses, location.\n"
    "- projects items must include title, name, type_domain, description, technologies, key_tools, performance_metrics, duration, github_url, live_url, team_size, link.\n"
    "- positions_of_responsibility items must include role, organization, duration, key_impact_numbers, impact_scale, volunteering, sports_extracurricular, description.\n"
    "- certifications items must include name, issuer, year, issue_date, credential_id_url, expiry_date.\n"
    "- awards and languages must be arrays of strings.\n"
    "- extracurriculars must be a brief array of strings.\n"
    "- missing_fields must list missing must/good/optional fields with field, tier, message.\n"
    "- parser_flags must include gaps such as missing summary, missing links, missing quantified metrics, skills used in projects but absent from skills, employment gaps, and domain mismatch when visible.\n"
    "- ats_keyword_match_score should be a 0-100 string estimate based only on the resume content.\n"
    "- experience_level should be Junior, Mid, Senior, Student, or Unknown.\n"
    "- domain_classification should classify the resume domain such as ML, Web, Data, Finance, or General.\n"
    "Return only JSON."
)

SECTION_ALIASES = {
    "contact": {"contact", "personal details", "personal info", "header"},
    "summary": {"summary", "profile", "about", "objective"},
    "skills": {"skills", "technical skills", "core skills", "skill set"},
    "experience": {"experience", "work experience", "employment", "professional experience"},
    "education": {"education", "academic background", "academics"},
    "projects": {"projects", "project experience", "selected projects"},
    "certifications": {"certifications", "certificate", "certificates"},
    "awards": {"awards", "achievements", "honors", "honours"},
    "languages": {"languages", "language proficiency"},
}


def build_sectioned_resume_text(raw_text: str) -> str:
    lines = [line.rstrip() for line in raw_text.splitlines()]
    sections: list[tuple[str, list[str]]] = []
    current_section = "other"
    current_lines: list[str] = []

    def flush_section() -> None:
        nonlocal current_lines, current_section
        content = [line for line in current_lines if line.strip()]
        if content:
            sections.append((current_section, content))
        current_lines = []

    for line in lines:
        normalized = line.strip().lower().rstrip(":")
        matched_section = None
        for section_name, aliases in SECTION_ALIASES.items():
            if normalized in aliases:
                matched_section = section_name
                break

        if matched_section is not None:
            flush_section()
            current_section = matched_section
            continue

        current_lines.append(line)

    flush_section()

    if not sections:
        return raw_text.strip()

    formatted_sections = []
    for section_name, content_lines in sections:
        formatted_sections.append(f"[{section_name.upper()}]\n" + "\n".join(content_lines).strip())

    return "\n\n".join(formatted_sections).strip()


def require_database_url() -> str:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return DATABASE_URL


def require_gemini_api_key() -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set")
    return GEMINI_API_KEY


def strip_json_code_fence(content: str) -> str:
    stripped = content.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if len(lines) < 2 or not lines[-1].strip().startswith("```"):
        return stripped

    return "\n".join(lines[1:-1]).strip()


def coerce_string_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, dict):
        items: list[str] = []
        for nested_value in value.values():
            items.extend(coerce_string_list(nested_value))
        return items
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(value).strip()] if str(value).strip() else []


def coerce_dict_list(value) -> list[dict]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item if isinstance(item, dict) else {"name": str(item)} for item in value]
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str) and value.strip():
        return [{"name": value.strip()}]
    return []


def coerce_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def coerce_string(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    return str(value)


def coerce_string_dict(value) -> dict[str, str]:
    raw = coerce_dict(value)
    return {str(key): coerce_string(item) for key, item in raw.items()}


def coerce_string_fields(item: dict, fields: tuple[str, ...]) -> None:
    for field in fields:
        item[field] = coerce_string(item.get(field))


def normalize_resume_payload(payload: dict) -> dict:
    for key in (
        "name",
        "email",
        "phone",
        "location",
        "linkedin",
        "github",
        "summary",
        "target_role",
        "years_experience",
        "ats_keyword_match_score",
        "experience_level",
        "domain_classification",
    ):
        payload[key] = coerce_string(payload.get(key))

    payload["skills"] = coerce_string_list(payload.get("skills"))
    payload["awards"] = coerce_string_list(payload.get("awards"))
    payload["languages"] = coerce_string_list(payload.get("languages"))

    for key in ("experience", "education", "projects", "certifications"):
        if payload.get(key) is None:
            payload[key] = []

    payload["experience"] = coerce_dict_list(payload.get("experience"))
    payload["education"] = coerce_dict_list(payload.get("education"))
    payload["projects"] = coerce_dict_list(payload.get("projects"))
    payload["certifications"] = coerce_dict_list(payload.get("certifications"))
    payload["education_history"] = coerce_dict_list(payload.get("education_history"))
    payload["positions_of_responsibility"] = coerce_dict_list(
        payload.get("positions_of_responsibility")
    )

    for project in payload["projects"]:
        coerce_string_fields(
            project,
            (
                "name",
                "title",
                "type_domain",
                "description",
                "duration",
                "github_url",
                "live_url",
                "team_size",
                "link",
            ),
        )
        project["technologies"] = coerce_string_list(project.get("technologies"))
        project["key_tools"] = coerce_string_list(project.get("key_tools"))
        project["performance_metrics"] = coerce_string_list(project.get("performance_metrics"))
        if not project.get("name") and project.get("title"):
            project["name"] = project["title"]
        if not project.get("title") and project.get("name"):
            project["title"] = project["name"]

    for position in payload["positions_of_responsibility"]:
        coerce_string_fields(
            position,
            ("role", "organization", "duration", "description"),
        )
        position["key_impact_numbers"] = coerce_string_list(position.get("key_impact_numbers"))
        position["impact_scale"] = coerce_string_list(position.get("impact_scale"))
        position["volunteering"] = coerce_string(position.get("volunteering"))
        position["sports_extracurricular"] = coerce_string(position.get("sports_extracurricular"))

    identity = coerce_dict(payload.get("identity"))
    payload["identity"] = {
        "name": coerce_string(identity.get("name") or payload.get("name")),
        "student_id": coerce_string(identity.get("student_id") or identity.get("id")),
        "institution": coerce_string(identity.get("institution")),
        "degree": coerce_string(identity.get("degree")),
        "stream": coerce_string(identity.get("stream")),
        "cgpa": coerce_string(identity.get("cgpa")),
        "graduation_year": coerce_string(identity.get("graduation_year") or identity.get("year")),
    }

    skills_grouped = coerce_dict(payload.get("skills_grouped"))
    payload["skills_grouped"] = {
        "languages": coerce_string_list(skills_grouped.get("languages")),
        "frameworks_libraries": coerce_string_list(skills_grouped.get("frameworks_libraries")),
        "tools_platforms": coerce_string_list(skills_grouped.get("tools_platforms")),
        "soft_skills": coerce_string_list(skills_grouped.get("soft_skills")),
        "proficiency_levels": coerce_string_dict(skills_grouped.get("proficiency_levels")),
        "ml_dl_frameworks": coerce_string_list(skills_grouped.get("ml_dl_frameworks")),
        "mlops_cloud_devops": coerce_string_list(skills_grouped.get("mlops_cloud_devops")),
        "data_viz": coerce_string_list(skills_grouped.get("data_viz")),
        "apis_web": coerce_string_list(skills_grouped.get("apis_web")),
        "other": coerce_string_list(skills_grouped.get("other")),
    }
    contact_card = coerce_dict(payload.get("contact_card"))
    payload["contact_card"] = {
        "full_name": coerce_string(contact_card.get("full_name") or payload.get("name")),
        "email": coerce_string(contact_card.get("email") or payload.get("email")),
        "phone": coerce_string(contact_card.get("phone") or payload.get("phone")),
        "location": coerce_string(contact_card.get("location") or payload.get("location")),
        "linkedin": coerce_string(contact_card.get("linkedin") or payload.get("linkedin")),
        "github_portfolio": coerce_string(
            contact_card.get("github_portfolio")
        or contact_card.get("github")
        or payload.get("github")
        ),
    }
    payload["extracurriculars"] = coerce_string_list(payload.get("extracurriculars"))
    payload["parser_flags"] = coerce_string_list(payload.get("parser_flags"))
    payload["missing_fields"] = coerce_dict_list(payload.get("missing_fields"))
    payload["role_timeline"] = coerce_dict_list(payload.get("role_timeline"))

    for experience in payload["experience"]:
        coerce_string_fields(
            experience,
            (
                "company",
                "role",
                "duration",
                "start_date",
                "end_date",
                "location",
                "employment_type",
                "description",
            ),
        )
        experience["responsibilities"] = coerce_string_list(experience.get("responsibilities"))
        experience["quantified_impact"] = coerce_string_list(experience.get("quantified_impact"))
        experience["tech_stack"] = coerce_string_list(experience.get("tech_stack"))

    for education in payload["education"]:
        coerce_string_fields(
            education,
            (
                "institution",
                "degree",
                "field_of_study",
                "year",
                "start_year",
                "end_year",
                "score",
                "board_university",
                "location",
            ),
        )
        education["achievements_honors"] = coerce_string_list(education.get("achievements_honors"))
        education["relevant_courses"] = coerce_string_list(education.get("relevant_courses"))

    for education_item in payload["education_history"]:
        coerce_string_fields(education_item, ("level", "school", "board", "score", "year"))

    for certification in payload["certifications"]:
        coerce_string_fields(
            certification,
            ("name", "issuer", "year", "issue_date", "credential_id_url", "expiry_date"),
        )

    for missing_field in payload["missing_fields"]:
        coerce_string_fields(missing_field, ("field", "tier", "message"))

    for role in payload["role_timeline"]:
        coerce_string_fields(role, ("title", "organization", "start_date", "end_date", "type"))

    return payload


def parse_with_gemini(raw_text: str) -> dict:
    client = genai.Client(api_key=require_gemini_api_key())
    sectioned_text = build_sectioned_resume_text(raw_text)
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=f"{USER_PROMPT}\n\nResume sections:\n{sectioned_text}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                system_instruction=SYSTEM_PROMPT,
            ),
        )
    except genai_errors.ClientError as exc:
        if getattr(exc, "code", None) == 429 or getattr(exc, "status_code", None) == 429:
            raise gemini.RateLimitError(str(exc)) from exc
        raise
    except genai_errors.ServerError as exc:
        raise gemini.ServerError(str(exc)) from exc
    except (httpx.TimeoutException, TimeoutError) as exc:
        raise gemini.APITimeoutError(str(exc)) from exc

    content = response.text
    if not content:
        raise ValueError("Gemini returned an empty response")

    return normalize_resume_payload(json.loads(strip_json_code_fence(content)))


def is_retryable_llm_error(exc: Exception) -> bool:
    if isinstance(exc, (gemini.RateLimitError, gemini.APITimeoutError, gemini.ServerError)):
        return True
    return False


async def set_resume_status(
    connection: asyncpg.Connection,
    resume_id: uuid.UUID,
    status: str,
) -> None:
    await connection.execute(
        "UPDATE resumes SET status = $1, updated_at = NOW() WHERE id = $2",
        status,
        resume_id,
    )


async def mark_resume_failed(resume_id: uuid.UUID, error_message: str) -> None:
    connection = await asyncpg.connect(dsn=require_database_url())
    try:
        await set_resume_status(connection, resume_id, "failed")
        logger.error(
            "Resume parsing task failed for resume_id=%s error=%s",
            resume_id,
            error_message,
        )
    finally:
        await connection.close()


async def run_parse_resume(resume_id: uuid.UUID, retry_count: int = 0) -> None:
    logger.info("Starting resume parsing task resume_id=%s retry=%s", resume_id, retry_count)
    connection = await asyncpg.connect(dsn=require_database_url())
    try:
        row = await connection.fetchrow(
            "SELECT raw_text FROM resumes WHERE id = $1",
            resume_id,
        )
        if row is None:
            raise ValueError(f"Resume {resume_id} was not found")

        await set_resume_status(connection, resume_id, "processing")

        try:
            payload = parse_with_gemini(row["raw_text"])
        except Exception as exc:
            if is_retryable_llm_error(exc):
                logger.warning(
                    "Retryable LLM failure for resume_id=%s retry=%s error=%s",
                    resume_id,
                    retry_count,
                    exc,
                )
                raise
            raise

        try:
            parsed = ParsedResume.model_validate(payload)
        except ValidationError:
            await set_resume_status(connection, resume_id, "failed")
            logger.exception("Gemini response validation failed for resume_id=%s", resume_id)
            return

        experience = [item.model_dump() for item in parsed.experience]
        education = [item.model_dump() for item in parsed.education]
        projects = [item.model_dump() for item in parsed.projects]
        certifications = [item.model_dump() for item in parsed.certifications]
        education_history = [item.model_dump() for item in parsed.education_history]
        positions_of_responsibility = [
            item.model_dump() for item in parsed.positions_of_responsibility
        ]
        missing_fields = [item.model_dump() for item in parsed.missing_fields]
        role_timeline = [item.model_dump() for item in parsed.role_timeline]

        await connection.execute(
            """
            INSERT INTO parsed_fields (
                id,
                resume_id,
                name,
                email,
                phone,
                location,
                linkedin,
                github,
                summary,
                target_role,
                years_experience,
                ats_keyword_match_score,
                experience_level,
                domain_classification,
                skills,
                experience,
                education,
                projects,
                certifications,
                awards,
                languages,
                identity,
                education_history,
                skills_grouped,
                positions_of_responsibility,
                extracurriculars,
                missing_fields,
                contact_card,
                role_timeline,
                parser_flags
            )
            VALUES (
                $1,
                $2,
                $3,
                $4,
                $5,
                $6,
                $7,
                $8,
                $9,
                $10,
                $11,
                $12,
                $13,
                $14,
                $15::jsonb,
                $16::jsonb,
                $17::jsonb,
                $18::jsonb,
                $19::jsonb,
                $20::jsonb,
                $21::jsonb,
                $22::jsonb,
                $23::jsonb,
                $24::jsonb,
                $25::jsonb,
                $26::jsonb,
                $27::jsonb,
                $28::jsonb,
                $29::jsonb,
                $30::jsonb
            )
            """,
            uuid.uuid4(),
            resume_id,
            parsed.name,
            parsed.email,
            parsed.phone,
            parsed.location,
            parsed.linkedin,
            parsed.github,
            parsed.summary,
            parsed.target_role,
            parsed.years_experience,
            parsed.ats_keyword_match_score,
            parsed.experience_level,
            parsed.domain_classification,
            json.dumps(parsed.skills),
            json.dumps(experience),
            json.dumps(education),
            json.dumps(projects),
            json.dumps(certifications),
            json.dumps(parsed.awards),
            json.dumps(parsed.languages),
            json.dumps(parsed.identity.model_dump()),
            json.dumps(education_history),
            json.dumps(parsed.skills_grouped.model_dump()),
            json.dumps(positions_of_responsibility),
            json.dumps(parsed.extracurriculars),
            json.dumps(missing_fields),
            json.dumps(parsed.contact_card.model_dump()),
            json.dumps(role_timeline),
            json.dumps(parsed.parser_flags),
        )
        await set_resume_status(connection, resume_id, "done")
        logger.info("Completed resume parsing task resume_id=%s", resume_id)
    except Exception as exc:
        if is_retryable_llm_error(exc):
            if retry_count < 3:
                logger.warning(
                    "Retrying resume parsing task resume_id=%s retry=%s error=%s",
                    resume_id,
                    retry_count + 1,
                    exc,
                )
                raise
            await set_resume_status(connection, resume_id, "failed")
            logger.exception("Resume parsing task failed after retries resume_id=%s", resume_id)
            raise

        await set_resume_status(connection, resume_id, "failed")
        logger.exception("Resume parsing task failed for resume_id=%s", resume_id)
        raise
    finally:
        await connection.close()


@celery_app.task(
    bind=True,
    name="workers.tasks.parse_resume_task",
    autoretry_for=(gemini.RateLimitError, gemini.APITimeoutError, gemini.ServerError),
    max_retries=3,
    retry_backoff=10,
    soft_time_limit=60,
    time_limit=70,
)
def parse_resume_task(self, resume_id: str) -> None:
    parsed_resume_id = uuid.UUID(resume_id)
    try:
        asyncio.run(run_parse_resume(parsed_resume_id, self.request.retries))
    except SoftTimeLimitExceeded:
        asyncio.run(mark_resume_failed(parsed_resume_id, "timeout"))
        raise
