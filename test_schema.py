from pydantic import ValidationError

from schemas import ParsedResume


SAMPLE_JSON = {
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "123-456-7890",
    "location": "Bengaluru, India",
    "linkedin": "https://linkedin.com/in/johndoe",
    "github": "https://github.com/johndoe",
    "summary": "Backend engineer focused on APIs and automation.",
    "skills": ["Python", "FastAPI"],
    "experience": [
        {
            "company": "Google",
            "role": "Engineer",
            "duration": "2 years",
            "location": "Hyderabad",
            "description": "Built internal tools.",
        }
    ],
    "education": [
        {
            "institution": "MIT",
            "degree": "BSc Computer Science",
            "year": "2020",
            "location": "Cambridge",
        }
    ],
    "projects": [
        {
            "name": "Resume Parser",
            "description": "Parsed structured resume data.",
            "technologies": ["FastAPI", "Gemini"],
            "link": "https://example.com",
        }
    ],
    "certifications": [
        {
            "name": "Cloud Developer",
            "issuer": "Google",
            "year": "2024",
        }
    ],
    "awards": ["Dean's List"],
    "languages": ["English", "Hindi"],
}


def main() -> None:
    try:
        ParsedResume.model_validate(SAMPLE_JSON)
    except ValidationError as exc:
        print(exc)
        return

    print("OK")


if __name__ == "__main__":
    main()
