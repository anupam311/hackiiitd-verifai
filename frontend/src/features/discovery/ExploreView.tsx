"use client";

import { useMemo, useState } from "react";
import { GitCompare, SearchX } from "lucide-react";
import Link from "next/link";
import { FilterBar } from "@/components/opportunities/FilterBar";
import { OpportunityCard } from "@/components/opportunities/OpportunityCard";
import { SearchBar } from "@/components/opportunities/SearchBar";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Select } from "@/components/ui/Field";
import { EmptyState, ErrorState, Notice, SkeletonCards } from "@/components/ui/States";
import { RunTimeline } from "@/components/verification/RunTimeline";
import { useCompare } from "@/features/comparison/CompareProvider";
import { useRun } from "@/features/verification/useRun";
import { useAsync } from "@/hooks/useAsync";
import { PAGE_SIZE } from "@/lib/config";
import { useDemo } from "@/providers/DemoProvider";
import { listOpportunities, searchOpportunities } from "./api";
import { DEFAULT_FILTERS, matchesFilters, sortOpportunities, type FilterState, type SortKey } from "./filters";

const MIN_QUERY = 2;

export function ExploreView({ initialQuery = "" }: { initialQuery?: string }) {
  const { demo, ready } = useDemo();
  const { selected } = useCompare();
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [submitted, setSubmitted] = useState(initialQuery);
  const [visible, setVisible] = useState(PAGE_SIZE);

  // Server-side work: only the query. Remaining filters are applied client-side to the returned set.
  const search = useAsync(
    (signal) => (submitted ? searchOpportunities(demo, { query: submitted, limit: 50 }, signal) : listOpportunities(demo, signal)),
    [demo, submitted],
    ready,
  );
  const result = search.data;
  const { run, error: runError } = useRun(result?.run_id ?? null, demo);

  const all = useMemo(() => result?.opportunities ?? [], [result]);
  const filtered = useMemo(() => sortOpportunities(all.filter((o) => matchesFilters(o, { ...filters, query: "" })), filters), [all, filters]);
  const shown = filtered.slice(0, visible);

  const onFilters = (f: FilterState) => {
    setFilters(f);
    setVisible(PAGE_SIZE);
  };
  const partial = result && (result.state === "partial" || result.state === "failed");
  const running = result && (result.state === "queued" || result.state === "running");

  return (
    <div className="page">
      <PageHeader eyebrow="Evidence-first discovery" title="Discover Opportunities" subtitle="Find opportunities from across the web, then verify each claim against traceable sources." />

      <SearchBar
        value={submitted}
        busy={search.loading}
        minLength={MIN_QUERY}
        onSubmit={(q) => {
          setSubmitted(q);
          setVisible(PAGE_SIZE);
        }}
      />
      <FilterBar filters={filters} onChange={onFilters} results={all} />

      {result?.run_id && (
        <Card className="run-card">
          <CardHeader title="Search progress" as="h2" />
          <RunTimeline run={run} error={runError} emptyMessage="Waiting for the backend to report the first event…" />
          <p className="muted small">Progress shows events reported by the backend run. Search runs cannot be cancelled from here because the backend does not expose cancellation.</p>
        </Card>
      )}

      {result && result.warnings.length > 0 && (
        <Notice tone={demo ? "info" : "warn"} title={partial ? "Partial results" : demo ? "Sample data" : "Notice from the API"}>
          {result.warnings.join(" ")}
        </Notice>
      )}
      {running && <Notice tone="info" title="Search still running">Results below may be incomplete until the run finishes.</Notice>}

      <div className="results-bar">
        <p className="results-count" role="status" aria-live="polite">
          {search.loading ? "Searching…" : result ? `Showing ${Math.min(shown.length, filtered.length)} of ${filtered.length} result${filtered.length === 1 ? "" : "s"}${submitted ? ` for “${submitted}”` : ""}` : ""}
        </p>
        <Select
          label="Sort by"
          hideLabel={false}
          value={filters.sort}
          onChange={(v) => onFilters({ ...filters, sort: v as SortKey })}
          options={[
            { value: "relevance", label: "Relevance (keyword match)" },
            { value: "deadline", label: "Deadline (soonest first)" },
            { value: "completeness", label: "Verification completeness" },
          ]}
        />
      </div>
      <p className="muted small relevance-note">Relevance and verification are separate: a closely matching opportunity is not necessarily a verified one.</p>

      {search.loading && !result && <SkeletonCards count={3} label="Loading opportunities" />}
      {search.error ? <ErrorState error={search.error} onRetry={search.reload} title="Could not load opportunities" /> : null}

      {!search.loading && !search.error && result && filtered.length === 0 && (
        <EmptyState
          icon={<SearchX size={22} />}
          title={all.length === 0 ? (submitted ? "No opportunities found" : "No opportunities to show yet") : "No results match these filters"}
          action={all.length > 0 ? <Button onClick={() => onFilters({ ...DEFAULT_FILTERS, sort: filters.sort })}>Reset filters</Button> : undefined}
        >
          {all.length === 0
            ? demo
              ? "No sample opportunity matches that search. Try a broader query."
              : "Nothing was returned by the API. Run a search above to discover opportunities. If the backend's discovery provider is not configured, no live results will be returned."
            : "Try removing a filter or broadening your search."}
        </EmptyState>
      )}

      <div className="opp-list" aria-live="polite">
        {shown.map((o) => (
          <OpportunityCard key={o.id} opportunity={o} />
        ))}
      </div>

      {filtered.length > shown.length && (
        <div className="load-more">
          <Button onClick={() => setVisible((v) => v + PAGE_SIZE)}>Load more ({filtered.length - shown.length} remaining)</Button>
        </div>
      )}

      {selected.length > 0 && (
        <div className="compare-tray" role="region" aria-label="Comparison selection">
          <GitCompare size={18} aria-hidden />
          <span>
            <strong>{selected.length}</strong> selected for comparison: {selected.map((s) => s.title).join(", ")}
          </span>
          <Link href="/compare?tab=opportunities" className="btn btn-primary btn-sm">
            Compare
          </Link>
        </div>
      )}
    </div>
  );
}
