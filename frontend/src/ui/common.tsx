import { Badge } from "@astryxdesign/core/Badge";
import { Button } from "@astryxdesign/core/Button";
import { EmptyState } from "@astryxdesign/core/EmptyState";
import { Heading } from "@astryxdesign/core/Heading";
import { Spinner } from "@astryxdesign/core/Spinner";
import { Text } from "@astryxdesign/core/Text";
import { AlertCircle } from "lucide-react";
import type { ReactNode } from "react";

import { statusText } from "../labels";

/**
 * Badges mark exceptional states only. A finished job reads as plain text;
 * failure is gray so it never collides with the red used for hate data.
 */
export function StatusLabel({ status }: { status: string }) {
  const text = statusText(status);
  switch (status) {
    case "running":
      return <Badge variant="blue" label={text} />;
    case "pending":
      return <Badge variant="neutral" label={text} />;
    case "partial_success":
      return <Badge variant="yellow" label={text} />;
    case "failed":
      return <Badge variant="neutral" label={text} icon={<AlertCircle size={12} aria-hidden />} />;
    default:
      return <Text type="supporting">{text}</Text>;
  }
}

export function PageHeader({ title, description, children }: { title: ReactNode; description?: ReactNode; children?: ReactNode }) {
  return (
    <header className="hs-page-header">
      <div>
        <Heading level={1}>{title}</Heading>
        {description && <Text type="supporting" as="p">{description}</Text>}
      </div>
      {children}
    </header>
  );
}

export function SectionHeader({ title, children, level = 2 }: { title: ReactNode; children?: ReactNode; level?: 2 | 3 }) {
  return (
    <div className="hs-section-header">
      <Heading level={level}>{title}</Heading>
      {children}
    </div>
  );
}

export function LoadingState({ label }: { label: string }) {
  return <div className="hs-state" role="status"><Spinner size="lg" label={label} /></div>;
}

export function ErrorState({ message, actionLabel = "새 분석 시작", actionHref = "/" }: { message: string; actionLabel?: string; actionHref?: string }) {
  return (
    <div className="hs-state" role="alert">
      <EmptyState
        title={message}
        icon={<AlertCircle size={28} aria-hidden />}
        actions={<Button label={actionLabel} href={actionHref} />}
      />
    </div>
  );
}
