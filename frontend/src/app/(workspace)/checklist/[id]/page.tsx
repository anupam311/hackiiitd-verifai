"use client";

import { ChecklistPage } from "@/features/checklist/ChecklistPage";

export default function Page({ params }: { params: { id: string } }) {
  return <ChecklistPage id={decodeURIComponent(params.id)} />;
}
