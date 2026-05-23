const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type ExperienceItem = {
  company?: string;
  role?: string;
  duration?: string;
  start_date?: string;
  end_date?: string;
  location?: string;
  responsibilities?: string[];
  quantified_impact?: string[];
  employment_type?: string;
  tech_stack?: string[];
  description?: string;
};

export type EducationItem = {
  institution?: string;
  degree?: string;
  field_of_study?: string;
  year?: string;
  start_year?: string;
  end_year?: string;
  score?: string;
  board_university?: string;
  achievements_honors?: string[];
  relevant_courses?: string[];
  location?: string;
};

export type ProjectItem = {
  name?: string;
  title?: string;
  type_domain?: string;
  description?: string;
  technologies?: string[];
  key_tools?: string[];
  performance_metrics?: string[];
  duration?: string;
  github_url?: string;
  live_url?: string;
  team_size?: string;
  link?: string;
};

export type CertificationItem = {
  name?: string;
  issuer?: string;
  year?: string;
  issue_date?: string;
  credential_id_url?: string;
  expiry_date?: string;
};

export type Identity = {
  name?: string;
  student_id?: string;
  institution?: string;
  degree?: string;
  stream?: string;
  cgpa?: string;
  graduation_year?: string;
};

export type EducationHistoryItem = {
  level?: string;
  school?: string;
  board?: string;
  score?: string;
  year?: string;
};

export type SkillGroups = {
  languages?: string[];
  frameworks_libraries?: string[];
  tools_platforms?: string[];
  soft_skills?: string[];
  proficiency_levels?: Record<string, string>;
  ml_dl_frameworks?: string[];
  mlops_cloud_devops?: string[];
  data_viz?: string[];
  apis_web?: string[];
  other?: string[];
};

export type PositionOfResponsibilityItem = {
  role?: string;
  organization?: string;
  duration?: string;
  key_impact_numbers?: string[];
  impact_scale?: string[];
  volunteering?: string;
  sports_extracurricular?: string;
  description?: string;
};

export type ContactCard = {
  full_name?: string;
  email?: string;
  phone?: string;
  location?: string;
  linkedin?: string;
  github_portfolio?: string;
};

export type RoleTimelineItem = {
  title?: string;
  organization?: string;
  start_date?: string;
  end_date?: string;
  type?: string;
};

export type MissingFieldAlert = {
  field?: string;
  tier?: string;
  message?: string;
};

export type ParsedResumeResult = {
  status: string;
  name?: string;
  email?: string;
  phone?: string;
  location?: string;
  linkedin?: string;
  github?: string;
  summary?: string;
  target_role?: string;
  years_experience?: string;
  ats_keyword_match_score?: string;
  experience_level?: string;
  domain_classification?: string;
  skills?: string[] | string;
  experience?: ExperienceItem[];
  education?: EducationItem[];
  projects?: ProjectItem[];
  certifications?: CertificationItem[];
  awards?: string[];
  languages?: string[];
  identity?: Identity;
  education_history?: EducationHistoryItem[];
  skills_grouped?: SkillGroups;
  positions_of_responsibility?: PositionOfResponsibilityItem[];
  extracurriculars?: string[];
  missing_fields?: MissingFieldAlert[];
  contact_card?: ContactCard;
  role_timeline?: RoleTimelineItem[];
  parser_flags?: string[];
};

export async function uploadResume(file: File): Promise<{ task_id: string }> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_URL}/parse`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    if (response.status === 413) {
      throw new Error("File too large");
    }
    if (response.status === 415) {
      throw new Error("Only PDFs accepted");
    }
    throw new Error("Upload failed");
  }

  return response.json();
}

export async function getResults(taskId: string): Promise<ParsedResumeResult> {
  const response = await fetch(`${API_URL}/results/${encodeURIComponent(taskId)}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Result not found");
    }
    throw new Error("Could not load results");
  }

  return response.json();
}
