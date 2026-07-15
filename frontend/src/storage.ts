import type { StoredJob } from "./types";

const STORAGE_KEY = "sentinel-yt:jobs";

export function getStoredJobs(): StoredJob[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter(isStoredJob) : [];
  } catch {
    return [];
  }
}

export function rememberJob(job: StoredJob): void {
  const jobs = getStoredJobs().filter((item) => item.jobId !== job.jobId);
  localStorage.setItem(STORAGE_KEY, JSON.stringify([job, ...jobs].slice(0, 50)));
}

function isStoredJob(value: unknown): value is StoredJob {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return typeof item.jobId === "string" && typeof item.videoId === "string" && typeof item.createdAt === "string";
}
