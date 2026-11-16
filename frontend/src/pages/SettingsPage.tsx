import { AlertDialog } from "@astryxdesign/core/AlertDialog";
import { Banner } from "@astryxdesign/core/Banner";
import { Button } from "@astryxdesign/core/Button";
import { Heading } from "@astryxdesign/core/Heading";
import { Spinner } from "@astryxdesign/core/Spinner";
import { Text } from "@astryxdesign/core/Text";
import { TextInput } from "@astryxdesign/core/TextInput";
import { ExternalLink, KeyRound } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { deleteApiKey, getApiKeys, putApiKey } from "../api";
import { errorMessage } from "../labels";
import { useSession } from "../session";
import type { ApiKeySummary } from "../types";
import { PageHeader } from "../ui/common";
import { formatDate } from "../utils";

const ISSUE_URL = "https://platform.claude.com/settings/keys";

type Notice = { status: "success" | "error"; title: string; description?: string } | null;

export function SettingsPage() {
  const { session, refresh, signOut } = useSession();
  const navigate = useNavigate();
  const [keys, setKeys] = useState<ApiKeySummary[] | null>(null);
  const [value, setValue] = useState("");
  const [replacing, setReplacing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<ApiKeySummary["provider"] | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);

  const reload = () => getApiKeys().then((payload) => setKeys(payload.items));
  useEffect(() => {
    void reload().catch(() => { setKeys([]); setNotice({ status: "error", title: "API 키 정보를 불러오지 못했습니다" }); });
  }, []);

  const anthropic = keys?.find((key) => key.provider === "anthropic");
  const legacy = keys?.find((key) => key.provider === "upstage");
  const showForm = !anthropic || replacing;

  async function save(event: FormEvent) {
    event.preventDefault();
    if (value.trim().length < 8) {
      setNotice({ status: "error", title: "키를 다시 확인해주세요", description: "Claude Console에서 복사한 키 전체를 붙여넣어 주세요." });
      return;
    }
    setSaving(true);
    setNotice(null);
    try {
      await putApiKey("anthropic", value.trim());
      setValue("");
      setReplacing(false);
      await Promise.all([reload(), refresh()]);
      setNotice({ status: "success", title: anthropic ? "새 키로 바꿨습니다" : "키를 등록했습니다", description: "사용할 수 있는지 확인한 뒤 암호화해 보관했습니다." });
    } catch (cause) {
      setNotice({ status: "error", title: "키를 저장하지 못했습니다", description: errorMessage(cause) });
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!confirmDelete) return;
    setDeleting(true);
    setNotice(null);
    try {
      await deleteApiKey(confirmDelete);
      await Promise.all([reload(), refresh()]);
      setNotice({ status: "success", title: "키를 삭제했습니다" });
    } catch (cause) {
      setNotice({ status: "error", title: "키를 삭제하지 못했습니다", description: errorMessage(cause) });
    } finally {
      setDeleting(false);
      setConfirmDelete(null);
    }
  }

  async function onSignOut() {
    await signOut();
    navigate("/");
  }

  return (
    <div className="hs-page hs-page--narrow">
      <PageHeader title="계정 설정" />
      {notice && <Banner status={notice.status} title={notice.title} description={notice.description} isDismissable onDismiss={() => setNotice(null)} />}

      <section className="hs-section" aria-labelledby="key-title">
        <div className="hs-stack hs-stack--tight">
          <Heading level={2} id="key-title">Anthropic API 키</Heading>
          <Text type="supporting" as="p">댓글 판정에 씁니다. Claude 사용 요금이 이 키로 청구되고, 검색용 처리 비용은 서비스가 부담합니다.</Text>
        </div>

        {keys === null ? <Spinner label="키 정보를 불러오는 중입니다" /> : (
          <>
            {anthropic && (
              <div className="hs-key-row">
                <KeyRound size={18} aria-hidden />
                <div className="hs-stack hs-stack--tight hs-grow">
                  <span className="hs-code">{anthropic.key_fingerprint}</span>
                  <Text type="supporting">{anthropic.is_valid ? "사용 가능 확인" : "다시 확인이 필요합니다"}{anthropic.last_validated_at ? ` · ${formatDate(anthropic.last_validated_at)}` : ""}</Text>
                </div>
                {!replacing && <Button size="sm" label="다른 키로 바꾸기" onClick={() => setReplacing(true)} />}
                <Button size="sm" variant="ghost" label="삭제" onClick={() => setConfirmDelete("anthropic")} />
              </div>
            )}

            {showForm && (
              <form className="hs-stack" onSubmit={(event) => void save(event)} noValidate>
                <TextInput
                  type="password"
                  label={anthropic ? "새 API 키" : "API 키"}
                  value={value}
                  onChange={setValue}
                  placeholder="sk-ant-…"
                  isDisabled={saving}
                  description="저장하기 전에 실제로 쓸 수 있는 키인지 확인합니다."
                />
                <div className="hs-row">
                  <Button type="submit" variant="primary" label={anthropic ? "확인하고 바꾸기" : "확인하고 저장"} isLoading={saving} />
                  {replacing && <Button variant="ghost" label="취소" onClick={() => { setReplacing(false); setValue(""); }} />}
                </div>
              </form>
            )}
          </>
        )}

        <div className="hs-callout">
          <div className="hs-section-header">
            <Text weight="semibold">키 발급 방법</Text>
            <a href={ISSUE_URL} target="_blank" rel="noreferrer">Claude Console에서 발급 <ExternalLink size={12} aria-hidden /></a>
          </div>
          <ol className="hs-list">
            <li>Claude Console 계정을 만들거나 로그인합니다.</li>
            <li>API Keys에서 Create Key를 선택하고 키 이름을 지정합니다.</li>
            <li>만든 직후 표시되는 키를 복사해 위 입력란에 붙여넣습니다.</li>
          </ol>
          <p className="hs-note">Claude 구독과 API 사용 크레딧은 별도입니다. Console에서 크레딧도 확인해주세요.</p>
        </div>
        <p className="hs-note">키는 암호화해 보관하고, 분석할 때만 꺼내 씁니다. 이 페이지 밖(Git, 메신저, 스크린샷)에는 남기지 마세요.</p>
      </section>

      {legacy && (
        <section className="hs-section" aria-labelledby="legacy-title">
          <Heading level={2} id="legacy-title">더 이상 쓰지 않는 키</Heading>
          <div className="hs-key-row">
            <KeyRound size={18} aria-hidden />
            <div className="hs-stack hs-stack--tight hs-grow">
              <Text weight="medium">검색용 키 (이전 방식)</Text>
              <Text type="supporting">2026년 11월 9일부터 검색용 처리는 서비스가 부담해 이 키를 쓰지 않습니다.</Text>
            </div>
            <Button size="sm" variant="ghost" label="삭제" onClick={() => setConfirmDelete("upstage")} />
          </div>
        </section>
      )}

      {session && (
        <section className="hs-section" aria-labelledby="account-title">
          <Heading level={2} id="account-title">Google 계정</Heading>
          <div className="hs-key-row">
            <div className="hs-stack hs-stack--tight hs-grow">
              <Text weight="medium">{session.display_name ?? session.email}</Text>
              <Text type="supporting">{session.email}</Text>
            </div>
            <Button size="sm" label="로그아웃" onClick={() => void onSignOut()} />
          </div>
        </section>
      )}

      <AlertDialog
        isOpen={confirmDelete !== null}
        onOpenChange={(open) => { if (!open) setConfirmDelete(null); }}
        title="키를 삭제할까요?"
        description={confirmDelete === "anthropic" ? "삭제하면 새 키를 등록하기 전까지 분석을 시작할 수 없습니다. 이미 끝난 보고서는 그대로 남습니다." : "이 키는 더 이상 쓰이지 않으므로 삭제해도 분석에 영향이 없습니다."}
        actionLabel="삭제"
        cancelLabel="취소"
        onAction={() => void remove()}
        isActionLoading={deleting}
      />
    </div>
  );
}
