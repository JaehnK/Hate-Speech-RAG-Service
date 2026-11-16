import { ApiError } from "./api";

export const STEP_LABELS: Record<string, string> = {
  validate_input: "입력 확인",
  collect_metadata: "영상 정보 수집",
  collect_comments: "댓글 수집",
  collect_transcript: "자막 수집",
  create_analysis_run: "분석 준비",
  analyze_comments: "댓글 판정",
  analyze_script: "자막 판정",
  build_comment_network: "답글 네트워크 만들기",
  build_report_snapshot: "보고서 만들기",
  finalize_job: "마무리",
};

export function stepLabel(stepKey: string | null | undefined): string {
  if (!stepKey) return "완료";
  return STEP_LABELS[stepKey] ?? stepKey;
}

const STATUS_TEXT: Record<string, string> = {
  pending: "대기 중",
  running: "분석 중",
  succeeded: "완료",
  partial_success: "일부 완료",
  failed: "실패",
  skipped: "건너뜀",
};

export function statusText(status: string): string {
  return STATUS_TEXT[status] ?? status;
}

export const SCOPE_LABELS: Record<string, string> = { group: "집단 혐오", individual: "모욕·욕설" };

export function ragContextLabel(status: string | null): string {
  return {
    complete: "유형 정의 + 비슷한 사례",
    definition_only: "유형 정의만",
    example_only: "비슷한 사례만",
    unavailable: "찾은 근거 없음",
    jev_filtered: "가벼운 모델이 먼저 혐오 아님으로 판정 (AI 판정 생략)",
  }[status ?? ""] ?? "기록 없음";
}

export function errorMessage(cause: unknown): string {
  if (cause instanceof ApiError || cause instanceof Error) return cause.message;
  return "알 수 없는 오류가 발생했습니다.";
}
