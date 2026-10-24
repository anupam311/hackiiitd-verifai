"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ConflictBanner } from "@/components/comparison/ConflictBanner";
import { OpportunityCompareTable } from "@/components/comparison/OpportunityCompareTable";
import { SourceComparisonTable } from "@/components/comparison/SourceComparisonTable";
import { SourceCard } from "@/components/evidence/SourceCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { OpportunityPicker } from "@/components/opportunities/OpportunityPicker";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState, ErrorState, SkeletonCards } from "@/components/ui/States";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import { useCompare } from "@/features/comparison/CompareProvider";
import { useOpportunityChoices } from "@/features/discovery/useChoices";
import { getSources } from "@/features/verification/api";
import { useAsync } from "@/hooks/useAsync";
import { ApiError } from "@/lib/api-errors";
import { useDemo } from "@/providers/DemoProvider";
import { LinkButton } from "@/components/ui/Button";

export function CompareView({ initialTab, initialOpp }: { initialTab?: string; initialOpp?: string }) {
  const { demo, ready } = useDemo();
  const router = useRouter();
  const { selected } = useCompare();
  const { choices, loading } = useOpportunityChoices();
  const [tab, setTab] = useState(initialTab === "opportunities" ? "opportunities" : "sources");
  const [oppId, setOppId] = useState(initialOpp ?? "");

  useEffect(() => {
    if (!oppId && choices.length > 0 && tab === "sources") setOppId(choices[0].id);
  }, [choices, oppId, tab]);

  const sources = useAsync((s) => getSources(demo, oppId, s), [demo, oppId], ready && !!oppId && tab === "sources");

  return (
    <div className="page">
      <PageHeader
        eyebrow="Side-by-side evidence"
        title="Compare Sources"
        subtitle="See where sources agree, differ or say nothing — and compare opportunities without hiding unknowns."
      />
      <Tabs
        label="Comparison mode"
        idPrefix="cmp"
        active={tab}
        onChange={(t) => {
          setTab(t);
          router.replace(`/compare?tab=${t}`, { scroll: false });
        }}
        tabs={[
          { id: "sources", label: "Compare sources" },
          { id: "opportunities", label: "Compare opportunities", badge: selected.length ? <span className="tab-count">{selected.length}</span> : null },
        ]}
      />

      <TabPanel id="sources" active={tab} idPrefix="cmp">
        <div className="picker-row">
          <OpportunityPicker choices={choices} value={oppId} onChange={setOppId} label="Opportunity to inspect" />
        </div>
        {loading && !choices.length ? <SkeletonCards count={1} /> : !oppId ? (
          <EmptyState title="Choose an opportunity">Pick an opportunity to compare the sources VERIFAI retrieved for it.</EmptyState>
        ) : sources.loading ? (
          <SkeletonCards count={2} />
        ) : sources.error ? (
          sources.error instanceof ApiError && sources.error.kind === "not_implemented" ? (
            <EmptyState title="No source evidence yet">No sources have been stored for this opportunity. Run a recheck to retrieve them.</EmptyState>
          ) : (
            <ErrorState error={sources.error} onRetry={sources.reload} />
          )
        ) : sources.data ? (
          <div className="stack">
            <ConflictBanner comparison={sources.data} />
            <Card>
              <CardHeader title="Claim-by-claim comparison" />
              <SourceComparisonTable comparison={sources.data} />
            </Card>
            <div className="source-grid">{sources.data.sources.map((s) => <SourceCard key={s.id} source={s} />)}</div>
          </div>
        ) : null}
      </TabPanel>

      <TabPanel id="opportunities" active={tab} idPrefix="cmp">
        {selected.length < 2 ? (
          <EmptyState title={selected.length === 0 ? "Nothing selected to compare" : "Select at least one more"} action={<LinkButton href="/explore" variant="primary">Go to Discover</LinkButton>}>
            Tick “Compare” on opportunity cards in Discover (up to 3), then return here to see them side by side.
          </EmptyState>
        ) : (
          <OpportunityCompareTable opportunities={selected} />
        )}
      </TabPanel>
    </div>
  );
}
