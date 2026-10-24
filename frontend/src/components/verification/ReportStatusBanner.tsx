import type { ReactNode } from "react";
import { ShieldAlert, ShieldCheck, ShieldQuestion } from "lucide-react";
import type { ReportStatus } from "@/types";
import { REPORT_STATUS_LABEL } from "@/lib/formatters";
import { reportTone } from "@/lib/verification";

const ICON = { verified_no_conflicts: ShieldCheck, conflicts_detected: ShieldAlert, partially_verified: ShieldQuestion, verification_incomplete: ShieldQuestion } as const;

export function ReportStatusBanner({ status, children, actions }: { status: ReportStatus; children: ReactNode; actions?: ReactNode }) {
  const Icon = ICON[status];
  return (
    <div className={`report-banner report-${reportTone(status)}`}>
      <Icon size={26} aria-hidden />
      <div className="report-banner-text">
        <h2>{REPORT_STATUS_LABEL[status]}</h2>
        <p>{children}</p>
      </div>
      {actions}
    </div>
  );
}
