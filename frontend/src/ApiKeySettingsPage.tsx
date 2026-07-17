import { Check, KeyRound, LoaderCircle, Trash2 } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";

import { deleteApiKey, getApiKeys, putApiKey } from "./api";
import type { ApiKeySummary } from "./types";

const PROVIDERS = [
  { id: "anthropic" as const, title: "Anthropic", description: "혐오표현 문맥 판정에 사용합니다." },
  { id: "upstage" as const, title: "Upstage", description: "정의와 유사 사례 검색용 임베딩에 사용합니다." },
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
      {message && <div className="settings-message" role="status">{message}</div>}
      <div className="key-grid">{PROVIDERS.map((provider) => {
        const saved = keys.find((key) => key.provider === provider.id);
        return <form className="panel key-card" onSubmit={(event) => void save(event, provider.id)} key={provider.id}>
          <div className="key-title"><span><KeyRound size={20} /></span><div><h2>{provider.title}</h2><p>{provider.description}</p></div></div>
          {saved && <div className="saved-key"><Check size={16} /><span>{saved.key_fingerprint}</span><strong>{saved.is_valid ? "검증됨" : "재검증 필요"}</strong></div>}
          <label>새 API 키<input type="password" autoComplete="off" minLength={8} required value={values[provider.id]} onChange={(event) => setValues((current) => ({ ...current, [provider.id]: event.target.value }))} placeholder={`${provider.title} API key`} /></label>
          <div><button className="button-small" disabled={busy !== null}>{busy === provider.id ? <LoaderCircle className="spin" size={15} /> : <KeyRound size={15} />} 검증 후 저장</button>{saved && <button className="key-delete" type="button" disabled={busy !== null} onClick={() => void remove(provider.id)}><Trash2 size={15} /> 삭제</button>}</div>
        </form>;
      })}</div>
    </div>
  );
}
