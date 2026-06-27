"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, FileText, Flag, Users } from "lucide-react";

const ITEMS = [
  { href: "/admin/news", label: "News", icon: FileText },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/reports", label: "Reports", icon: Flag },
  { href: "/admin/visits", label: "Visits", icon: Activity },
];

export function AdminNav() {
  const pathname = usePathname();
  return (
    <nav className="flex gap-2 pb-3">
      {ITEMS.map((item) => {
        const active = pathname?.startsWith(item.href);
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`inline-flex items-center gap-1.5 rounded-btn px-3 py-1.5 text-sm font-semibold transition-colors ${
              active
                ? "bg-accent-yellow/15 text-accent-yellow"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
