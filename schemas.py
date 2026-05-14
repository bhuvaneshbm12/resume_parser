from pydantic import BaseModel, ConfigDict


class ParsedResume(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    email: str
    skills: list[str]
    experience: list[dict]
    education: list[dict]
