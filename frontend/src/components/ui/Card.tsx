import type { HTMLAttributes, ReactNode } from "react";

export function Card({ children, className = "", pad = true, ...rest }: HTMLAttributes<HTMLElement> & { pad?: boolean }) {
  return (
    <section className={`card ${pad ? "card-pad" : ""} ${className}`} {...rest}>
      {children}
    </section>
  );
}

export function CardHeader({ title, icon, action, as: Tag = "h2", id }: { title: ReactNode; icon?: ReactNode; action?: ReactNode; as?: "h2" | "h3"; id?: string }) {
  return (
    <div className="card-head">
      <Tag className="card-title" id={id}>
        {icon}
        {title}
      </Tag>
      {action}
    </div>
  );
}
