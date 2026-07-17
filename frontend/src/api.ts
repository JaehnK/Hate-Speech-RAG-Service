import type { CommentNetwork, CreatedJob, ExportStatus, Job, Report, ReportCommentPage, ReportScriptSegmentPage } from "./types";

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
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const message = payload?.error?.message ?? payload?.detail ?? `요청에 실패했습니다. (${response.status})`;
    throw new ApiError(message, response.status);
  }
  return response.json() as Promise<T>;
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
