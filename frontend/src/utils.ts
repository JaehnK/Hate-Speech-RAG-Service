export const TERMINAL_STATUSES = new Set(["succeeded", "partial_success", "failed"]);

export function formatNumber(value: number | null | undefined): string {
  return new Intl.NumberFormat("ko-KR").format(value ?? 0);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  return new Intl.DateTimeFormat("ko-KR", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function ratioPercent(count: number, total: number): number {
  return total > 0 ? (count / total) * 100 : 0;
}

export function reportIdFromPath(path: string | null): string | null {
  return path?.split("/").filter(Boolean).at(-1) ?? null;
}

export function itemProgressText(
  stepKey: string,
  progress: { total: number; completed: number; succeeded: number; failed: number },
): string {
  const unit = stepKey === "analyze_script" ? "세그먼트" : "댓글·답글";
  return `${unit} ${formatNumber(progress.completed)} / ${formatNumber(progress.total)} 완료 · 성공 ${formatNumber(progress.succeeded)} · 실패 ${formatNumber(progress.failed)}`;
}
