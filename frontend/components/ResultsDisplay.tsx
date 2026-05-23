"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { DownloadIcon, ExternalLinkIcon, LinkIcon, MailIcon, MapPinIcon, PhoneIcon } from "lucide-react";
import {
  EducationHistoryItem,
  EducationItem,
  ExperienceItem,
  getResults,
  ParsedResumeResult,
  PositionOfResponsibilityItem,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";

type ResultsDisplayProps = {
  taskId: string;
};

export default function ResultsDisplay({ taskId }: ResultsDisplayProps) {
  const router = useRouter();
  const [result, setResult] = useState<ParsedResumeResult | null>(null);
  const [hasFailed, setHasFailed] = useState(false);
  const normalizedTaskId = typeof taskId === "string" ? taskId : "";

  useEffect(() => {
    let isActive = true;
    let intervalId: ReturnType<typeof setInterval> | undefined;

    async function poll() {
      if (!normalizedTaskId) {
        setHasFailed(true);
        return;
      }

      try {
        const nextResult = await getResults(normalizedTaskId);
        if (!isActive) {
          return;
        }

        setResult(nextResult);
        if (nextResult.status === "done" || nextResult.status === "failed") {
          setHasFailed(nextResult.status === "failed");
          clearInterval(intervalId);
        }
      } catch (err) {
        if (!isActive) {
          return;
        }
        setHasFailed(true);
        clearInterval(intervalId);
      }
    }

    poll();
    intervalId = setInterval(poll, 3000);

    return () => {
      isActive = false;
      clearInterval(intervalId);
    };
  }, [normalizedTaskId]);

  if (hasFailed || result?.status === "failed") {
    return (
      <Card className="w-full border-red-200 bg-red-50 shadow-sm">
        <CardContent className="space-y-4 pt-6">
          <p className="text-sm font-medium text-red-700">Parsing failed. Please try again.</p>
          <Button type="button" variant="destructive" onClick={() => router.push("/")}>
            Parse another resume
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!result || result.status === "pending" || result.status === "processing") {
    return (
      <Card className="w-full shadow-sm">
        <CardContent className="flex animate-pulse items-center justify-center gap-3 py-10 text-sm text-slate-600">
          <Spinner />
          <span>Parsing your resume...</span>
        </CardContent>
      </Card>
    );
  }

  const experience = (result.experience ?? []) as ExperienceItem[];
  const education = (result.education ?? []) as EducationItem[];
  const projects = result.projects ?? [];
  const certifications = result.certifications ?? [];
  const awards = result.awards ?? [];
  const languages = result.languages ?? [];
  const identity = result.identity ?? {};
  const educationHistory = (result.education_history ?? []) as EducationHistoryItem[];
  const skillsGrouped = result.skills_grouped ?? {};
  const positions = (result.positions_of_responsibility ?? []) as PositionOfResponsibilityItem[];
  const extracurriculars = result.extracurriculars ?? [];
  const roleTimeline = result.role_timeline ?? [];
  let skills: string[] = [];
  if (typeof result.skills === "string") {
    try {
      const parsedSkills = JSON.parse(result.skills);
      skills = Array.isArray(parsedSkills) ? parsedSkills : [];
    } catch {
      skills = [];
    }
  } else {
    skills = result.skills ?? [];
  }
  const skillSections: Array<[string, string[] | undefined]> = [
    ["Languages", skillsGrouped.languages],
    ["Frameworks & Libraries", skillsGrouped.frameworks_libraries],
    ["Tools & Platforms", skillsGrouped.tools_platforms],
    ["Soft Skills", skillsGrouped.soft_skills],
    ["ML/DL Frameworks", skillsGrouped.ml_dl_frameworks],
    ["MLOps/Cloud/DevOps", skillsGrouped.mlops_cloud_devops],
    ["Data & Viz", skillsGrouped.data_viz],
    ["APIs & Web", skillsGrouped.apis_web],
    ["Other", skillsGrouped.other],
  ];
  const completedResult = result;

  function handleDownloadJson() {
    const parsedResume = {
      name: completedResult.name ?? "",
      email: completedResult.email ?? "",
      phone: completedResult.phone ?? "",
      location: completedResult.location ?? "",
      linkedin: completedResult.linkedin ?? "",
      github: completedResult.github ?? "",
      summary: completedResult.summary ?? "",
      target_role: completedResult.target_role ?? "",
      years_experience: completedResult.years_experience ?? "",
      ats_keyword_match_score: completedResult.ats_keyword_match_score ?? "",
      experience_level: completedResult.experience_level ?? "",
      domain_classification: completedResult.domain_classification ?? "",
      skills,
      experience,
      education,
      projects,
      certifications,
      awards,
      languages,
      identity,
      education_history: educationHistory,
      skills_grouped: skillsGrouped,
      positions_of_responsibility: positions,
      extracurriculars,
      contact_card: completedResult.contact_card ?? {},
      role_timeline: roleTimeline,
    };
    const blob = new Blob([JSON.stringify(parsedResume, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "resume_parsed.json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4">
      <Card className="w-full p-6 shadow-sm">
        <CardHeader className="px-0">
          <CardTitle>Parsed resume</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6 px-0">
          <section>
            <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-muted-foreground">
              Contact
            </h2>
            <p className="text-2xl font-semibold text-slate-950">{result.name || "Name not found"}</p>
            {result.email ? (
              <a
                className="mt-1 inline-flex items-center gap-2 text-sm text-muted-foreground hover:underline"
                href={`mailto:${result.email}`}
              >
                <MailIcon className="size-4" />
                {result.email}
              </a>
            ) : (
              <p className="mt-1 inline-flex items-center gap-2 text-sm text-muted-foreground">
                <MailIcon className="size-4" />
                Email not found
              </p>
            )}
            <div className="mt-3 space-y-2 text-sm text-muted-foreground">
              {result.phone ? (
                <p className="inline-flex items-center gap-2">
                  <PhoneIcon className="size-4" />
                  {result.phone}
                </p>
              ) : null}
              {result.location ? (
                <p className="inline-flex items-center gap-2">
                  <MapPinIcon className="size-4" />
                  {result.location}
                </p>
              ) : null}
              {result.linkedin ? (
                <a
                  className="inline-flex items-center gap-2 hover:underline"
                  href={result.linkedin}
                  target="_blank"
                  rel="noreferrer"
                >
                  <LinkIcon className="size-4" />
                  LinkedIn
                </a>
              ) : null}
              {result.github ? (
                <a
                  className="inline-flex items-center gap-2 hover:underline"
                  href={result.github}
                  target="_blank"
                  rel="noreferrer"
                >
                  <LinkIcon className="size-4" />
                  GitHub
                </a>
              ) : null}
            </div>
          </section>

          {result.summary ? (
            <>
              <Separator />
              <section>
                <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-muted-foreground">
                  Summary
                </h2>
                <p className="text-sm leading-6 text-slate-700">{result.summary}</p>
              </section>
            </>
          ) : null}

          <Separator />

          <section>
            <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-muted-foreground">
              Parser Analysis
            </h2>
            <div className="grid gap-2 text-sm text-slate-700 sm:grid-cols-2">
              {[
                ["Target Role", result.target_role],
                ["Years of Experience", result.years_experience],
                ["ATS Keyword Match", result.ats_keyword_match_score],
                ["Experience Level", result.experience_level],
                ["Domain", result.domain_classification],
              ].map(([label, value]) =>
                value ? (
                  <p key={label}>
                    <span className="font-medium text-slate-950">{label}:</span> {value}
                  </p>
                ) : null
              )}
            </div>
          </section>

          {roleTimeline.length > 0 ? (
            <>
              <Separator />
              <section>
                <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-muted-foreground">
                  Timeline
                </h2>
                <div className="space-y-3">
                  {roleTimeline.map((item, index) => (
                    <div key={`${item.title}-${item.organization}-${index}`} className="border-l-2 border-muted pl-4">
                      <p className="font-semibold text-slate-950">{item.title || "Role not specified"}</p>
                      <p className="text-sm text-muted-foreground">
                        {[item.organization, item.start_date, item.end_date, item.type].filter(Boolean).join(" - ")}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            </>
          ) : null}

          <Separator />

          <section>
            <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-muted-foreground">
              Identity
            </h2>
            <div className="grid gap-2 text-sm text-slate-700 sm:grid-cols-2">
              {[
                ["ID", identity.student_id],
                ["Institution", identity.institution],
                ["Degree", identity.degree],
                ["Stream", identity.stream],
                ["CGPA", identity.cgpa],
                ["Graduation Year", identity.graduation_year],
              ].map(([label, value]) =>
                value ? (
                  <p key={label}>
                    <span className="font-medium text-slate-950">{label}:</span> {value}
                  </p>
                ) : null
              )}
            </div>
          </section>

          {educationHistory.length > 0 ? (
            <>
              <Separator />
              <section>
                <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-muted-foreground">
                  Education History
                </h2>
                <div className="space-y-3">
                  {educationHistory.map((item, index) => (
                    <div key={`${item.level}-${item.school}-${index}`} className="border-l-2 border-muted pl-4">
                      <p className="font-semibold text-slate-950">{item.school || item.level || "School not specified"}</p>
                      <p className="text-sm text-muted-foreground">
                        {[item.level, item.board, item.score, item.year].filter(Boolean).join(" - ")}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            </>
          ) : null}

          <Separator />

          <section>
            <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-muted-foreground">
              Skills
            </h2>
            <div className="space-y-3">
              {skillSections.map(([label, values]) =>
                Array.isArray(values) && values.length > 0 ? (
                  <div key={label}>
                    <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
                    <div className="flex flex-wrap gap-2">
                      {values.map((skill) => (
                        <Badge key={`${label}-${skill}`} variant="secondary" className="bg-blue-50 text-blue-700 hover:bg-blue-100">
                          {skill}
                        </Badge>
                      ))}
                    </div>
                  </div>
                ) : null
              )}
              <div className="flex flex-wrap gap-2">
                {skills.map((skill) => (
                  <Badge key={skill} variant="secondary" className="bg-blue-50 text-blue-700 hover:bg-blue-100">
                    {skill}
                  </Badge>
                ))}
              </div>
            </div>
          </section>

          <Separator />

          <section>
            <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-muted-foreground">
              Experience
            </h2>
            <div>
              {experience.map((item, index) => (
                <div
                  key={`${item.company}-${item.role}-${index}`}
                  className="mb-3 border-l-2 border-muted pl-4 last:mb-0"
                >
                  <p className="font-semibold text-slate-950">{item.company || "Company not specified"}</p>
                  <p className="text-sm text-muted-foreground">
                    {item.role || "Role not specified"}
                    {item.duration ? ` - ${item.duration}` : ""}
                  </p>
                </div>
              ))}
            </div>
          </section>

          <Separator />

          <section>
            <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-muted-foreground">
              Education
            </h2>
            <div>
              {education.map((item, index) => (
                <div
                  key={`${item.institution}-${item.degree}-${index}`}
                  className="mb-3 border-l-2 border-muted pl-4 last:mb-0"
                >
                  <p className="font-semibold text-slate-950">
                    {item.institution || "Institution not specified"}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {item.degree || "Degree not specified"}
                    {item.year ? ` - ${item.year}` : ""}
                  </p>
                </div>
              ))}
            </div>
          </section>

          {projects.length > 0 ? (
            <>
              <Separator />
              <section>
                <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-muted-foreground">
                  Projects
                </h2>
                <div className="space-y-3">
                  {projects.map((item, index) => (
                    <div key={`${item.name}-${index}`} className="border-l-2 border-muted pl-4">
                      <p className="font-semibold text-slate-950">{item.title || item.name || "Project not specified"}</p>
                      {item.type_domain ? <p className="text-sm text-muted-foreground">{item.type_domain}</p> : null}
                      {item.description ? <p className="text-sm text-muted-foreground">{item.description}</p> : null}
                      {item.key_tools?.length ? (
                        <p className="text-sm text-muted-foreground">{item.key_tools.join(" - ")}</p>
                      ) : null}
                      {item.performance_metrics?.length ? (
                        <p className="text-sm text-muted-foreground">{item.performance_metrics.join(" - ")}</p>
                      ) : null}
                      {item.technologies?.length ? (
                        <p className="text-sm text-muted-foreground">{item.technologies.join(" • ")}</p>
                      ) : null}
                      {item.link ? (
                        <a
                          className="mt-1 inline-flex items-center gap-2 text-sm text-blue-700 hover:underline"
                          href={item.link}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <ExternalLinkIcon className="size-4" />
                          View project
                        </a>
                      ) : null}
                    </div>
                  ))}
                </div>
              </section>
            </>
          ) : null}

          {positions.length > 0 ? (
            <>
              <Separator />
              <section>
                <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-muted-foreground">
                  Positions of Responsibility
                </h2>
                <div className="space-y-3">
                  {positions.map((item, index) => (
                    <div key={`${item.role}-${item.organization}-${index}`} className="border-l-2 border-muted pl-4">
                      <p className="font-semibold text-slate-950">{item.role || "Role not specified"}</p>
                      <p className="text-sm text-muted-foreground">
                        {[item.organization, item.duration].filter(Boolean).join(" - ")}
                      </p>
                      {item.description ? <p className="text-sm text-muted-foreground">{item.description}</p> : null}
                      {item.key_impact_numbers?.length ? (
                        <p className="text-sm text-muted-foreground">{item.key_impact_numbers.join(" - ")}</p>
                      ) : null}
                    </div>
                  ))}
                </div>
              </section>
            </>
          ) : null}

          {certifications.length > 0 ? (
            <>
              <Separator />
              <section>
                <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-muted-foreground">
                  Certifications
                </h2>
                <div className="space-y-3">
                  {certifications.map((item, index) => (
                    <div key={`${item.name}-${index}`} className="border-l-2 border-muted pl-4">
                      <p className="font-semibold text-slate-950">{item.name || "Certification not specified"}</p>
                      <p className="text-sm text-muted-foreground">
                        {[item.issuer, item.year].filter(Boolean).join(" • ")}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            </>
          ) : null}

          {awards.length > 0 ? (
            <>
              <Separator />
              <section>
                <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-muted-foreground">
                  Awards
                </h2>
                <div className="flex flex-wrap gap-2">
                  {awards.map((award) => (
                    <Badge
                      key={award}
                      variant="secondary"
                      className="bg-amber-50 text-amber-700 hover:bg-amber-100"
                    >
                      {award}
                    </Badge>
                  ))}
                </div>
              </section>
            </>
          ) : null}

          {languages.length > 0 ? (
            <>
              <Separator />
              <section>
                <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-muted-foreground">
                  Languages
                </h2>
                <div className="flex flex-wrap gap-2">
                  {languages.map((language) => (
                    <Badge key={language} variant="secondary">
                      {language}
                    </Badge>
                  ))}
                </div>
              </section>
            </>
          ) : null}

          {extracurriculars.length > 0 ? (
            <>
              <Separator />
              <section>
                <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-muted-foreground">
                  Extra-curriculars
                </h2>
                <div className="flex flex-wrap gap-2">
                  {extracurriculars.map((item) => (
                    <Badge key={item} variant="secondary">
                      {item}
                    </Badge>
                  ))}
                </div>
              </section>
            </>
          ) : null}
        </CardContent>
      </Card>
      <Button type="button" onClick={handleDownloadJson}>
        <DownloadIcon />
        Download JSON
      </Button>
    </div>
  );
}
