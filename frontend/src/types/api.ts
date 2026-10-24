import type {
  AppNotification,
  ApplicantProfile,
  Opportunity,
  Run,
  RunState,
  Snapshot,
  SourceComparison,
  VerificationReport,
} from "./domain";

/** Discovery search request — see docs/api.md `POST /api/v1/discovery/search`. */
export interface DiscoverySearchRequest {
  query: string;
  location?: string | null;
  categories?: string[];
  fields_of_study?: string[];
  deadline_before?: string | null;
  limit?: number;
}

export interface DiscoverySearchResponse {
  run_id: string | null;
  state: RunState;
  opportunities: Opportunity[];
  warnings: string[];
}

export interface OpportunityListResponse {
  items: Opportunity[];
  total: number;
  note?: string;
}

export interface RecheckResponse {
  run_id: string;
  state: RunState;
}

export type ReportResponse = VerificationReport;
export type SourcesResponse = SourceComparison;
export interface HistoryResponse {
  snapshots: Snapshot[];
}
export type RunResponse = Run;
export type ProfileResponse = ApplicantProfile;
export interface SavedResponse {
  items: Opportunity[];
  savedAt: Record<string, string>;
}
export interface NotificationsResponse {
  items: AppNotification[];
}

/** Standard error envelope from docs/api.md. */
export interface ApiErrorEnvelope {
  error: { code: string; message: string; request_id?: string };
}
