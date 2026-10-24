import type { Metadata } from "next";
import { CompareView } from "@/features/compare/CompareView";

export const metadata: Metadata = { title: "Compare Sources" };

export default function ComparePage({ searchParams }: { searchParams: { tab?: string; opp?: string } }) {
  return <CompareView initialTab={searchParams.tab} initialOpp={searchParams.opp} />;
}
