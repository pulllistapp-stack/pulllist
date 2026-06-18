/**
 * Global route-transition skeleton.
 *
 * Next.js renders this between route segments while server components
 * for the next page are streaming. Keep it cheap and neutral - no
 * page-specific shapes here, that's what nested loading.tsx files
 * are for.
 */
export default function Loading() {
  return (
    <div className="px-4 sm:px-6 py-8 sm:py-10 max-w-7xl mx-auto" aria-busy="true" aria-live="polite">
      <div className="space-y-6">
        {/* Header skeleton */}
        <div className="flex items-center justify-between gap-4">
          <div className="space-y-2 flex-1">
            <div className="h-3 w-24 rounded-full bg-bg-surface animate-pulse" />
            <div className="h-8 w-3/5 max-w-md rounded-lg bg-bg-surface animate-pulse" />
          </div>
          <div className="hidden sm:flex gap-2">
            <div className="h-9 w-28 rounded-full bg-bg-surface animate-pulse" />
            <div className="h-9 w-28 rounded-full bg-bg-surface animate-pulse" />
          </div>
        </div>

        {/* Stat row skeleton */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="h-24 rounded-2xl border border-border bg-bg-surface animate-pulse"
            />
          ))}
        </div>

        {/* Grid skeleton */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {Array.from({ length: 10 }).map((_, i) => (
            <div
              key={i}
              className="aspect-[5/7] rounded-xl border border-border bg-bg-surface animate-pulse"
              style={{ animationDelay: `${i * 60}ms` }}
            />
          ))}
        </div>
      </div>

      <span className="sr-only">Loading…</span>
    </div>
  );
}
