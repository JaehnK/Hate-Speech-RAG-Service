export const TERMINAL_STATUSES = new Set(["succeeded", "partial_success", "failed"]);

const CATEGORY_LABELS: Record<string, string> = {
  gender: "성별",
  age: "연령",
  identity: "정체성",
  profanity: "욕설",
  state_authority: "국가 권위체",
  non_state_authority: "비국가 권위체",
  state_regime: "국가 제도",
  non_state_regime: "비국가 제도",
  state_community: "국가 공동체",
  non_state_community: "비국가 공동체",
  no_target: "대상 없음",
  other: "기타",
  unclassified: "미분류",
};

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? `알 수 없는 분류 (${category})`;
}

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
