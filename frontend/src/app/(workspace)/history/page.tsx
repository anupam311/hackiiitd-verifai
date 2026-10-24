import type { Metadata } from "next";
import { HistoryView } from "@/features/history/HistoryView";

export const metadata: Metadata = { title: "History" };

export default function HistoryPage({ searchParams }: { searchParams: { opp?: string } }) {
  return <HistoryView initialOpp={searchParams.opp} />;
}
