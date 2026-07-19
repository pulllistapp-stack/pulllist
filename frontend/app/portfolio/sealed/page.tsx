"use client";

/**
 * /portfolio/sealed — user's sealed inventory (boxes, ETBs, bundles).
 * Parallel to the singles Collection tab; renders tiles from the
 * SealedCollectionEntry payload the backend joins for us.
 */

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Bookmark, LineChart, Loader2, Pencil, Trash2 } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { MascotLoader } from "@/components/MascotLoader";
import { PortfolioTabs } from "@/components/portfolio/PortfolioTabs";
import { SealedItemEditModal } from "@/components/portfolio/SealedItemEditModal";
import {
  deleteSealedOwnership,
  listSealedCollection,
  listSealedWishlist,
  SealedCollectionEntry,
  SealedCollectionList,
  SealedWishlistList,
  toggleSealedWishlist,
} from "@/lib/api";

const CONDITION_LABEL: Record<string, string> = {
  sealed: "Sealed",
  opened: "Opened",
  damaged: "Damaged",
};

const TYPE_LABEL: Record<string, string> = {
  booster_box: "Booster Box",
  etb: "Elite Trainer Box",
  booster_bundle: "Booster Bundle",
  premium_collection: "Premium Collection",
  tin: "Tin",
  blister: "Blister",
  build_battle: "Build & Battle",
  sleeved_booster: "Sleeved Booster",
  other: "Other",
};

function fmtPrice(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1000) return `$${Math.round(v).toLocaleString()}`;
  return `$${v.toFixed(2)}`;
}

export default function SealedPortfolioPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [collection, setCollection] = useState<SealedCollectionList | null>(null);
  const [wishlist, setWishlist] = useState<SealedWishlistList | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<SealedCollectionEntry | null>(null);

  const reloadCollection = async () => {
    try {
      const c = await listSealedCollection();
      setCollection(c);
    } catch {
      /* silent */
    }
  };

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.replace("/login?next=/portfolio/sealed");
      return;
    }
    let cancelled = false;
    setLoading(true);
    Promise.all([listSealedCollection(), listSealedWishlist()])
      .then(([c, w]) => {
        if (cancelled) return;
        setCollection(c);
        setWishlist(w);
      })
      .catch(() => {
        if (cancelled) return;
        setCollection({
          items: [],
          total_owned: 0,
          unique_products: 0,
          estimated_value_usd: 0,
        });
        setWishlist({ items: [], count: 0 });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user, authLoading, router]);

  const removeOwned = async (productId: string) => {
    await deleteSealedOwnership(productId);
    setCollection((prev) =>
      prev
        ? {
            ...prev,
            items: prev.items.filter((e) => e.product.id !== productId),
            unique_products: prev.unique_products - 1,
          }
        : prev,
    );
  };

  const removeWishlisted = async (productId: string) => {
    await toggleSealedWishlist(productId);
    setWishlist((prev) =>
      prev
        ? {
            ...prev,
            items: prev.items.filter((e) => e.product.id !== productId),
            count: prev.count - 1,
          }
        : prev,
    );
  };

  if (authLoading || loading) {
    return (
      <main className="mx-auto max-w-[100rem] px-4 py-8">
        <PortfolioTabs active="sealed" />
        <div className="flex justify-center py-16">
          <MascotLoader />
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-[100rem] px-4 py-8">
      <PortfolioTabs active="sealed" />

      <header className="mb-6 rounded-card border border-border bg-bg-surface/70 p-5">
        <div className="flex flex-wrap items-baseline gap-8">
          <div>
            <div className="text-3xl font-extrabold text-text-primary">
              {collection?.unique_products ?? 0}
            </div>
            <div className="mt-1 text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
              Unique products
            </div>
          </div>
          <div>
            <div className="text-3xl font-extrabold text-text-primary">
              {collection?.total_owned ?? 0}
            </div>
            <div className="mt-1 text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
              Total copies
            </div>
          </div>
          <div>
            <div className="text-3xl font-extrabold text-accent-green">
              {fmtPrice(collection?.estimated_value_usd)}
            </div>
            <div className="mt-1 text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
              Est. value
            </div>
          </div>
          <div>
            <div className="text-3xl font-extrabold text-text-primary">
              {wishlist?.count ?? 0}
            </div>
            <div className="mt-1 text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
              On wishlist
            </div>
          </div>
        </div>
      </header>

      <section className="mb-10">
        <h2 className="mb-3 text-lg font-bold tracking-tight">In your collection</h2>
        {collection && collection.items.length > 0 ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
            {collection.items.map((entry) => (
              <SealedTile
                key={entry.product.id}
                entry={entry}
                onRemove={() => removeOwned(entry.product.id)}
                onEdit={() => setEditing(entry)}
                removeIcon="trash"
              />
            ))}
          </div>
        ) : (
          <EmptyState
            title="No sealed products in your collection yet"
            body="Open any sealed product page and click Mark as owned to add it here."
          />
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-bold tracking-tight">Wishlist</h2>
        {wishlist && wishlist.items.length > 0 ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
            {wishlist.items.map((entry) => (
              <SealedTile
                key={entry.product.id}
                entry={{ product: entry.product, item: null }}
                onRemove={() => removeWishlisted(entry.product.id)}
                removeIcon="bookmark"
              />
            ))}
          </div>
        ) : (
          <EmptyState
            title="Nothing on your sealed wishlist yet"
            body="Add products from any sealed product page — deal alerts will use this list once shipping."
          />
        )}
      </section>
      {editing && (
        <SealedItemEditModal
          entry={editing}
          onClose={() => setEditing(null)}
          onSaved={reloadCollection}
          onDeleted={reloadCollection}
        />
      )}
    </main>
  );
}

function SealedTile({
  entry,
  onRemove,
  onEdit,
  removeIcon,
}: {
  entry: {
    product: {
      id: string;
      name: string;
      product_type: string;
      set_id: string | null;
      market_price_usd: number | null;
      image_url: string | null;
    };
    item:
      | {
          qty: number;
          condition?: string;
          purchase_price_usd: number | null;
        }
      | null;
  };
  onRemove: () => void;
  onEdit?: () => void;
  removeIcon: "trash" | "bookmark";
}) {
  const [removing, setRemoving] = useState(false);
  const handleRemove = async () => {
    if (removing) return;
    setRemoving(true);
    try {
      await onRemove();
    } catch {
      setRemoving(false);
    }
  };
  return (
    <div className="group relative overflow-hidden rounded-card border border-border bg-bg-surface transition-colors hover:border-accent-yellow/40">
      <Link
        href={`/products/${entry.product.id}`}
        className="block"
        aria-label={entry.product.name}
      >
        <div className="relative aspect-[3/4] bg-bg">
          {entry.product.image_url ? (
            <Image
              src={entry.product.image_url}
              alt={entry.product.name}
              fill
              className="object-contain p-2"
              sizes="(max-width: 640px) 50vw, (max-width: 1024px) 25vw, 15vw"
              unoptimized
            />
          ) : (
            <div className="flex h-full items-center justify-center text-text-tertiary text-xs">
              No image
            </div>
          )}
        </div>
        <div className="p-2">
          <div className="text-[10px] uppercase font-mono text-text-tertiary tracking-wider">
            {TYPE_LABEL[entry.product.product_type] ?? entry.product.product_type}
          </div>
          <div className="mt-1 line-clamp-2 text-xs font-semibold text-text-primary">
            {entry.product.name}
          </div>
          <div className="mt-1 flex items-center justify-between text-xs">
            <span className="font-mono text-accent-green">
              {fmtPrice(entry.product.market_price_usd)}
            </span>
            {entry.item?.qty && entry.item.qty > 1 && (
              <span className="font-mono text-text-tertiary">
                ×{entry.item.qty}
              </span>
            )}
          </div>
          {entry.item && (
            <div className="mt-1 flex items-center gap-1 text-[10px] font-mono text-text-tertiary">
              {entry.item.condition && (
                <span
                  className={
                    "rounded px-1.5 py-[1px] uppercase tracking-wider " +
                    (entry.item.condition === "sealed"
                      ? "bg-accent-green/15 text-accent-green"
                      : entry.item.condition === "opened"
                      ? "bg-amber-500/15 text-amber-400"
                      : "bg-red-500/15 text-red-400")
                  }
                >
                  {CONDITION_LABEL[entry.item.condition] ?? entry.item.condition}
                </span>
              )}
              {entry.item.purchase_price_usd != null && (
                <span>paid ${entry.item.purchase_price_usd.toFixed(2)}</span>
              )}
            </div>
          )}
        </div>
      </Link>
      {/* Action rail — appears on hover / touch. Edit + chart-link
          only surface for owned rows (wishlist tiles hide them). */}
      <div className="absolute right-1.5 top-1.5 flex gap-1 opacity-0 transition group-hover:opacity-100">
        {onEdit && (
          <button
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onEdit();
            }}
            aria-label="Edit"
            className="rounded-full border border-border bg-bg/80 p-1.5 text-text-tertiary backdrop-blur hover:text-accent-yellow transition-colors"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
        )}
        <Link
          href={`/products/${entry.product.id}`}
          aria-label="Price history"
          className="rounded-full border border-border bg-bg/80 p-1.5 text-text-tertiary backdrop-blur hover:text-accent-yellow transition-colors"
          onClick={(e) => e.stopPropagation()}
        >
          <LineChart className="h-3.5 w-3.5" />
        </Link>
        <button
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            handleRemove();
          }}
          disabled={removing}
          aria-label={
            removeIcon === "trash" ? "Remove from collection" : "Remove from wishlist"
          }
          className="rounded-full border border-border bg-bg/80 p-1.5 text-text-tertiary backdrop-blur hover:text-accent-red disabled:opacity-30 transition-colors"
        >
          {removing ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : removeIcon === "trash" ? (
            <Trash2 className="h-3.5 w-3.5" />
          ) : (
            <Bookmark className="h-3.5 w-3.5" fill="currentColor" />
          )}
        </button>
      </div>
    </div>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-card border border-dashed border-border/60 bg-bg-surface/40 p-8 text-center">
      <div className="text-sm font-semibold text-text-secondary">{title}</div>
      <div className="mt-1 text-xs text-text-tertiary">{body}</div>
    </div>
  );
}
