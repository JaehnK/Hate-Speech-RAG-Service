import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from "react";

import { getAuthSession, logout } from "./api";
import type { AuthSession } from "./types";

const LOGIN_MESSAGE = "hatescope:login-complete";
const POPUP_NAME = "hatescope-google-login";
const CHANNEL_NAME = "hatescope-auth";
const STORAGE_KEY = "hatescope:last-login";

interface SessionState {
  /** undefined while the first check is in flight, null when signed out. */
  session: AuthSession | null | undefined;
  refresh: () => Promise<void>;
  signIn: () => void;
  signOut: () => Promise<void>;
}

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null | undefined>(undefined);

  const refresh = useCallback(async () => {
    try {
      setSession(await getAuthSession());
    } catch {
      setSession(null);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  // Google's sign-in pages set Cross-Origin-Opener-Policy, which can cut the popup off
  // from window.opener. Listen on same-origin channels that survive that as well.
  useEffect(() => {
    function onMessage(event: MessageEvent) {
      if (event.origin === window.location.origin && event.data === LOGIN_MESSAGE) void refresh();
    }
    function onStorage(event: StorageEvent) {
      if (event.key === STORAGE_KEY) void refresh();
    }
    const channel = typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel(CHANNEL_NAME);
    if (channel) channel.onmessage = (event) => { if (event.data === LOGIN_MESSAGE) void refresh(); };
    window.addEventListener("message", onMessage);
    window.addEventListener("storage", onStorage);
    return () => {
      channel?.close();
      window.removeEventListener("message", onMessage);
      window.removeEventListener("storage", onStorage);
    };
  }, [refresh]);

  const signIn = useCallback(() => {
    const popup = openLoginPopup();
    if (!popup) {
      // Popup blocked: fall back to a full-page redirect back to the current page.
      window.location.assign(loginUrl(window.location.pathname + window.location.search));
      return;
    }
    // Refresh once the window closes too, in case the message never arrives.
    const timer = window.setInterval(() => {
      if (popup.closed) {
        window.clearInterval(timer);
        void refresh();
      }
    }, 700);
  }, [refresh]);

  const signOut = useCallback(async () => {
    await logout();
    setSession(null);
  }, []);

  return <SessionContext.Provider value={{ session, refresh, signIn, signOut }}>{children}</SessionContext.Provider>;
}

/** Fixed session for tests and static rendering. */
export function StaticSessionProvider({ session, children }: { session: AuthSession | null | undefined; children: ReactNode }) {
  const noop = async () => {};
  return <SessionContext.Provider value={{ session, refresh: noop, signIn: () => {}, signOut: noop }}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionState {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}

export function loginUrl(returnTo: string): string {
  return `/api/auth/google/login?return_to=${encodeURIComponent(returnTo)}`;
}

function openLoginPopup(): Window | null {
  const width = 480;
  const height = 640;
  const left = window.screenX + Math.max(0, (window.outerWidth - width) / 2);
  const top = window.screenY + Math.max(0, (window.outerHeight - height) / 2);
  return window.open(
    loginUrl("/auth/complete"),
    POPUP_NAME,
    `popup=yes,width=${width},height=${height},left=${Math.round(left)},top=${Math.round(top)}`,
  );
}

/** Landing page inside the popup after Google sign-in: notify the opener and close. */
export function AuthCompletePage() {
  useEffect(() => {
    try { window.opener?.postMessage(LOGIN_MESSAGE, window.location.origin); } catch { /* opener cut off */ }
    if (typeof BroadcastChannel !== "undefined") {
      const channel = new BroadcastChannel(CHANNEL_NAME);
      channel.postMessage(LOGIN_MESSAGE);
      channel.close();
    }
    try { window.localStorage.setItem(STORAGE_KEY, String(Date.now())); } catch { /* storage blocked */ }
    window.close();
  }, []);
  return <div className="state-card"><strong>로그인을 완료했습니다.</strong><p>이 창이 닫히지 않으면 직접 닫아주세요.</p><a href="/">HateScope로 이동</a></div>;
}
