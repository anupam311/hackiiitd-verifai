import Link from "next/link";
import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, ComponentProps, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "md" | "sm";

const cls = (variant: Variant, size: Size, extra?: string) => ["btn", `btn-${variant}`, size === "sm" ? "btn-sm" : "", extra ?? ""].filter(Boolean).join(" ");

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
}

export function Button({ variant = "secondary", size = "md", loading, icon, children, className, disabled, type = "button", ...rest }: ButtonProps) {
  return (
    <button type={type} className={cls(variant, size, className)} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading ? <Loader2 size={15} className="spin" aria-hidden /> : icon}
      {children}
    </button>
  );
}

interface LinkButtonProps extends ComponentProps<typeof Link> {
  variant?: Variant;
  size?: Size;
  icon?: ReactNode;
}

export function LinkButton({ variant = "secondary", size = "md", icon, children, className, ...rest }: LinkButtonProps) {
  return (
    <Link className={cls(variant, size, className)} {...rest}>
      {icon}
      {children}
    </Link>
  );
}

/** Link to an external page; always opens in a new tab with safe rel. */
export function ExternalLink({ href, children, className }: { href: string; children: ReactNode; className?: string }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={className ?? "link"}>
      {children}
    </a>
  );
}
