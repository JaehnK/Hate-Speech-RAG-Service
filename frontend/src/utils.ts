export const TERMINAL_STATUSES = new Set(["succeeded", "partial_success", "failed"]);

const CATEGORY_LABELS: Record<string, string> = {
  gender: "성별 비하",
  age: "연령 비하",
  identity: "출신·인종·종교·장애 등 비하",
  profanity: "욕설·모욕·기타 공격",
  state_authority: "정부·공직자 공격",
  non_state_authority: "정당·정치인·언론 공격",
  state_regime: "법·제도 공격",
  non_state_regime: "정당·단체 운영방식 공격",
  state_community: "국민 전체 비하",
  non_state_community: "지지층·진영 비하",
  no_target: "대상 없는 욕설",
  other: "기타 대상 공격 (이전 분류)",
  unclassified: "혐오 아님",
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

export function formatPlaybackTime(value: number): string {
  const seconds = Math.max(0, Math.floor(value));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainder = seconds % 60;
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`
    : `${minutes}:${String(remainder).padStart(2, "0")}`;
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
