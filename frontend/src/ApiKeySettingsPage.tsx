import { Check, ExternalLink, KeyRound, LoaderCircle, ShieldCheck, Trash2 } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";

import { deleteApiKey, getApiKeys, putApiKey } from "./api";
import type { ApiKeySummary } from "./types";

const PROVIDERS = [
  {
    id: "anthropic" as const,
    title: "Anthropic",
    description: "혐오표현 문맥 판정에 사용합니다.",
    issueUrl: "https://platform.claude.com/settings/keys",
    steps: [
      "Claude Console 계정을 만들거나 로그인합니다.",
      "API Keys에서 Create Key를 선택하고 키 이름을 지정합니다.",
      "생성 직후 표시되는 키를 복사해 아래 입력란에 붙여넣습니다.",
    ],
    note: "Claude 구독과 API 사용 크레딧은 별도입니다. Console에서 크레딧도 확인해주세요.",
  },
  {
    id: "upstage" as const,
    title: "Upstage",
    description: "정의와 유사 사례 검색용 임베딩에 사용합니다.",
    issueUrl: "https://console.upstage.ai/api-keys",
    steps: [
      "Upstage Console에 가입하거나 로그인합니다.",
      "API Keys 화면에서 새 키를 발급합니다.",
      "발급된 키를 복사해 아래 입력란에 붙여넣습니다.",
    ],
    note: "Embed 2 사용량과 잔여 크레딧은 Console의 Billing과 Usage에서 확인할 수 있습니다.",
  },
];

export function ApiKeySettingsPage() {
  const [keys, setKeys] = useState<ApiKeySummary[]>([]);
  const [values, setValues] = useState({ anthropic: "", upstage: "" });
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const reload = () => getApiKeys().then((payload) => setKeys(payload.items));
  useEffect(() => { void reload().catch(() => setMessage("API 키 정보를 불러오지 못했습니다.")); }, []);

  async function save(event: FormEvent, provider: "anthropic" | "upstage") {
    event.preventDefault(); setBusy(provider); setMessage(null);
    try { await putApiKey(provider, values[provider]); setValues((current) => ({ ...current, [provider]: "" })); await reload(); setMessage("검증과 암호화 저장을 완료했습니다."); }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : "API 키를 저장하지 못했습니다."); }
    finally { setBusy(null); }
  }

  async function remove(provider: "anthropic" | "upstage") {
    setBusy(provider); setMessage(null);
    try { await deleteApiKey(provider); await reload(); setMessage("등록된 키를 삭제했습니다."); }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : "API 키를 삭제하지 못했습니다."); }
    finally { setBusy(null); }
  }

  return (
    <div className="page-wrap key-settings">
      <div className="page-title"><div><small>BYOK SETTINGS</small><h1>분석 API 키</h1></div></div>
      <p className="page-description">키는 유효성을 확인한 뒤 암호화해 저장하며, 분석 작업 중에만 복호화합니다.</p>
      <aside className="key-security-note"><ShieldCheck size={18} /><p><strong>API 키를 안전하게 보관하세요.</strong> 이 페이지에만 입력하고 Git, 메신저, 스크린샷에는 남기지 마세요.</p></aside>
      {message && <div className="settings-message" role="status">{message}</div>}
      <div className="key-grid">{PROVIDERS.map((provider) => {
        const saved = keys.find((key) => key.provider === provider.id);
        return <form className="panel key-card" onSubmit={(event) => void save(event, provider.id)} key={provider.id}>
          <div className="key-title"><span><KeyRound size={20} /></span><div><h2>{provider.title}</h2><p>{provider.description}</p></div></div>
          <section className="key-issuance" aria-labelledby={`${provider.id}-issuance-title`}>
            <div><strong id={`${provider.id}-issuance-title`}>발급 방법</strong><a href={provider.issueUrl} target="_blank" rel="noreferrer">공식 발급 페이지 <ExternalLink size={14} /></a></div>
            <ol>{provider.steps.map((step) => <li key={step}>{step}</li>)}</ol>
            <p>{provider.note}</p>
          </section>
          {saved && <div className="saved-key"><Check size={16} /><span>{saved.key_fingerprint}</span><strong>{saved.is_valid ? "검증됨" : "재검증 필요"}</strong></div>}
          <label>새 API 키<input type="password" autoComplete="off" minLength={8} required value={values[provider.id]} onChange={(event) => setValues((current) => ({ ...current, [provider.id]: event.target.value }))} placeholder={`${provider.title} API key`} /></label>
          <div className="key-actions"><button className="button-small" disabled={busy !== null}>{busy === provider.id ? <LoaderCircle className="spin" size={15} /> : <KeyRound size={15} />} 검증 후 저장</button>{saved && <button className="key-delete" type="button" disabled={busy !== null} onClick={() => void remove(provider.id)}><Trash2 size={15} /> 삭제</button>}</div>
        </form>;
      })}</div>
    </div>
  );
}
