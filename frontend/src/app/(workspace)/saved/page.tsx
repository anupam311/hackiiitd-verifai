import type { Metadata } from "next";
import { SavedView } from "@/features/saved/SavedView";

export const metadata: Metadata = { title: "Saved Opportunities" };

export default function SavedPage() {
  return <SavedView />;
}
