"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ApplicantProfile } from "@/types";
import { api } from "@/lib/api-client";
import { DEMO_PROFILE } from "@/lib/dev-fixtures/demo-data";
import { EMPTY_PROFILE } from "@/features/matching/match";
import { useDemo } from "@/providers/DemoProvider";

interface ProfileCtx {
  profile: ApplicantProfile;
  /** True once a profile with real content exists. */
  hasProfile: boolean;
  save: (p: ApplicantProfile) => Promise<{ synced: boolean }>;
  clear: () => void;
}
const Ctx = createContext<ProfileCtx | null>(null);

/** Shape of `GET/PATCH /api/v1/profile` (backend/app/schemas/profile.py). */
interface RemoteProfile {
  education?: string | null;
  location?: string | null;
  experience_years?: number | null;
  interests?: string[] | null;
}

/** Fill only the fields the browser does not already have; the local profile is the richer source. */
function mergeRemote(p: ApplicantProfile, r: RemoteProfile): ApplicantProfile {
  const interests = Array.isArray(r.interests) ? r.interests.filter((x): x is string => typeof x === "string") : [];
  return {
    ...p,
    degree: p.degree || (typeof r.education === "string" ? r.education : ""),
    location: p.location || (typeof r.location === "string" ? r.location : ""),
    experience: p.experience || (typeof r.experience_years === "number" ? `${r.experience_years} years` : ""),
    researchInterests: p.researchInterests.length > 0 ? p.researchInterests : interests,
  };
}

/** Only the four fields the backend stores are sent (data minimisation). */
function toRemote(p: ApplicantProfile): RemoteProfile {
  const years = /\d+/.exec(p.experience);
  const interests = [...new Set([...p.researchInterests, ...p.skills].map((x) => x.trim()).filter(Boolean))].slice(0, 10);
  return {
    education: [p.degree, p.institution].map((x) => x.trim()).filter(Boolean).join(", ").slice(0, 200) || null,
    location: p.location.trim().slice(0, 200) || null,
    experience_years: years ? Math.min(50, Number(years[0])) : null,
    interests,
  };
}

const KEY_LIVE = "verifai.profile";
const KEY_SAMPLE = "verifai.profile.sample";

function read(key: string): ApplicantProfile | null {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? { ...EMPTY_PROFILE, ...(JSON.parse(raw) as Partial<ApplicantProfile>) } : null;
  } catch {
    return null;
  }
}

export function ProfileProvider({ children }: { children: React.ReactNode }) {
  const { demo, ready } = useDemo();
  const [profile, setProfile] = useState<ApplicantProfile>(EMPTY_PROFILE);

  useEffect(() => {
    if (!ready) return;
    if (demo) {
      setProfile(read(KEY_SAMPLE) ?? DEMO_PROFILE);
      return;
    }
    setProfile(read(KEY_LIVE) ?? EMPTY_PROFILE);
    const ctrl = new AbortController();
    api
      .get<RemoteProfile>("/api/v1/profile", undefined, ctrl.signal)
      .then((remote) => {
        if (remote && typeof remote === "object") setProfile((p) => mergeRemote(p, remote));
      })
      .catch(() => {
        /* backend profile is optional; a local profile is used */
      });
    return () => ctrl.abort();
  }, [demo, ready]);

  const save = useCallback(
    async (next: ApplicantProfile) => {
      setProfile(next);
      try {
        window.localStorage.setItem(demo ? KEY_SAMPLE : KEY_LIVE, JSON.stringify(next));
      } catch {
        /* ignore */
      }
      if (demo) return { synced: false };
      try {
        await api.patch("/api/v1/profile", toRemote(next));
        return { synced: true };
      } catch {
        return { synced: false };
      }
    },
    [demo],
  );

  const clear = useCallback(() => {
    setProfile(EMPTY_PROFILE);
    try {
      window.localStorage.removeItem(demo ? KEY_SAMPLE : KEY_LIVE);
    } catch {
      /* ignore */
    }
  }, [demo]);

  const hasProfile = profile.educationLevel !== "unknown" || profile.fieldOfStudy !== "" || profile.location !== "" || profile.graduationYear !== null;
  const value = useMemo(() => ({ profile, hasProfile, save, clear }), [profile, hasProfile, save, clear]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useProfile(): ProfileCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useProfile must be used within ProfileProvider");
  return v;
}
