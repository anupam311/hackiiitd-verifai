"use client";

import { Bookmark, BookmarkCheck } from "lucide-react";
import { useState } from "react";
import type { Opportunity } from "@/types";
import { Button } from "@/components/ui/Button";
import { useSaved } from "@/features/saved/SavedProvider";

export function SaveButton({ opportunity, size = "sm", iconOnly = false }: { opportunity: Opportunity; size?: "sm" | "md"; iconOnly?: boolean }) {
  const { isSaved, toggle } = useSaved();
  const [busy, setBusy] = useState(false);
  const saved = isSaved(opportunity.id);
  const label = saved ? "Saved" : "Save";
  return (
    <Button
      size={size}
      variant="secondary"
      loading={busy}
      aria-pressed={saved}
      aria-label={`${saved ? "Remove from saved" : "Save"}: ${opportunity.title}`}
      className={saved ? "btn-saved" : ""}
      icon={saved ? <BookmarkCheck size={15} aria-hidden /> : <Bookmark size={15} aria-hidden />}
      onClick={async () => {
        setBusy(true);
        await toggle(opportunity);
        setBusy(false);
      }}
    >
      {iconOnly ? null : label}
    </Button>
  );
}
