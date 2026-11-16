import { Button } from "@astryxdesign/core/Button";
import { EmptyState } from "@astryxdesign/core/EmptyState";
import { LogIn } from "lucide-react";
import { lazy, type ReactNode, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { HomePage } from "./pages/HomePage";
import { AuthCompletePage, SessionProvider, useSession } from "./session";
import { AppLayout } from "./shell/AppLayout";
import { LoadingState } from "./ui/common";

const HistoryPage = lazy(() => import("./pages/HistoryPage").then((m) => ({ default: m.HistoryPage })));
const JobPage = lazy(() => import("./pages/JobPage").then((m) => ({ default: m.JobPage })));
const ReportPage = lazy(() => import("./pages/ReportPage").then((m) => ({ default: m.ReportPage })));
const MethodologyPage = lazy(() => import("./pages/MethodologyPage").then((m) => ({ default: m.MethodologyPage })));
const SettingsPage = lazy(() => import("./pages/SettingsPage").then((m) => ({ default: m.SettingsPage })));

const page = (node: ReactNode) => <Suspense fallback={<LoadingState label="화면을 불러오는 중입니다" />}>{node}</Suspense>;

export default function App() {
  return <SessionProvider><AppRoutes /></SessionProvider>;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/auth/complete" element={<AuthCompletePage />} />
      <Route element={<AppLayout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/history" element={<RequireSession>{page(<HistoryPage />)}</RequireSession>} />
        <Route path="/jobs/:jobId" element={page(<JobPage />)} />
        <Route path="/reports/:reportId" element={page(<ReportPage />)} />
        <Route path="/rag-methodology" element={page(<MethodologyPage />)} />
        <Route path="/settings" element={<RequireSession>{page(<SettingsPage />)}</RequireSession>} />
        {/* Older links: samples now live on the home page. */}
        <Route path="/samples" element={<Navigate to="/#samples" replace />} />
        <Route path="/analyze" element={<Navigate to="/" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function RequireSession({ children }: { children: ReactNode }) {
  const { session, signIn } = useSession();
  if (session === undefined) return <LoadingState label="로그인 상태를 확인하는 중입니다" />;
  if (session === null) {
    return (
      <div className="hs-state">
        <EmptyState
          title="로그인이 필요합니다"
          description="Google 계정으로 로그인하면 내 분석과 계정 설정을 볼 수 있습니다."
          icon={<LogIn size={28} aria-hidden />}
          actions={<Button variant="primary" label="Google 로그인" onClick={signIn} />}
        />
      </div>
    );
  }
  return <>{children}</>;
}
