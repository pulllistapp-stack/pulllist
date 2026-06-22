"use client";

import { useRouter } from "next/navigation";
import { ReactNode, useEffect } from "react";

import { AdminNav } from "@/components/admin/AdminNav";
import { useAuth } from "@/components/AuthProvider";
import { MascotLoader } from "@/components/MascotLoader";

/**
 * Wrap an admin page in this to gate access. Redirects non-admins to
 * the home page; shows the mascot loader while auth resolves so the
 * component tree doesn't flash the underlying form to a non-admin.
 *
 * Also renders the shared admin nav strip (News / Users / etc.) above
 * each gated page so admins can jump between surfaces without going
 * back to the home menu.
 */
export function AdminGuard({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user || !user.is_admin) router.replace("/");
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-16">
        <MascotLoader size="lg" />
      </main>
    );
  }
  if (!user.is_admin) return null;
  return (
    <>
      <div className="border-b border-border bg-bg-surface/40">
        <div className="mx-auto max-w-6xl px-4 pt-4">
          <AdminNav />
        </div>
      </div>
      {children}
    </>
  );
}
