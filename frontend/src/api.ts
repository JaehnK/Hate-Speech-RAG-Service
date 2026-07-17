import type { ApiKeySummary, AuthSession, CommentNetwork, CreatedJob, ExportStatus, Job, Page, PublicReportSummary, Report, ReportCommentPage, ReportScriptSegmentPage } from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.method && init.method !== "GET" ? { "X-Requested-With": "hatespeechraw" } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const message = payload?.error?.message ?? payload?.detail ?? `요청에 실패했습니다. (${response.status})`;
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function getAuthSession(): Promise<AuthSession | null> {
  try {
    return await request<AuthSession>("/api/auth/session");
  } catch (cause) {
    if (cause instanceof ApiError && cause.status === 401) return null;
    throw cause;
  }
}

export function logout(): Promise<void> {
  return request<void>("/api/auth/logout", { method: "POST" });
}

export function getApiKeys(): Promise<{ items: ApiKeySummary[] }> {
  return request("/api/me/api-keys");
}

export function putApiKey(provider: "anthropic" | "upstage", apiKey: string): Promise<ApiKeySummary> {
  return request(`/api/me/api-keys/${provider}`, { method: "PUT", body: JSON.stringify({ api_key: apiKey }) });
}

export function deleteApiKey(provider: "anthropic" | "upstage"): Promise<void> {
  return request<void>(`/api/me/api-keys/${provider}`, { method: "DELETE" });
}

export function getPublicReports(): Promise<Page<PublicReportSummary>> {
  return request("/api/reports/public?limit=12");
}

export function getMyJobs(): Promise<Page<Job>> {
  return request("/api/me/jobs?limit=200");
}

export function createJob(inputValue: string): Promise<CreatedJob> {
  return request("/api/analysis-jobs", {
    method: "POST",
    body: JSON.stringify({ input_value: inputValue }),
  });
}

export function getJob(jobId: string): Promise<Job> {
  return request(`/api/analysis-jobs/${encodeURIComponent(jobId)}`);
}

export function getReport(reportId: string): Promise<Report> {
  return request(`/api/reports/${encodeURIComponent(reportId)}`);
}

export function getReportNetwork(reportId: string): Promise<CommentNetwork> {
  return request(`/api/reports/${encodeURIComponent(reportId)}/network`);
}

export function getHateComments(reportId: string, cursor = 0): Promise<ReportCommentPage> {
  const query = new URLSearchParams({
    is_hate_speech: "true",
    status: "succeeded",
    sort: "like_count",
    limit: "200",
    cursor: String(cursor),
  });
  return request(`/api/reports/${encodeURIComponent(reportId)}/comments?${query}`);
}

export function getScriptSegments(reportId: string, cursor = 0): Promise<ReportScriptSegmentPage> {
  const query = new URLSearchParams({ limit: "200", cursor: String(cursor) });
  return request(`/api/reports/${encodeURIComponent(reportId)}/script-segments?${query}`);
}

export function createExport(reportId: string, format: "html" | "xlsx"): Promise<ExportStatus> {
  return request(`/api/reports/${encodeURIComponent(reportId)}/exports`, {
    method: "POST",
    body: JSON.stringify({ format }),
  });
}

export function getExport(exportId: string): Promise<ExportStatus> {
  return request(`/api/exports/${encodeURIComponent(exportId)}`);
}
