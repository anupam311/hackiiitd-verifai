"use client";

import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";

/** Natural-language search. Submitting runs a discovery search; empty submit lists stored opportunities. */
export function SearchBar({ value, onSubmit, busy, minLength }: { value: string; onSubmit: (q: string) => void; busy?: boolean; minLength: number }) {
  const [draft, setDraft] = useState(value);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setDraft(value), [value]);

  return (
    <form
      role="search"
      className="search-form"
      onSubmit={(e) => {
        e.preventDefault();
        const q = draft.trim();
        if (q.length > 0 && q.length < minLength) {
          setError(`Enter at least ${minLength} characters, or clear the box to browse stored opportunities.`);
          return;
        }
        setError(null);
        onSubmit(q);
      }}
    >
      <div className="search-row">
        <Search size={18} aria-hidden />
        <label htmlFor="opp-search" className="sr-only">
          Search opportunities
        </label>
        <input
          id="opp-search"
          type="search"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Search opportunities, e.g. “software engineering internships in Bengaluru”"
          aria-describedby={error ? "search-error" : undefined}
          aria-invalid={!!error}
          autoComplete="off"
        />
        <Button type="submit" variant="primary" loading={busy}>
          Search
        </Button>
      </div>
      {error && (
        <p id="search-error" className="field-error" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}
