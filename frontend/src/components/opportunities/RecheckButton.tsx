"use client";

import { RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { startRecheck } from "@/features/verification/api";
import { describeError } from "@/lib/api-errors";
import { useDemo } from "@/providers/DemoProvider";
import { useToast } from "@/providers/ToastProvider";

/**
 * Starts a real recheck run through the backend. In sample mode no run is started;
 * the user is taken to the Recheck page to inspect the stored sample run instead.
 */
export function RecheckButton({ opportunityId, size = "sm", variant = "secondary", label = "Recheck" }: { opportunityId: string; size?: "sm" | "md"; variant?: "primary" | "secondary"; label?: string }) {
  const { demo } = useDemo();
  const router = useRouter();
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  const onClick = async () => {
    if (demo) {
      toast({ tone: "info", title: "Sample mode — no live recheck was run", body: "Showing the stored sample run. Switch off sample data and connect the backend to run real rechecks." });
      router.push(`/recheck?opp=${encodeURIComponent(opportunityId)}`);
      return;
    }
    setBusy(true);
    try {
      const { runId } = await startRecheck(opportunityId);
      toast({ tone: "success", title: "Recheck started", body: "Following the run on the Recheck page." });
      router.push(`/recheck?opp=${encodeURIComponent(opportunityId)}&run=${encodeURIComponent(runId)}`);
    } catch (e) {
      const d = describeError(e);
      toast({ tone: "error", title: `Recheck not started — ${d.title}`, body: d.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Button size={size} variant={variant} loading={busy} onClick={onClick} icon={<RefreshCw size={15} aria-hidden />}>
      {label}
    </Button>
  );
}
