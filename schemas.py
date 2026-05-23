from pydantic import BaseModel, ConfigDict, Field


class ExperienceItem(BaseModel):
    company: str = ""
    role: str = ""
    duration: str = ""
    start_date: str = ""
    end_date: str = ""
    location: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    quantified_impact: list[str] = Field(default_factory=list)
    employment_type: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    description: str = ""


class EducationItem(BaseModel):
    institution: str = ""
    degree: str = ""
    field_of_study: str = ""
    year: str = ""
    start_year: str = ""
    end_year: str = ""
    score: str = ""
    board_university: str = ""
    achievements_honors: list[str] = Field(default_factory=list)
    relevant_courses: list[str] = Field(default_factory=list)
    location: str = ""


class ProjectItem(BaseModel):
    name: str = ""
    title: str = ""
    type_domain: str = ""
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    key_tools: list[str] = Field(default_factory=list)
    performance_metrics: list[str] = Field(default_factory=list)
    duration: str = ""
    github_url: str = ""
    live_url: str = ""
    team_size: str = ""
    link: str = ""


class CertificationItem(BaseModel):
    name: str = ""
    issuer: str = ""
    year: str = ""
    issue_date: str = ""
    credential_id_url: str = ""
    expiry_date: str = ""


class Identity(BaseModel):
    name: str = ""
    student_id: str = ""
    institution: str = ""
    degree: str = ""
    stream: str = ""
    cgpa: str = ""
    graduation_year: str = ""


class EducationHistoryItem(BaseModel):
    level: str = ""
    school: str = ""
    board: str = ""
    score: str = ""
    year: str = ""


class SkillGroups(BaseModel):
    languages: list[str] = Field(default_factory=list)
    frameworks_libraries: list[str] = Field(default_factory=list)
    tools_platforms: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    proficiency_levels: dict[str, str] = Field(default_factory=dict)
    ml_dl_frameworks: list[str] = Field(default_factory=list)
    mlops_cloud_devops: list[str] = Field(default_factory=list)
    data_viz: list[str] = Field(default_factory=list)
    apis_web: list[str] = Field(default_factory=list)
    other: list[str] = Field(default_factory=list)


class PositionOfResponsibilityItem(BaseModel):
    role: str = ""
    organization: str = ""
    duration: str = ""
    key_impact_numbers: list[str] = Field(default_factory=list)
    impact_scale: list[str] = Field(default_factory=list)
    volunteering: str = ""
    sports_extracurricular: str = ""
    description: str = ""


class ContactCard(BaseModel):
    full_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github_portfolio: str = ""


class RoleTimelineItem(BaseModel):
    title: str = ""
    organization: str = ""
    start_date: str = ""
    end_date: str = ""
    type: str = ""


class MissingFieldAlert(BaseModel):
    field: str = ""
    tier: str = ""
    message: str = ""


class ParsedResume(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    email: str
    phone: str
    location: str
    linkedin: str
    github: str
    summary: str
    skills: list[str]
    experience: list[ExperienceItem]
    education: list[EducationItem]
    projects: list[ProjectItem]
    certifications: list[CertificationItem]
    awards: list[str]
    languages: list[str]
    identity: Identity = Field(default_factory=Identity)
    education_history: list[EducationHistoryItem] = Field(default_factory=list)
    skills_grouped: SkillGroups = Field(default_factory=SkillGroups)
    positions_of_responsibility: list[PositionOfResponsibilityItem] = Field(default_factory=list)
    extracurriculars: list[str] = Field(default_factory=list)
    target_role: str = ""
    years_experience: str = ""
    ats_keyword_match_score: str = ""
    experience_level: str = ""
    domain_classification: str = ""
    missing_fields: list[MissingFieldAlert] = Field(default_factory=list)
    contact_card: ContactCard = Field(default_factory=ContactCard)
    role_timeline: list[RoleTimelineItem] = Field(default_factory=list)
    parser_flags: list[str] = Field(default_factory=list)
