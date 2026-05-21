"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { DownloadIcon, MailIcon } from "lucide-react";
import { getResults, ParsedResumeResult } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";

type ResultsDisplayProps = {
  taskId: string;
};

type ExperienceItem = {
  company?: string;
  role?: string;
  duration?: string;
};

type EducationItem = {
  institution?: string;
  degree?: string;
  year?: string;
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
  const completedResult = result;

  function handleDownloadJson() {
    const parsedResume = {
      name: completedResult.name ?? "",
      email: completedResult.email ?? "",
      skills,
      experience,
      education,
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
          </section>

          <Separator />

          <section>
            <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-muted-foreground">
              Skills
            </h2>
            <div className="flex flex-wrap gap-2">
              {skills.map((skill) => (
                <Badge
                  key={skill}
                  variant="secondary"
                  className="bg-blue-50 text-blue-700 hover:bg-blue-100"
                >
                  {skill}
                </Badge>
              ))}
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
        </CardContent>
      </Card>
      <Button type="button" onClick={handleDownloadJson}>
        <DownloadIcon />
        Download JSON
      </Button>
    </div>
  );
}
