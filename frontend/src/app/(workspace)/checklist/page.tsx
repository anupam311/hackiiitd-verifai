import type { Metadata } from "next";
import { ChecklistIndex } from "@/features/checklist/ChecklistIndex";

export const metadata: Metadata = { title: "Application Checklists" };

export default function ChecklistsPage() {
  return <ChecklistIndex />;
}
