import os

from dotenv import load_dotenv
from google import genai
from google.genai import types


SYSTEM_PROMPT = (
    "You are a resume parser. Extract structured data from the resume text provided. "
    "Return ONLY valid JSON with no explanation, no markdown, no backticks."
)
USER_PROMPT = (
    "Extract the following fields from this resume: name (string), email (string), "
    "skills (array of strings), experience (array of objects with keys: company, "
    "role, duration), education (array of objects with keys: institution, degree, year). "
    "If a string field is missing, use an empty string. If an array field is missing, "
    "use an empty array. Return only JSON."
)

SAMPLE_RESUME = """
Jane Doe
jane.doe@example.com

Skills
Python, FastAPI, PostgreSQL, Docker, Celery, Redis, Machine Learning

Experience
Acme Analytics - Backend Engineer - January 2022 to Present
Built FastAPI services for document processing workflows and optimized Postgres queries.

Bright Data Labs - Software Intern - June 2021 to December 2021
Created Python ETL scripts and deployed worker jobs with Celery and Redis.

Education
Indian Institute of Technology Madras - B.Tech in Computer Science - 2021
"""


def main() -> None:
    load_dotenv()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        contents=f"{USER_PROMPT}\n\nResume text:\n{SAMPLE_RESUME}",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            system_instruction=SYSTEM_PROMPT,
        ),
    )

    print(response.text)


if __name__ == "__main__":
    main()
