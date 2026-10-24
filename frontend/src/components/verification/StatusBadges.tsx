import { AlertTriangle, Ban, CheckCircle2, CircleDashed, HelpCircle, ShieldAlert, ShieldCheck, ShieldQuestion } from "lucide-react";
import type { ClaimStatus, ReportStatus } from "@/types";
import { CLAIM_STATUS_HELP, CLAIM_STATUS_LABEL, REPORT_STATUS_LABEL, REPORT_STATUS_SHORT } from "@/lib/formatters";
import { claimTone, reportTone } from "@/lib/verification";
import { Badge } from "@/components/ui/Badge";

const CLAIM_ICON: Record<ClaimStatus, typeof CheckCircle2> = {
  confirmed: CheckCircle2,
  partially_confirmed: CircleDashed,
  conflicting: AlertTriangle,
  unverified: HelpCircle,
  unavailable: Ban,
};

/** Claim status — colour is never the only signal: each status has its own icon and label. */
export function ClaimStatusBadge({ status }: { status: ClaimStatus }) {
  const Icon = CLAIM_ICON[status];
  return (
    <Badge tone={claimTone(status)} icon={<Icon size={12} aria-hidden />} title={CLAIM_STATUS_HELP[status]}>
      {CLAIM_STATUS_LABEL[status]}
    </Badge>
  );
}

const REPORT_ICON: Record<ReportStatus, typeof ShieldCheck> = {
  verified_no_conflicts: ShieldCheck,
  conflicts_detected: ShieldAlert,
  partially_verified: ShieldQuestion,
  verification_incomplete: ShieldQuestion,
};

export function ReportStatusBadge({ status, short = false }: { status: ReportStatus; short?: boolean }) {
  const Icon = REPORT_ICON[status];
  return (
    <Badge tone={reportTone(status)} icon={<Icon size={12} aria-hidden />}>
      {short ? REPORT_STATUS_SHORT[status] : REPORT_STATUS_LABEL[status]}
    </Badge>
  );
}

export function NoReportBadge() {
  return (
    <Badge tone="gray" icon={<HelpCircle size={12} aria-hidden />} title="No verification report has been generated for this opportunity yet.">
      Not yet verified
    </Badge>
  );
}
