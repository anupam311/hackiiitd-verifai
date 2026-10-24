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
      .get<Partial<ApplicantProfile>>("/api/v1/profile", undefined, ctrl.signal)
      .then((remote) => {
        if (remote && typeof remote === "object") setProfile((p) => ({ ...p, ...remote }));
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
        await api.patch("/api/v1/profile", next);
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
