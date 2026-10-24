"use client";

import { useEffect, useState } from "react";
import type { ApplicantProfile, EducationLevel, OpportunityCategory, WorkMode } from "@/types";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { splitList, validateProfile, type ProfileErrors } from "@/features/profile/validate";
import { CATEGORY_LABEL, EDUCATION_LABEL } from "@/lib/formatters";

type Draft = Omit<ApplicantProfile, "graduationYear" | "preferredRegions" | "skills" | "researchInterests"> & {
  graduationYear: string;
  preferredRegions: string;
  skills: string;
  researchInterests: string;
};

const toDraft = (p: ApplicantProfile): Draft => ({
  ...p,
  graduationYear: p.graduationYear?.toString() ?? "",
  preferredRegions: p.preferredRegions.join(", "),
  skills: p.skills.join(", "),
  researchInterests: p.researchInterests.join(", "),
});

const fromDraft = (d: Draft): ApplicantProfile => ({
  ...d,
  graduationYear: d.graduationYear.trim() === "" ? null : Number(d.graduationYear),
  preferredRegions: splitList(d.preferredRegions),
  skills: splitList(d.skills),
  researchInterests: splitList(d.researchInterests),
});

export function ProfileForm({ profile, onSave, onClear }: { profile: ApplicantProfile; onSave: (p: ApplicantProfile) => Promise<void>; onClear: () => void }) {
  const [draft, setDraft] = useState<Draft>(toDraft(profile));
  const [errors, setErrors] = useState<ProfileErrors>({});
  const [saving, setSaving] = useState(false);
  useEffect(() => setDraft(toDraft(profile)), [profile]);

  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft((d) => ({ ...d, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const next = fromDraft(draft);
    const errs = validateProfile(next);
    if (draft.graduationYear.trim() !== "" && Number.isNaN(Number(draft.graduationYear))) errs.graduationYear = "Enter a four-digit year.";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setSaving(true);
    await onSave(next);
    setSaving(false);
  };

  const toggleCat = (c: OpportunityCategory) =>
    set("preferredCategories", draft.preferredCategories.includes(c) ? draft.preferredCategories.filter((x) => x !== c) : [...draft.preferredCategories, c]);

  return (
    <form onSubmit={submit} noValidate className="profile-form">
      <fieldset>
        <legend>Education</legend>
        <div className="form-grid">
          <Field label="Education level">
            {({ id }) => (
              <select id={id} className="select" value={draft.educationLevel} onChange={(e) => set("educationLevel", e.target.value as EducationLevel)}>
                {(["unknown", "high_school", "undergraduate", "postgraduate", "doctoral"] as const).map((v) => (
                  <option key={v} value={v}>{v === "unknown" ? "Select…" : EDUCATION_LABEL[v]}</option>
                ))}
              </select>
            )}
          </Field>
          <Field label="Degree" error={errors.degree}>
            {({ id, describedBy, invalid }) => <input id={id} className="input" value={draft.degree} onChange={(e) => set("degree", e.target.value)} placeholder="e.g. BTech" aria-describedby={describedBy} aria-invalid={invalid} />}
          </Field>
          <Field label="Field of study" error={errors.fieldOfStudy}>
            {({ id, describedBy, invalid }) => <input id={id} className="input" value={draft.fieldOfStudy} onChange={(e) => set("fieldOfStudy", e.target.value)} placeholder="e.g. Computer Science" aria-describedby={describedBy} aria-invalid={invalid} />}
          </Field>
          <Field label="Institution" error={errors.institution}>
            {({ id, describedBy, invalid }) => <input id={id} className="input" value={draft.institution} onChange={(e) => set("institution", e.target.value)} aria-describedby={describedBy} aria-invalid={invalid} />}
          </Field>
          <Field label="Expected graduation year" error={errors.graduationYear}>
            {({ id, describedBy, invalid }) => <input id={id} className="input" inputMode="numeric" value={draft.graduationYear} onChange={(e) => set("graduationYear", e.target.value)} placeholder="e.g. 2027" aria-describedby={describedBy} aria-invalid={invalid} />}
          </Field>
        </div>
      </fieldset>

      <fieldset>
        <legend>Location & preferences</legend>
        <div className="form-grid">
          <Field label="Where you are based" hint="City and country is enough — no street address is needed." error={errors.location}>
            {({ id, describedBy, invalid }) => <input id={id} className="input" value={draft.location} onChange={(e) => set("location", e.target.value)} placeholder="e.g. Bengaluru, India" aria-describedby={describedBy} aria-invalid={invalid} />}
          </Field>
          <Field label="Preferred regions" hint="Comma-separated." error={errors.preferredRegions}>
            {({ id, describedBy, invalid }) => <input id={id} className="input" value={draft.preferredRegions} onChange={(e) => set("preferredRegions", e.target.value)} placeholder="India, Remote" aria-describedby={describedBy} aria-invalid={invalid} />}
          </Field>
          <Field label="Remote / on-site preference">
            {({ id }) => (
              <select id={id} className="select" value={draft.workModePreference} onChange={(e) => set("workModePreference", e.target.value as WorkMode | "any")}>
                <option value="any">No preference</option><option value="remote">Remote</option><option value="on_site">On-site</option><option value="hybrid">Hybrid</option>
              </select>
            )}
          </Field>
        </div>
        <div className="field">
          <span className="label" id="cats-label">Preferred opportunity categories</span>
          <div className="chip-group" role="group" aria-labelledby="cats-label">
            {(Object.keys(CATEGORY_LABEL) as OpportunityCategory[]).map((c) => (
              <label key={c} className={`chip ${draft.preferredCategories.includes(c) ? "chip-on" : ""}`}>
                <input type="checkbox" checked={draft.preferredCategories.includes(c)} onChange={() => toggleCat(c)} />
                {CATEGORY_LABEL[c]}
              </label>
            ))}
          </div>
        </div>
      </fieldset>

      <fieldset>
        <legend>Experience & interests</legend>
        <div className="form-grid">
          <Field label="Skills" hint="Comma-separated." error={errors.skills}>
            {({ id, describedBy, invalid }) => <input id={id} className="input" value={draft.skills} onChange={(e) => set("skills", e.target.value)} placeholder="Python, SQL, Figma" aria-describedby={describedBy} aria-invalid={invalid} />}
          </Field>
          <Field label="Research interests" hint="Comma-separated." error={errors.researchInterests}>
            {({ id, describedBy, invalid }) => <input id={id} className="input" value={draft.researchInterests} onChange={(e) => set("researchInterests", e.target.value)} aria-describedby={describedBy} aria-invalid={invalid} />}
          </Field>
        </div>
        <Field label="Experience" hint="A short summary. Avoid personal identifiers." error={errors.experience}>
          {({ id, describedBy, invalid }) => <textarea id={id} className="textarea" rows={3} value={draft.experience} onChange={(e) => set("experience", e.target.value)} aria-describedby={describedBy} aria-invalid={invalid} />}
        </Field>
      </fieldset>

      <div className="form-actions">
        <Button type="submit" variant="primary" loading={saving}>Save profile</Button>
        <Button variant="ghost" onClick={() => { onClear(); setErrors({}); }}>Clear profile</Button>
      </div>
    </form>
  );
}
