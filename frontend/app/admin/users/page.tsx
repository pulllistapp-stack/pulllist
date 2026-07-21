"use client";

import { useCallback, useEffect, useState } from "react";
import { Search, Shield, Trash2, Undo2 } from "lucide-react";

import { AdminGuard } from "@/components/admin/AdminGuard";
import { useAuth } from "@/components/AuthProvider";
import { getToken } from "@/lib/auth";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

type AdminUser = {
  id: string;
  email: string;
  name: string | null;
  avatar_url: string | null;
  is_admin: boolean;
  deleted_at: string | null;
  created_at: string;
  card_count: number;
  wishlist_count: number;
};

type ListResponse = {
  total: number;
  page: number;
  page_size: number;
  items: AdminUser[];
};

export default function AdminUsersPage() {
  return (
    <AdminGuard>
      <AdminUsersContent />
    </AdminGuard>
  );
}

function AdminUsersContent() {
  const { user: me } = useAuth();
  const [q, setQ] = useState("");
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 50;
  const [data, setData] = useState<ListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const token = getToken();
      const url = new URL(`${API_BASE}/admin/users`);
      if (q) url.searchParams.set("q", q);
      if (includeDeleted) url.searchParams.set("include_deleted", "true");
      url.searchParams.set("page", String(page));
      url.searchParams.set("page_size", String(PAGE_SIZE));
      const r = await fetch(url.toString(), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData((await r.json()) as ListResponse);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [q, includeDeleted, page]);

  useEffect(() => {
    void load();
  }, [load]);

  async function toggleAdmin(target: AdminUser) {
    const next = !target.is_admin;
    if (target.id === me?.id && !next) {
      alert("You can't remove your own admin role.");
      return;
    }
    if (!confirm(`${next ? "Promote" : "Demote"} ${target.email}?`)) return;
    const token = getToken();
    const r = await fetch(`${API_BASE}/admin/users/${target.id}/admin`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ is_admin: next }),
    });
    if (!r.ok) {
      const body = await r.json().catch(() => null);
      alert(body?.detail ?? `Failed: ${r.status}`);
      return;
    }
    void load();
  }

  async function softDelete(target: AdminUser) {
    if (target.id === me?.id) {
      alert("You can't delete your own account.");
      return;
    }
    if (!confirm(`Soft-delete ${target.email}?\nThey can be restored later.`)) return;
    const token = getToken();
    const r = await fetch(`${API_BASE}/admin/users/${target.id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!r.ok && r.status !== 204) {
      const body = await r.json().catch(() => null);
      alert(body?.detail ?? `Failed: ${r.status}`);
      return;
    }
    void load();
  }

  async function restore(target: AdminUser) {
    const token = getToken();
    const r = await fetch(`${API_BASE}/admin/users/${target.id}/restore`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!r.ok) {
      const body = await r.json().catch(() => null);
      alert(body?.detail ?? `Failed: ${r.status}`);
      return;
    }
    void load();
  }

  const items = data?.items ?? [];
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      <header className="mb-6">
        <p className="font-mono text-xs uppercase tracking-widest text-text-tertiary">
          Admin
        </p>
        <h1 className="mt-1 text-3xl font-extrabold tracking-tight text-text-primary">
          Users
        </h1>
        <p className="mt-1 text-sm text-text-secondary">
          {data ? `${data.total.toLocaleString()} total` : "Loading..."}
        </p>
      </header>

      {/* Search + filter */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-tertiary" />
          <input
            type="search"
            value={q}
            onChange={(e) => {
              setPage(1);
              setQ(e.target.value);
            }}
            placeholder="Search email / name"
            className="w-full rounded-btn border border-border bg-bg-surface pl-9 pr-3 py-2 text-sm text-text-primary focus:border-accent-yellow focus:outline-none"
          />
        </div>
        <label className="inline-flex items-center gap-2 text-sm text-text-secondary">
          <input
            type="checkbox"
            checked={includeDeleted}
            onChange={(e) => {
              setPage(1);
              setIncludeDeleted(e.target.checked);
            }}
          />
          Include deleted
        </label>
      </div>

      {err && (
        <div className="mb-4 rounded-card bg-accent-red/10 border border-accent-red/30 p-3 text-sm text-accent-red">
          {err}
        </div>
      )}

      {loading ? (
        <p className="py-12 text-center text-sm text-text-tertiary">Loading...</p>
      ) : items.length === 0 ? (
        <p className="py-12 text-center text-sm text-text-tertiary">
          No users match.
        </p>
      ) : (
        <>
        {/* Mobile: stacked card per user. Everything visible without
            needing a horizontal scroll. */}
        <ul className="sm:hidden space-y-2">
          {items.map((u) => (
            <li
              key={u.id}
              className={`rounded-card border border-border bg-bg-surface p-3 ${
                u.deleted_at ? "opacity-60" : ""
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-text-primary truncate">
                    {u.name ?? "—"}
                  </p>
                  <p className="font-mono text-xs text-text-tertiary truncate">
                    {u.email}
                  </p>
                </div>
                {u.is_admin ? (
                  <span className="shrink-0 inline-flex items-center gap-1 rounded-full bg-accent-yellow/15 px-2 py-0.5 text-[10px] font-bold text-accent-yellow">
                    <Shield className="h-3 w-3" />
                    ADMIN
                  </span>
                ) : (
                  <span className="shrink-0 text-[10px] text-text-tertiary">
                    member
                  </span>
                )}
              </div>
              <div className="mt-2 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-text-secondary">
                <span>
                  Joined{" "}
                  <span className="font-mono text-text-primary">
                    {formatDate(u.created_at)}
                  </span>
                </span>
                <span>
                  Cards{" "}
                  <span className="font-mono font-bold text-text-primary">
                    {u.card_count}
                  </span>
                </span>
                <span>
                  Wishlist{" "}
                  <span className="font-mono font-bold text-text-primary">
                    {u.wishlist_count}
                  </span>
                </span>
              </div>
              {u.deleted_at && (
                <p className="mt-1 text-[11px] text-accent-red">
                  deleted {formatDate(u.deleted_at)}
                </p>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  onClick={() => toggleAdmin(u)}
                  disabled={u.id === me?.id && u.is_admin}
                  className="rounded-btn border border-border bg-bg px-3 py-1.5 text-xs font-semibold text-text-secondary hover:text-text-primary disabled:opacity-40"
                >
                  {u.is_admin ? "Demote" : "Promote"}
                </button>
                {u.deleted_at ? (
                  <button
                    onClick={() => restore(u)}
                    className="inline-flex items-center gap-1 rounded-btn border border-accent-green/40 bg-accent-green/10 px-3 py-1.5 text-xs font-semibold text-accent-green hover:bg-accent-green/20"
                  >
                    <Undo2 className="h-3 w-3" />
                    Restore
                  </button>
                ) : (
                  <button
                    onClick={() => softDelete(u)}
                    disabled={u.id === me?.id}
                    className="inline-flex items-center gap-1 rounded-btn border border-accent-red/40 bg-accent-red/10 px-3 py-1.5 text-xs font-semibold text-accent-red hover:bg-accent-red/20 disabled:opacity-40"
                  >
                    <Trash2 className="h-3 w-3" />
                    Delete
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>

        {/* Desktop: original table with horizontal-scroll fallback. */}
        <div className="hidden sm:block overflow-x-auto rounded-card border border-border bg-bg-surface">
          <table className="w-full text-sm">
            <thead className="text-xs font-mono uppercase tracking-wider text-text-tertiary">
              <tr>
                <th className="px-3 py-2 text-left">User</th>
                <th className="px-3 py-2 text-left">Joined</th>
                <th className="px-3 py-2 text-right">Cards</th>
                <th className="px-3 py-2 text-right">Wishlist</th>
                <th className="px-3 py-2 text-center">Role</th>
                <th className="px-3 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((u) => (
                <tr
                  key={u.id}
                  className={`border-t border-border ${
                    u.deleted_at ? "opacity-50" : ""
                  }`}
                >
                  <td className="px-3 py-2">
                    <div className="flex flex-col">
                      <span className="font-semibold text-text-primary">
                        {u.name ?? "—"}
                      </span>
                      <span className="font-mono text-xs text-text-tertiary">
                        {u.email}
                      </span>
                      {u.deleted_at && (
                        <span className="mt-0.5 text-xs text-accent-red">
                          deleted {formatDate(u.deleted_at)}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-text-tertiary">
                    {formatDate(u.created_at)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-text-secondary">
                    {u.card_count}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-text-secondary">
                    {u.wishlist_count}
                  </td>
                  <td className="px-3 py-2 text-center">
                    {u.is_admin ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-accent-yellow/15 px-2 py-0.5 text-xs font-bold text-accent-yellow">
                        <Shield className="h-3 w-3" />
                        ADMIN
                      </span>
                    ) : (
                      <span className="text-xs text-text-tertiary">member</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <div className="inline-flex gap-1">
                      <button
                        onClick={() => toggleAdmin(u)}
                        disabled={u.id === me?.id && u.is_admin}
                        title={
                          u.id === me?.id && u.is_admin
                            ? "Admins can't demote themself"
                            : u.is_admin
                              ? "Remove admin"
                              : "Make admin"
                        }
                        className="rounded-btn border border-border bg-bg px-2 py-1 text-xs font-semibold text-text-secondary hover:text-text-primary disabled:opacity-40"
                      >
                        {u.is_admin ? "Demote" : "Promote"}
                      </button>
                      {u.deleted_at ? (
                        <button
                          onClick={() => restore(u)}
                          className="inline-flex items-center gap-1 rounded-btn border border-accent-green/40 bg-accent-green/10 px-2 py-1 text-xs font-semibold text-accent-green hover:bg-accent-green/20"
                        >
                          <Undo2 className="h-3 w-3" />
                          Restore
                        </button>
                      ) : (
                        <button
                          onClick={() => softDelete(u)}
                          disabled={u.id === me?.id}
                          title={
                            u.id === me?.id
                              ? "Admins can't delete themself"
                              : "Soft delete"
                          }
                          className="inline-flex items-center gap-1 rounded-btn border border-accent-red/40 bg-accent-red/10 px-2 py-1 text-xs font-semibold text-accent-red hover:bg-accent-red/20 disabled:opacity-40"
                        >
                          <Trash2 className="h-3 w-3" />
                          Delete
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        </>
      )}

      {/* Pagination */}
      {data && totalPages > 1 && (
        <div className="mt-4 flex items-center justify-center gap-2 text-sm">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="rounded-btn border border-border bg-bg-surface px-3 py-1.5 text-text-secondary hover:text-text-primary disabled:opacity-40"
          >
            Prev
          </button>
          <span className="font-mono text-xs text-text-tertiary">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="rounded-btn border border-border bg-bg-surface px-3 py-1.5 text-text-secondary hover:text-text-primary disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </main>
  );
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
