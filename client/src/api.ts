import type { ResultResponse, SetupForm } from "./types";
import { apiBaseUrl, backendUrl } from "./deployment";

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("The resume could not be read."));
    reader.onload = () => {
      const value = String(reader.result);
      resolve(value.slice(value.indexOf(",") + 1));
    };
    reader.readAsDataURL(file);
  });
}

async function responseError(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    return payload.detail || "The request could not be completed.";
  } catch {
    return "The request could not be completed.";
  }
}

async function callBackend(url: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(backendUrl(url), init);
  } catch {
    throw new Error(
      apiBaseUrl
        ? "Cannot reach the deployed InterviewFlow backend. Please try again shortly."
        : "Cannot reach the InterviewFlow backend on port 7860. Start the Python server, then try again.",
    );
  }
}

export async function prepareInterview(form: SetupForm) {
  const response = await callBackend("/api/interview-setup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      resume_base64: await fileToBase64(form.resume),
      job_description: form.jobDescription,
      rubric: form.rubric,
      rubric_approved: true,
    }),
  });
  if (!response.ok) throw new Error(await responseError(response));
  return response.json() as Promise<{
    setup_id: string;
    page_count: number;
    role_title: string;
  }>;
}

export async function getInterviewResult(sessionId: string): Promise<ResultResponse> {
  const response = await callBackend(`/api/interview-results/${sessionId}`);
  if (!response.ok) throw new Error(await responseError(response));
  return response.json();
}
