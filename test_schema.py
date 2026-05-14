from pydantic import ValidationError

from schemas import ParsedResume


SAMPLE_JSON = {
    "name": "John Doe",
    "email": "john@example.com",
    "skills": ["Python", "FastAPI"],
    "experience": [
        {
            "company": "Google",
            "role": "Engineer",
            "duration": "2 years",
        }
    ],
    "education": [
        {
            "institution": "MIT",
            "degree": "BSc Computer Science",
            "year": "2020",
        }
    ],
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
