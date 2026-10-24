import type { Metadata } from "next";
import { ExploreView } from "@/features/discovery/ExploreView";

export const metadata: Metadata = { title: "Discover" };

export default function ExplorePage({ searchParams }: { searchParams: { q?: string } }) {
  return <ExploreView initialQuery={searchParams.q?.slice(0, 500) ?? ""} />;
}
