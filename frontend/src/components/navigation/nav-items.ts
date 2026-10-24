import { Bell, Bookmark, History, ListChecks, RefreshCw, Scale, Search, UserRound, type LucideIcon } from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Extra path prefixes that should light this item up. */
  also?: string[];
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/explore", label: "Discover", icon: Search, also: ["/opportunities", "/reports", "/passport"] },
  { href: "/saved", label: "Saved Opportunities", icon: Bookmark },
  { href: "/recheck", label: "Recheck", icon: RefreshCw },
  { href: "/history", label: "History", icon: History },
  { href: "/compare", label: "Compare Sources", icon: Scale },
  { href: "/profile", label: "Applicant Profile", icon: UserRound },
  { href: "/checklist", label: "Application Checklists", icon: ListChecks },
  { href: "/notifications", label: "Notifications", icon: Bell },
];

export function isActive(pathname: string, item: NavItem): boolean {
  return [item.href, ...(item.also ?? [])].some((p) => pathname === p || pathname.startsWith(`${p}/`));
}
