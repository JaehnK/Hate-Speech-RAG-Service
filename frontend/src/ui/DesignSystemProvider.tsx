import { LinkProvider } from "@astryxdesign/core/Link";
import { Theme } from "@astryxdesign/core/theme";
import { forwardRef, type AnchorHTMLAttributes, type ReactNode } from "react";
import { Link as RouterLink } from "react-router-dom";

import { defaultThemeSlug, themes } from "../astryx-themes";

type RouterAnchorProps = AnchorHTMLAttributes<HTMLAnchorElement> & { href?: string; to?: string };

/** Routes in-app hrefs through react-router; external and hash links stay plain anchors. */
const AppLink = forwardRef<HTMLAnchorElement, RouterAnchorProps>(function AppLink({ href, to, ...rest }, ref) {
  const destination = to ?? href ?? "";
  const isInternal = destination.startsWith("/") && !destination.startsWith("//") && !destination.startsWith("/api/");
  if (isInternal && !rest.target) return <RouterLink ref={ref} to={destination} {...rest} />;
  return <a ref={ref} href={destination} {...rest} />;
});

export function DesignSystemProvider({ children }: { children: ReactNode }) {
  return (
    <Theme theme={themes[defaultThemeSlug]}>
      <LinkProvider component={AppLink}>{children}</LinkProvider>
    </Theme>
  );
}
