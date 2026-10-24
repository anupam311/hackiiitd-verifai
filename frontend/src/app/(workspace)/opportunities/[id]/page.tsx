"use client";

import { Suspense } from "react";
import { OpportunityDetail } from "@/components/opportunities/OpportunityDetail";
import { SkeletonCards } from "@/components/ui/States";

export default function OpportunityPage({ params }: { params: { id: string } }) {
  const id = decodeURIComponent(params.id);
  return (
    <Suspense fallback={<div className="page"><SkeletonCards count={2} /></div>}>
      <OpportunityDetail id={id} />
    </Suspense>
  );
}
