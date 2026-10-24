/**
 * DEVELOPMENT FIXTURES — SAMPLE DATA ONLY.
 *
 * Everything in this file is invented for UI development. Organisations are
 * fictional, URLs use the reserved `.example` TLD, and no excerpt, timestamp or
 * value here is evidence about a real opportunity. The UI shows a persistent
 * "Sample data" banner whenever these fixtures are in use, and they are only
 * loaded when the Sample-data switch is on (see providers/DemoProvider).
 *
 * Replace by real responses from the FastAPI backend (see lib/api-client.ts).
 */
import type {
  AppNotification,
  ApplicantProfile,
  Claim,
  ClaimEvidence,
  ClaimStatus,
  ClaimType,
  Opportunity,
  Run,
  Snapshot,
  SourceObservation,
  VerificationReport,
} from "@/types";
import { countClaims, deriveReportStatus } from "@/lib/verification";

/* ───────────── builders ───────────── */

const T_LATEST = "2026-10-22T09:14:00Z";
const T_MID = "2026-10-14T06:40:00Z";
const T_OLD = "2026-10-03T11:05:00Z";

function src(id: string, name: string, url: string, sourceType: SourceObservation["sourceType"], over: Partial<SourceObservation> = {}): SourceObservation {
  return {
    id,
    name,
    url,
    domain: new URL(url).hostname,
    sourceType,
    retrievedAt: T_LATEST,
    httpStatus: 200,
    outcome: "ok",
    freshness: "fresh",
    ...over,
  };
}

function ev(sourceId: string, extractedValue: string | null, excerpt: string | null, locator?: string): ClaimEvidence {
  return { sourceId, extractedValue, excerpt, locator: locator ?? null, extractionConfidence: excerpt ? "high" : null };
}

function claim(
  oppId: string,
  type: ClaimType,
  status: ClaimStatus,
  originalWording: string | null,
  normalizedValue: string | null,
  explanation: string,
  evidence: ClaimEvidence[],
  nextStep?: string,
): Claim {
  return { id: `${oppId}:${type}`, type, status, originalWording, normalizedValue, explanation, evidence, nextStep };
}

function report(
  opportunityId: string,
  claims: Claim[],
  sources: SourceObservation[],
  unresolvedQuestions: string[],
  limitations: string[],
  runId: string | null = `sample-run-${opportunityId}`,
): VerificationReport {
  return { opportunityId, runId, generatedAt: T_LATEST, claims, sources, unresolvedQuestions, limitations, isSample: true };
}

const STD_LIMITS = [
  "Sample report: values, excerpts and timestamps are invented fixtures, not evidence about a real opportunity.",
  "Source pages can change after retrieval; confirm critical details on the official page before applying.",
];

/* ───────────── 1. Helio — stipend conflict ───────────── */

const HELIO = "demo-helio-swe";
const helioSources = [
  src("helio-official", "Helio careers — student programmes", "https://careers.helio.example/students/swe-intern", "official"),
  src("helio-board", "InternBoard listing", "https://internboard.example/listings/helio-swe-2027", "aggregator", { retrievedAt: "2026-10-22T09:15:00Z" }),
  src("helio-forum", "CampusTalk discussion thread", "https://campustalk.example/t/helio-intern-stipend", "community", { retrievedAt: "2026-10-22T09:15:30Z", freshness: "stale" }),
  src("helio-pdf", "Helio programme brochure (PDF)", "https://careers.helio.example/files/swe-intern-brochure.pdf", "official", {
    retrievedAt: "2026-10-22T09:16:00Z",
    httpStatus: null,
    outcome: "timeout",
    freshness: "unknown",
    note: "The request timed out. This is not evidence that the programme is closed.",
  }),
];
const helioClaims: Claim[] = [
  claim(HELIO, "deadline", "confirmed", "Apply by 15 December 2026", "2026-12-15", "The official page states the deadline and the aggregator repeats the same date.", [
    ev("helio-official", "15 Dec 2026", "Applications close on 15 December 2026, 23:59 IST.", "Section: Key dates"),
    ev("helio-board", "Dec 15, 2026", "Apply by Dec 15, 2026"),
  ]),
  claim(HELIO, "application_status", "confirmed", "Applications open", "open", "The official page shows an active application button and open-for-applications wording.", [
    ev("helio-official", "Open", "Applications are now open for the 2027 intake.", "Header banner"),
  ]),
  claim(HELIO, "application_url", "confirmed", "careers.helio.example/students/apply", "https://careers.helio.example/students/apply", "The link is on the official domain and is referenced from the official programme page.", [
    ev("helio-official", "https://careers.helio.example/students/apply", "Apply now → careers.helio.example/students/apply", "Primary call-to-action"),
  ]),
  claim(HELIO, "eligibility", "partially_confirmed", "BE/BTech in CS, IT or related fields", "BE/BTech; CS, IT or related", "The official page lists BE/BTech in CS/IT, but 'related fields' is not defined, and the brochure that may clarify it could not be retrieved.", [
    ev("helio-official", "BE/BTech (CS, IT)", "Open to students pursuing BE/BTech in Computer Science, IT or related disciplines.", "Section: Who can apply"),
    ev("helio-board", "BE/BTech (CS, IT)", "Eligibility: BE/BTech CS/IT"),
  ], "Check the brochure or ask the recruiter what counts as a 'related' discipline."),
  claim(HELIO, "stipend", "conflicting", "₹1,20,000 per month", "₹1,20,000 / month (official) vs ₹1,10,000 / month (aggregator)", "The official page and an aggregator state different monthly amounts. The aggregator may be out of date, but that is not established.", [
    ev("helio-official", "₹1,20,000 / month", "Monthly stipend of ₹1,20,000 for the 12-week programme.", "Section: Benefits"),
    ev("helio-board", "₹1,10,000 / month", "Stipend: ₹1,10,000 per month"),
    ev("helio-forum", "~₹1,00,000 / month", "I think the stipend last year was around 1L a month?"),
  ], "Treat the official page as the authority and confirm the amount in your offer letter."),
  claim(HELIO, "location", "confirmed", "Bengaluru, India", "Bengaluru, India", "Official and aggregator sources agree.", [
    ev("helio-official", "Bengaluru, India", "Location: Bengaluru, India (on-site).", "Section: Programme details"),
    ev("helio-board", "Bengaluru, India", "Bengaluru"),
  ]),
  claim(HELIO, "duration", "confirmed", "12 weeks", "12 weeks", "Both retrieved sources state 12 weeks.", [
    ev("helio-official", "12 weeks", "A 12-week summer programme.", "Section: Programme details"),
    ev("helio-board", "12 weeks", "Duration: 12 weeks"),
  ]),
];
const helioReport = report(
  HELIO,
  helioClaims,
  helioSources,
  [
    "Which stipend figure is current? The official page and an aggregator disagree.",
    "What counts as a 'related' discipline for eligibility?",
    "The programme brochure (PDF) could not be retrieved, so its contents were not checked.",
  ],
  [...STD_LIMITS, "One official source timed out; the claims it may contain were not evaluated against it."],
);

/* ───────────── 2. Brightpath — partial, no conflicts ───────────── */

const BRIGHT = "demo-brightpath-explore";
const brightSources = [
  src("bright-official", "Brightpath Explore programme page", "https://explore.brightpath.example/internship", "official"),
  src("bright-board", "InternBoard listing", "https://internboard.example/listings/brightpath-explore", "aggregator", { freshness: "stale", retrievedAt: "2026-10-22T09:20:00Z" }),
  src("bright-faq", "Brightpath FAQ", "https://explore.brightpath.example/faq", "official", {
    retrievedAt: "2026-10-22T09:21:00Z", httpStatus: 403, outcome: "blocked", freshness: "unknown",
    note: "The page blocked automated access. This is not evidence of closure or of missing information.",
  }),
];
const brightClaims: Claim[] = [
  claim(BRIGHT, "deadline", "confirmed", "Applications due 30 November 2026", "2026-11-30", "The official page states this date.", [
    ev("bright-official", "30 Nov 2026", "Submit your application by 30 November 2026.", "Section: Timeline"),
  ]),
  claim(BRIGHT, "application_status", "confirmed", "Open", "open", "The official page shows the application form as active.", [
    ev("bright-official", "Open", "Applications are open.", "Header banner"),
  ]),
  claim(BRIGHT, "application_url", "confirmed", "explore.brightpath.example/apply", "https://explore.brightpath.example/apply", "The link is on the official domain.", [
    ev("bright-official", "https://explore.brightpath.example/apply", "Start your application", "Primary call-to-action"),
  ]),
  claim(BRIGHT, "eligibility", "unverified", "Open to students in technology programmes", null, "Only an aggregator describes eligibility; the official page does not state criteria on the retrieved page and the FAQ was blocked.", [
    ev("bright-board", "Technology students", "Open to technology students"),
  ], "Open the official FAQ in your browser to read the eligibility criteria."),
  claim(BRIGHT, "stipend", "unavailable", null, null, "No retrieved source states a stipend, and the FAQ that may contain it was blocked.", [], "Check the official FAQ or ask the recruiting team."),
  claim(BRIGHT, "location", "confirmed", "Hyderabad, India", "Hyderabad, India", "The official page states the location.", [
    ev("bright-official", "Hyderabad, India", "Location: Hyderabad, India", "Section: Programme details"),
  ]),
  claim(BRIGHT, "duration", "partially_confirmed", "10–12 weeks", "10–12 weeks (range)", "The official page gives a range, so the exact duration is not determined.", [
    ev("bright-official", "10–12 weeks", "Programmes run for 10 to 12 weeks depending on team.", "Section: Programme details"),
  ]),
];
const brightReport = report(
  BRIGHT,
  brightClaims,
  brightSources,
  ["What are the eligibility criteria?", "Is a stipend offered, and how much?", "The FAQ page was blocked, so its contents are unknown."],
  [...STD_LIMITS, "Only one retrieved source is official; independent corroboration is limited."],
);

/* ───────────── 3. Meridian — verified, single source ───────────── */

const MERID = "demo-meridian-scholarship";
const meridSources = [src("merid-official", "Meridian Foundation scholarship page", "https://meridianfoundation.example/scholarships/undergraduate", "official")];
const meridClaims: Claim[] = [
  claim(MERID, "deadline", "confirmed", "Last date: 31 January 2027", "2027-01-31", "The official page states the date.", [ev("merid-official", "31 Jan 2027", "Applications close on 31 January 2027.", "Section: Important dates")]),
  claim(MERID, "application_status", "confirmed", "Applications open", "open", "The official page states that applications are open.", [ev("merid-official", "Open", "The 2027 round is open for applications.", "Header")]),
  claim(MERID, "application_url", "confirmed", "meridianfoundation.example/apply", "https://meridianfoundation.example/apply", "The link is on the official domain.", [ev("merid-official", "https://meridianfoundation.example/apply", "Apply online", "Primary call-to-action")]),
  claim(MERID, "eligibility", "confirmed", "Undergraduate students with family income below a stated threshold", "Undergraduate; income-based", "The official page lists the criteria.", [ev("merid-official", "Undergraduate; income-based", "Open to undergraduate students; annual family income below ₹8,00,000.", "Section: Eligibility")]),
  claim(MERID, "stipend", "confirmed", "₹60,000 per year", "₹60,000 / year", "The official page states the award.", [ev("merid-official", "₹60,000 / year", "Award: ₹60,000 per academic year.", "Section: Award")]),
  claim(MERID, "location", "confirmed", "Pan India", "India (any)", "The official page states nationwide eligibility.", [ev("merid-official", "Pan India", "Open to students across India.", "Section: Eligibility")]),
];
const meridReport = report(MERID, meridClaims, meridSources, [], [...STD_LIMITS, "Only one source was retrieved. Independent corroboration is limited: a single source can be wrong or out of date."]);

/* ───────────── 4. Aldrin — incomplete, deadline unknown ───────────── */

const ALDRIN = "demo-aldrin-research";
const aldrinSources = [
  src("aldrin-official", "Aldrin Institute summer programme", "https://aldrin-institute.example/summer", "institution", { retrievedAt: "2026-10-22T09:30:00Z" }),
  src("aldrin-board", "ResearchHub listing", "https://researchhub.example/p/aldrin-summer", "aggregator", { outcome: "not_found", httpStatus: 404, freshness: "unknown", retrievedAt: "2026-10-22T09:31:00Z", note: "The listing was not found. This is not evidence that the programme is closed." }),
];
const aldrinClaims: Claim[] = [
  claim(ALDRIN, "deadline", "unverified", null, null, "No deadline was found on the retrieved page. It is shown as unknown rather than estimated.", [], "Check the institute's page directly or contact the programme office."),
  claim(ALDRIN, "application_status", "unverified", "Applications for 2027 — details to follow", null, "The page mentions future applications but does not say whether they are open.", [ev("aldrin-official", "Details to follow", "Applications for the 2027 programme will be announced.", "Home banner")]),
  claim(ALDRIN, "application_url", "unavailable", null, null, "No application link was found and the second source could not be retrieved.", []),
  claim(ALDRIN, "eligibility", "partially_confirmed", "Strong academic record in science or engineering", "Science / engineering students", "The page names fields but not the education level or any grade threshold.", [ev("aldrin-official", "Science / engineering students", "Intended for students with a strong record in science or engineering.", "Section: About")], "Confirm the required education level."),
  claim(ALDRIN, "location", "confirmed", "Cambridge-style campus, UK", "United Kingdom", "The institute page states the location.", [ev("aldrin-official", "United Kingdom", "Hosted on our campus in the United Kingdom.", "Section: About")]),
];
const aldrinReport = report(
  ALDRIN, aldrinClaims, aldrinSources,
  ["When is the application deadline?", "Are applications open yet?", "Where is the application link?"],
  [...STD_LIMITS, "The aggregator listing was not retrievable, so no corroboration is available."],
);

/* ───────────── 5. Lumen — rolling fellowship ───────────── */

const LUMEN = "demo-lumen-fellowship";
const lumenSources = [
  src("lumen-official", "Lumen Open Science — fellowship", "https://lumen-science.example/fellowship", "official"),
  src("lumen-board", "FellowshipFinder listing", "https://fellowshipfinder.example/lumen-open-science", "aggregator", { retrievedAt: "2026-10-22T09:41:00Z" }),
];
const lumenClaims: Claim[] = [
  claim(LUMEN, "deadline", "partially_confirmed", "Rolling — reviewed monthly", null, "Both sources describe rolling review, so no single date exists. The normalised date is intentionally empty.", [
    ev("lumen-official", "Rolling", "Applications are reviewed on a rolling monthly basis.", "Section: How to apply"),
    ev("lumen-board", "Rolling", "Deadline: rolling"),
  ]),
  claim(LUMEN, "application_status", "confirmed", "Rolling applications", "rolling", "Both sources agree.", [ev("lumen-official", "Rolling", "We accept applications year-round.", "Section: How to apply")]),
  claim(LUMEN, "application_url", "confirmed", "lumen-science.example/apply", "https://lumen-science.example/apply", "The link is on the official domain.", [ev("lumen-official", "https://lumen-science.example/apply", "Apply", "Primary call-to-action")]),
  claim(LUMEN, "eligibility", "confirmed", "Open to any early-career researcher", "Any level; early-career", "The official page lists this.", [ev("lumen-official", "Early-career researchers", "Open to early-career researchers worldwide.", "Section: Eligibility")]),
  claim(LUMEN, "stipend", "partially_confirmed", "Up to $2,000 per month", "Up to $2,000 / month", "Both sources say 'up to' without stating how the amount is decided.", [
    ev("lumen-official", "Up to $2,000 / month", "Fellows receive up to $2,000 per month.", "Section: Funding"),
    ev("lumen-board", "Up to $2,000 / month", "Funding: up to $2k/month"),
  ]),
  claim(LUMEN, "location", "confirmed", "Remote", "Remote", "Both sources state remote.", [ev("lumen-official", "Remote", "This is a fully remote fellowship.", "Section: Programme details")]),
];
const lumenReport = report(LUMEN, lumenClaims, lumenSources, ["How is the funding amount within 'up to $2,000' determined?"], STD_LIMITS);

/* ───────────── 6. Northstar — deadline conflict ───────────── */

const NORTH = "demo-northstar-challenge";
const northSources = [
  src("north-official", "Northstar Build Challenge — rules", "https://northstar-challenge.example/rules", "official"),
  src("north-board", "HackList event page", "https://hacklist.example/events/northstar-2026", "aggregator", { retrievedAt: "2026-10-22T09:50:00Z" }),
];
const northClaims: Claim[] = [
  claim(NORTH, "deadline", "conflicting", "Registration closes 8 November 2026", "2026-11-08 (official) vs 2026-11-15 (aggregator)", "The official rules and an aggregator give different dates. Both values remain visible.", [
    ev("north-official", "8 Nov 2026", "Registration closes on 8 November 2026.", "Section: Timeline"),
    ev("north-board", "15 Nov 2026", "Registration deadline: 15 Nov 2026"),
  ], "Rely on the official rules and re-check closer to the date."),
  claim(NORTH, "application_status", "confirmed", "Registration open", "open", "The official page states registration is open.", [ev("north-official", "Open", "Registration is open.", "Header")]),
  claim(NORTH, "application_url", "confirmed", "northstar-challenge.example/register", "https://northstar-challenge.example/register", "The link is on the official domain.", [ev("north-official", "https://northstar-challenge.example/register", "Register your team", "Primary call-to-action")]),
  claim(NORTH, "eligibility", "confirmed", "Open to students and early-career developers", "Students; early-career", "The official rules state this.", [ev("north-official", "Students; early-career", "Teams of 1–4 students or early-career developers.", "Section: Who can enter")]),
  claim(NORTH, "stipend", "unverified", "Prize pool", null, "Prize amounts are mentioned but not itemised on the retrieved pages.", [ev("north-official", null, "Prizes will be announced.", "Section: Prizes")]),
  claim(NORTH, "location", "confirmed", "Remote", "Remote", "The official rules state online participation.", [ev("north-official", "Remote", "Held fully online.", "Section: Format")]),
];
const northReport = report(NORTH, northClaims, northSources, ["Which deadline is correct — 8 Nov or 15 Nov 2026?", "What are the prizes?"], STD_LIMITS);

/* ───────────── Opportunities ───────────── */

const reports: Record<string, VerificationReport> = {
  [HELIO]: helioReport,
  [BRIGHT]: brightReport,
  [MERID]: meridReport,
  [ALDRIN]: aldrinReport,
  [LUMEN]: lumenReport,
  [NORTH]: northReport,
};

function headline(id: string) {
  const r = reports[id];
  return { reportStatus: deriveReportStatus(r.claims), counts: countClaims(r.claims), lastCheckedAt: r.generatedAt };
}

const base = { isSample: true } as const;

export const DEMO_OPPORTUNITIES: Opportunity[] = [
  {
    ...base, id: HELIO, title: "Software Engineering Internship 2027", organization: "Helio Systems", category: "internship",
    location: "Bengaluru, India", workMode: "on_site", deadline: "2026-12-15", applicationState: "open",
    description: "Work on production systems with an engineering team, build scalable services and learn from senior engineers over a 12-week summer programme.",
    tags: ["Computer Science", "Software Engineering", "Internship"], fieldsOfStudy: ["Computer Science", "Information Technology"],
    educationLevels: ["undergraduate"], eligibilitySummary: "BE/BTech in CS, IT or related fields; graduating 2027–2028.",
    eligibility: [
      { id: "h1", kind: "education_level", text: "Currently pursuing BE/BTech", values: ["undergraduate"] },
      { id: "h2", kind: "field_of_study", text: "Computer Science, IT or related fields", values: ["Computer Science", "Information Technology"] },
      { id: "h3", kind: "graduation_year", text: "Expected graduation 2027–2028", minYear: 2027, maxYear: 2028 },
      { id: "h4", kind: "other", text: "Authorised to work in India" },
    ],
    canonicalUrl: "https://careers.helio.example/students/swe-intern", applicationUrl: "https://careers.helio.example/students/apply",
    stipendText: "₹1,20,000 / month (see conflict)", durationText: "12 weeks", startDateText: "May 2027", postedAt: "2026-10-22T00:00:00Z",
    applicationSteps: [
      { id: "s1", group: "documents", label: "Prepare an up-to-date résumé (PDF)", sourceUrl: "https://careers.helio.example/students/swe-intern", sourceLabel: "Helio careers" },
      { id: "s2", group: "links", label: "Add GitHub or portfolio link", detail: "Optional but recommended.", sourceUrl: "https://careers.helio.example/students/swe-intern", sourceLabel: "Helio careers" },
      { id: "s3", group: "form", label: "Complete the online application form", sourceUrl: "https://careers.helio.example/students/apply", sourceLabel: "Application form" },
      { id: "s4", group: "submission", label: "Submit before 23:59 IST on the deadline day", sourceUrl: "https://careers.helio.example/students/swe-intern", sourceLabel: "Helio careers" },
    ],
    verification: headline(HELIO),
  },
  {
    ...base, id: BRIGHT, title: "Explore Internship Program 2027", organization: "Brightpath", category: "internship",
    location: "Hyderabad, India", workMode: "hybrid", deadline: "2026-11-30", applicationState: "open",
    description: "Explore career paths, work on impactful projects and get mentorship from experienced engineers and product teams.",
    tags: ["Computer Science", "Technology", "Internship"], fieldsOfStudy: ["Computer Science", "Technology"], educationLevels: ["undergraduate", "postgraduate"],
    eligibilitySummary: null,
    eligibility: [{ id: "b1", kind: "field_of_study", text: "Technology programmes (unverified)", values: ["Technology", "Computer Science"] }],
    canonicalUrl: "https://explore.brightpath.example/internship", applicationUrl: "https://explore.brightpath.example/apply",
    stipendText: null, durationText: "10–12 weeks", postedAt: "2026-10-20T00:00:00Z",
    applicationSteps: [{ id: "s1", group: "form", label: "Complete the online application", sourceUrl: "https://explore.brightpath.example/apply", sourceLabel: "Application form" }],
    verification: headline(BRIGHT),
  },
  {
    ...base, id: MERID, title: "Undergraduate Scholarship 2027", organization: "Meridian Foundation", category: "scholarship",
    location: "Pan India", workMode: "unknown", deadline: "2027-01-31", applicationState: "open",
    description: "Financial support for meritorious undergraduate students from families with limited income, renewable annually.",
    tags: ["Higher Education", "Scholarship", "All Fields"], fieldsOfStudy: ["Any"], educationLevels: ["undergraduate"],
    eligibilitySummary: "Undergraduate students; annual family income below ₹8,00,000.",
    eligibility: [
      { id: "m1", kind: "education_level", text: "Enrolled in an undergraduate programme", values: ["undergraduate"] },
      { id: "m2", kind: "other", text: "Annual family income below ₹8,00,000" },
    ],
    canonicalUrl: "https://meridianfoundation.example/scholarships/undergraduate", applicationUrl: "https://meridianfoundation.example/apply",
    stipendText: "₹60,000 / year", postedAt: "2026-10-01T00:00:00Z",
    applicationSteps: [
      { id: "s1", group: "documents", label: "Income certificate", detail: "Issued within the last 12 months.", sourceUrl: "https://meridianfoundation.example/scholarships/undergraduate", sourceLabel: "Meridian Foundation" },
      { id: "s2", group: "documents", label: "Latest academic transcript", sourceUrl: "https://meridianfoundation.example/scholarships/undergraduate", sourceLabel: "Meridian Foundation" },
      { id: "s3", group: "form", label: "Submit the online scholarship form", sourceUrl: "https://meridianfoundation.example/apply", sourceLabel: "Application form" },
    ],
    verification: headline(MERID),
  },
  {
    ...base, id: ALDRIN, title: "Summer Research Programme 2027", organization: "Aldrin Institute", category: "research",
    location: "United Kingdom", workMode: "on_site", deadline: null, deadlineText: null, applicationState: "unknown",
    description: "Join researchers and work on cutting-edge projects in science and technology over the summer.",
    tags: ["STEM", "Research", "Summer Programme"], fieldsOfStudy: ["Science", "Engineering"], educationLevels: ["unknown"],
    eligibilitySummary: "Strong academic record in science or engineering; education level not stated.",
    eligibility: [{ id: "a1", kind: "field_of_study", text: "Science or engineering", values: ["Science", "Engineering", "Computer Science"] }, { id: "a2", kind: "education_level", text: "Education level not stated" }],
    canonicalUrl: "https://aldrin-institute.example/summer", applicationUrl: null, postedAt: null,
    verification: headline(ALDRIN),
  },
  {
    ...base, id: LUMEN, title: "Open Science Fellowship", organization: "Lumen Open Science", category: "fellowship",
    location: "Remote (worldwide)", workMode: "remote", deadline: null, deadlineText: "Rolling — reviewed monthly", applicationState: "rolling",
    description: "A remote fellowship for early-career researchers building open, reproducible science.",
    tags: ["Research", "Open Science", "Remote"], fieldsOfStudy: ["Any"], educationLevels: ["any"],
    eligibilitySummary: "Early-career researchers worldwide.",
    eligibility: [{ id: "l1", kind: "other", text: "Early-career researcher" }],
    canonicalUrl: "https://lumen-science.example/fellowship", applicationUrl: "https://lumen-science.example/apply", stipendText: "Up to $2,000 / month",
    postedAt: "2026-09-12T00:00:00Z",
    applicationSteps: [
      { id: "s1", group: "documents", label: "One-page research statement", sourceUrl: "https://lumen-science.example/fellowship", sourceLabel: "Lumen fellowship page" },
      { id: "s2", group: "form", label: "Apply through the online form", sourceUrl: "https://lumen-science.example/apply", sourceLabel: "Application form" },
    ],
    verification: headline(LUMEN),
  },
  {
    ...base, id: NORTH, title: "Build Challenge 2026", organization: "Northstar", category: "competition",
    location: "Online", workMode: "remote", deadline: "2026-11-08", applicationState: "open",
    description: "A four-week online build challenge for students and early-career developers, in teams of up to four.",
    tags: ["Software", "Competition", "Teams"], fieldsOfStudy: ["Computer Science", "Engineering"], educationLevels: ["undergraduate", "postgraduate"],
    eligibilitySummary: "Students or early-career developers; teams of 1–4.",
    eligibility: [{ id: "n1", kind: "other", text: "Student or early-career developer" }],
    canonicalUrl: "https://northstar-challenge.example/rules", applicationUrl: "https://northstar-challenge.example/register", postedAt: "2026-10-05T00:00:00Z",
    applicationSteps: [
      { id: "s1", group: "form", label: "Register your team", detail: "Teams of 1–4.", sourceUrl: "https://northstar-challenge.example/register", sourceLabel: "Registration" },
      { id: "s2", group: "submission", label: "Confirm the registration deadline in the official rules", sourceUrl: "https://northstar-challenge.example/rules", sourceLabel: "Official rules" },
    ],
    verification: headline(NORTH),
  },
];

export const DEMO_REPORTS = reports;

/* ───────────── History ───────────── */

function snapshotFrom(id: string, runId: string, capturedAt: string, claims: Claim[], overrides: Partial<Snapshot> = {}): Snapshot {
  return {
    id: `${id}:${runId}`,
    opportunityId: id,
    runId,
    capturedAt,
    runState: "completed",
    reportStatus: deriveReportStatus(claims),
    claims: claims.map((c) => ({ type: c.type, normalizedValue: c.normalizedValue, status: c.status })),
    unavailableSources: [],
    ...overrides,
  };
}

function helioHistory(): Snapshot[] {
  const latest = snapshotFrom(HELIO, "run-3", T_LATEST, helioClaims, {
    runState: "partial",
    unavailableSources: [{ url: "https://careers.helio.example/files/swe-intern-brochure.pdf", reason: "Request timed out" }],
  });
  const mid = snapshotFrom(HELIO, "run-2", T_MID, helioClaims.map((c) => {
    if (c.type === "deadline") return { ...c, normalizedValue: "2026-12-01", status: "confirmed" as const };
    if (c.type === "stipend") return { ...c, normalizedValue: "₹1,20,000 / month", status: "confirmed" as const };
    return c;
  }));
  const old = snapshotFrom(HELIO, "run-1", T_OLD, helioClaims.filter((c) => c.type !== "stipend" && c.type !== "duration").map((c) => (c.type === "deadline" ? { ...c, normalizedValue: "2026-12-01" } : c)), { runState: "completed" });
  return [latest, mid, old];
}

function northHistory(): Snapshot[] {
  const latest = snapshotFrom(NORTH, "run-2", T_LATEST, northClaims);
  const prev = snapshotFrom(NORTH, "run-1", T_MID, northClaims.map((c) => (c.type === "deadline" ? { ...c, normalizedValue: "2026-11-08", status: "confirmed" as const } : c)));
  return [latest, prev];
}

function aldrinHistory(): Snapshot[] {
  const latest = snapshotFrom(ALDRIN, "run-2", T_LATEST, aldrinClaims, { runState: "partial", unavailableSources: [{ url: "https://researchhub.example/p/aldrin-summer", reason: "Not found (404)" }] });
  const prev = snapshotFrom(ALDRIN, "run-1", T_MID, aldrinClaims.slice(0, 3), { runState: "failed", unavailableSources: [{ url: "https://aldrin-institute.example/summer", reason: "Request timed out" }] });
  return [latest, prev];
}

function stableHistory(id: string, claims: Claim[]): Snapshot[] {
  return [snapshotFrom(id, "run-2", T_LATEST, claims), snapshotFrom(id, "run-1", T_MID, claims)];
}

export const DEMO_HISTORY: Record<string, Snapshot[]> = {
  [HELIO]: helioHistory(),
  [NORTH]: northHistory(),
  [ALDRIN]: aldrinHistory(),
  [BRIGHT]: stableHistory(BRIGHT, brightClaims),
  [MERID]: stableHistory(MERID, meridClaims),
  [LUMEN]: stableHistory(LUMEN, lumenClaims),
};

/* ───────────── Run log (sample) ───────────── */

export const DEMO_RUN: Run = {
  id: "sample-run-helio-3",
  state: "partial",
  isSample: true,
  warnings: ["One official source timed out; the report was built from the sources that responded."],
  events: [
    { id: "e1", step: "request_received", state: "completed", at: "2026-10-22T09:13:50Z", message: "Recheck requested." },
    { id: "e2", step: "discovering", state: "completed", at: "2026-10-22T09:13:52Z", message: "Found 4 candidate source pages." },
    { id: "e3", step: "retrieving_sources", state: "failed", at: "2026-10-22T09:15:58Z", message: "3 of 4 pages retrieved; 1 timed out." },
    { id: "e4", step: "extracting_claims", state: "completed", at: "2026-10-22T09:16:20Z", message: "Extracted 7 candidate claims." },
    { id: "e5", step: "comparing_claims", state: "completed", at: "2026-10-22T09:16:41Z" },
    { id: "e6", step: "detecting_conflicts", state: "completed", at: "2026-10-22T09:16:43Z", message: "1 conflict detected (stipend)." },
    { id: "e7", step: "building_report", state: "completed", at: "2026-10-22T09:16:48Z" },
    { id: "e8", step: "finished", state: "completed", at: "2026-10-22T09:16:49Z", message: "Completed with partial source coverage." },
  ],
};

/* ───────────── Notifications (sample) ───────────── */

export const DEMO_NOTIFICATIONS: AppNotification[] = [
  { id: "n1", kind: "conflict_detected", title: "New conflict: stipend", body: "Sources disagree on the monthly stipend for Software Engineering Internship 2027.", opportunityId: HELIO, createdAt: T_LATEST, read: false, isSample: true },
  { id: "n2", kind: "deadline_changed", title: "Deadline changed", body: "The listed deadline moved from 1 Dec 2026 to 15 Dec 2026.", opportunityId: HELIO, createdAt: "2026-10-22T09:16:00Z", read: false, isSample: true },
  { id: "n3", kind: "verification_failed", title: "Recheck incomplete", body: "Summer Research Programme 2027: one source was not found, so comparison is incomplete.", opportunityId: ALDRIN, createdAt: "2026-10-22T09:32:00Z", read: false, isSample: true },
  { id: "n4", kind: "recheck_result", title: "Recheck finished — no detected changes", body: "Undergraduate Scholarship 2027: no changes between the last two runs.", opportunityId: MERID, createdAt: "2026-10-21T17:00:00Z", read: true, isSample: true },
  { id: "n5", kind: "saved_update", title: "Saved opportunity updated", body: "Build Challenge 2026: the deadline now conflicts between sources.", opportunityId: NORTH, createdAt: "2026-10-20T08:20:00Z", read: true, isSample: true },
];

/* ───────────── Profile (sample) ───────────── */

export const DEMO_PROFILE: ApplicantProfile = {
  educationLevel: "undergraduate",
  degree: "BTech",
  fieldOfStudy: "Computer Science",
  institution: "Sample Institute of Technology",
  graduationYear: 2027,
  location: "Bengaluru, India",
  preferredRegions: ["India", "Remote"],
  experience: "Two small web projects and one hackathon.",
  skills: ["Python", "Java", "SQL", "Machine Learning"],
  researchInterests: ["Software engineering", "AI", "Cloud"],
  preferredCategories: ["internship", "scholarship", "research"],
  workModePreference: "any",
};

export const DEMO_SAVED_IDS = [BRIGHT, MERID, NORTH];
