const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type ParsedResumeResult = {
  status: string;
  name?: string;
  email?: string;
  skills?: string[] | string;
  experience?: Record<string, unknown>[];
  education?: Record<string, unknown>[];
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
