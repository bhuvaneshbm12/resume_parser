import os

from dotenv import load_dotenv
from google import genai
from google.genai import types


SYSTEM_PROMPT = (
    "You are a resume parser. Extract structured data from the resume text provided. "
    "Return ONLY valid JSON with no explanation, no markdown, no backticks."
)
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

SAMPLE_RESUME = """
Jane Doe
jane.doe@example.com
123-456-7890
New Delhi, India
https://linkedin.com/in/janedoe
https://github.com/janedoe

Summary
Backend engineer who builds resume processing and document automation systems.

Skills
Python, FastAPI, PostgreSQL, Docker, Celery, Redis, Machine Learning

Experience
Acme Analytics - Backend Engineer - January 2022 to Present
New Delhi
Built FastAPI services for document processing workflows and optimized Postgres queries.

Bright Data Labs - Software Intern - June 2021 to December 2021
Bengaluru
Created Python ETL scripts and deployed worker jobs with Celery and Redis.

Education
Indian Institute of Technology Madras - B.Tech in Computer Science - 2021

Projects
Resume Parser - Extracted structured resume data with FastAPI and Gemini.

Certifications
Google Cloud Professional Cloud Developer - Google - 2024

Awards
Dean's List, Hackathon Winner

Languages
English, Hindi
"""


def main() -> None:
    load_dotenv()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set")

    client = genai.Client(api_key=api_key)
    sectioned_resume = build_sectioned_resume_text(SAMPLE_RESUME)
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        contents=f"{USER_PROMPT}\n\nResume sections:\n{sectioned_resume}",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            system_instruction=SYSTEM_PROMPT,
        ),
    )

    print(response.text)


if __name__ == "__main__":
    main()
