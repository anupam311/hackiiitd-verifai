"use client";

import { FlaskConical } from "lucide-react";
import { useDemo } from "@/providers/DemoProvider";

/** Shown whenever fixtures are in use so sample results cannot be mistaken for live ones. */
export function SampleBanner() {
  const { demo, setDemo } = useDemo();
  if (!demo) return null;
  return (
    <div className="sample-banner" role="note">
      <FlaskConical size={16} aria-hidden />
      <p>
        <strong>Sample data.</strong> Organisations, sources, timestamps and evidence on screen are invented development fixtures — not live results and not about real opportunities.
      </p>
      <button className="link-btn" onClick={() => setDemo(false)}>
        Switch to live API
      </button>
    </div>
  );
}
