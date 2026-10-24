import type { Metadata } from "next";
import { RecheckView } from "@/features/verification/RecheckView";

export const metadata: Metadata = { title: "Recheck" };

export default function RecheckPage({ searchParams }: { searchParams: { opp?: string; run?: string } }) {
  return <RecheckView initialOpp={searchParams.opp} initialRun={searchParams.run} />;
}
