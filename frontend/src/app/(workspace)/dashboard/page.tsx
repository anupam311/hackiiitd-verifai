import type { Metadata } from "next";
import { DashboardView } from "@/features/discovery/DashboardView";

export const metadata: Metadata = { title: "Overview" };

export default function DashboardPage() {
  return <DashboardView />;
}
