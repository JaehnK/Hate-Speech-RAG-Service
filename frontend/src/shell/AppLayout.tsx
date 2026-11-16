import { AppShell } from "@astryxdesign/core/AppShell";
import { Avatar } from "@astryxdesign/core/Avatar";
import { Button } from "@astryxdesign/core/Button";
import { DropdownMenu } from "@astryxdesign/core/DropdownMenu";
import { Spinner } from "@astryxdesign/core/Spinner";
import { TopNav, TopNavItem } from "@astryxdesign/core/TopNav";
import { Plus } from "lucide-react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";

import { useSession } from "../session";

export function AppLayout() {
  return (
    <AppShell variant="elevated" height="auto" topNav={<Header />}>
      <Outlet />
    </AppShell>
  );
}

function Header() {
  const { session, signIn, signOut } = useSession();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const active = (prefix: string) => pathname === prefix || pathname.startsWith(`${prefix}/`);

  async function onSignOut() {
    await signOut();
    navigate("/");
  }

  return (
    <TopNav
      label="주 메뉴"
      heading={<Link className="hs-brand" to="/">HateScope</Link>}
      startContent={
        <>
          {session && <TopNavItem label="내 분석" href="/history" isSelected={active("/history") || active("/jobs")} />}
          <TopNavItem label="방법론" href="/rag-methodology" isSelected={active("/rag-methodology")} />
        </>
      }
      endContent={
        <div className="hs-header-end">
          <Button variant="primary" size="sm" label="새 분석" icon={<Plus size={16} aria-hidden />} href="/" />
          {session === undefined ? (
            <Spinner size="sm" aria-label="로그인 상태 확인 중" />
          ) : session === null ? (
            <Button size="sm" label="Google 로그인" onClick={signIn} />
          ) : (
            <DropdownMenu
              alignment="end"
              hasChevron={false}
              renderTrigger={(props) => (
                <button {...props} type="button" className="hs-account-trigger" aria-label="계정 메뉴">
                  <Avatar size="sm" name={session.display_name ?? session.email} src={session.avatar_url ?? undefined} tooltip={false} />
                </button>
              )}
              items={[
                {
                  type: "section",
                  title: session.display_name ?? session.email,
                  items: [
                    { label: "계정 설정", href: "/settings" },
                    { label: "로그아웃", onClick: () => void onSignOut() },
                  ],
                },
              ]}
            />
          )}
        </div>
      }
    />
  );
}
