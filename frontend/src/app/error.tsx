"use client";

import { ErrorState } from "@/components/ui/States";

export default function GlobalError({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <main className="page" style={{ maxWidth: 640, margin: "10vh auto", padding: 24 }}>
      <ErrorState error={error} onRetry={reset} title="Something went wrong on this page" />
    </main>
  );
}
