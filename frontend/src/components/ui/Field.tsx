import { useId, type ReactNode, type SelectHTMLAttributes } from "react";

export function Field({ label, hint, error, children, htmlFor }: { label: string; hint?: string; error?: string | null; children: (ids: { id: string; describedBy?: string; invalid: boolean }) => ReactNode; htmlFor?: string }) {
  const gen = useId();
  const id = htmlFor ?? gen;
  const hintId = `${id}-hint`;
  const errId = `${id}-err`;
  const describedBy = [hint ? hintId : "", error ? errId : ""].filter(Boolean).join(" ") || undefined;
  return (
    <div className={`field ${error ? "field-invalid" : ""}`}>
      <label htmlFor={id}>{label}</label>
      {children({ id, describedBy, invalid: !!error })}
      {hint && !error && (
        <p className="hint" id={hintId}>
          {hint}
        </p>
      )}
      {error && (
        <p className="field-error" id={errId} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "onChange"> {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  hideLabel?: boolean;
}

export function Select({ label, value, onChange, options, hideLabel = true, ...rest }: SelectProps) {
  const id = useId();
  return (
    <div className="select-wrap">
      <label htmlFor={id} className={hideLabel ? "sr-only" : "select-label"}>
        {label}
      </label>
      <select id={id} className="select" value={value} onChange={(e) => onChange(e.target.value)} {...rest}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
