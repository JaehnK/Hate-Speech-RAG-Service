import { Badge } from "@astryxdesign/core/Badge";
import { Text } from "@astryxdesign/core/Text";
import { ChevronDown, ExternalLink } from "lucide-react";

import { ragContextLabel, SCOPE_LABELS } from "../labels";
import type { ReportComment } from "../types";
import { categoryLabel, formatNumber } from "../utils";

export function HateCommentCard({ comment }: { comment: ReportComment }) {
  const { analysis } = comment;
  const similarCases = analysis.similar_cases_used ?? [];
  const definitionDocs = analysis.definition_docs_used ?? [];
  const isInsult = analysis.target_scope === "individual";
  const isNormal = analysis.is_hate_speech === false;
  return (
    <article className="hs-comment">
      <details>
        <summary>
          <span className="hs-comment-meta">
            <span className={`hs-swatch ${isNormal ? "is-normal" : isInsult ? "is-insult" : "is-hate"}`} aria-hidden />
            <Text type="label">{isNormal ? "혐오 아님" : SCOPE_LABELS[analysis.target_scope ?? ""] ?? "혐오표현"}</Text>
            {!isNormal && <Text type="supporting">{(analysis.categories ?? []).map(categoryLabel).join(", ") || "유형 없음"}</Text>}
            <Text type="supporting" hasTabularNumbers>좋아요 {formatNumber(comment.like_count)}</Text>
            {comment.is_reply && <Badge variant="neutral" label="답글" />}
          </span>
          <Text as="p">{comment.text_original || "내용이 없는 댓글입니다."}</Text>
          <span className="hs-comment-toggle">
            <Text type="supporting" weight="medium">판정 근거 보기</Text>
            <ChevronDown size={14} aria-hidden />
          </span>
        </summary>
        <div className="hs-evidence">
          <section>
            <Text type="label" as="div">판정 이유</Text>
            <Text as="p">{analysis.reasoning || "저장된 판정 이유가 없습니다."}</Text>
          </section>
          <dl className="hs-kv">
            <div><dt>공격 대상</dt><dd>{analysis.target_group || "특정되지 않음"}</dd></div>
            <div><dt>표현 방식</dt><dd>{analysis.hate_type || "특정되지 않음"}</dd></div>
            <div><dt>찾은 근거</dt><dd>{ragContextLabel(analysis.rag_context_status)}</dd></div>
          </dl>
          <section>
            <Text type="label" as="div">근거로 쓴 기준</Text>
            {definitionDocs.length > 0 ? (
              <ul className="hs-citations">
                {definitionDocs.map((item, index) => (
                  <li key={`${item.doc_id ?? "definition"}-${index}`}>
                    {item.title ? (
                      <>
                        <Text weight="medium">{item.title}</Text>
                        <Text type="supporting">
                          {item.section}{item.source_label ? ` (${item.source_label})` : ""}
                          {item.source_url && <> · <a href={item.source_url} target="_blank" rel="noopener noreferrer">원문 <ExternalLink size={12} aria-hidden /></a></>}
                        </Text>
                      </>
                    ) : (
                      <>
                        <span className="hs-code">{item.doc_id ?? "문서 ID 없음"}</span>
                        <Text type="supporting">{item.source_label ?? item.source_id ?? "출처 기록 없음"}</Text>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            ) : <Text type="supporting" as="p">인용한 기준 문서가 없습니다.</Text>}
          </section>
          <section>
            <Text type="label" as="div">비슷한 사례</Text>
            {similarCases.length > 0 ? (
              <ul className="hs-citations">
                {similarCases.map((item, index) => (
                  <li key={`${item.doc_id ?? "case"}-${index}`}>
                    <span className="hs-code">{item.doc_id ?? "문서 ID 없음"}</span>
                    <Text type="supporting">{item.source_dataset ?? "출처 기록 없음"}{item.mapped_categories?.length ? ` · ${item.mapped_categories.map(categoryLabel).join(", ")}` : ""}</Text>
                  </li>
                ))}
              </ul>
            ) : <Text type="supporting" as="p">인용한 비슷한 사례가 없습니다.</Text>}
          </section>
          <p className="hs-note">비슷한 사례는 비교용 참고 자료이며, 최종 판단이나 법적 근거가 아닙니다.</p>
        </div>
      </details>
    </article>
  );
}
