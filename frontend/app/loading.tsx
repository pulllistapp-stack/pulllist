import { MascotLoader } from "@/components/MascotLoader";

/**
 * Global route-transition loader.
 *
 * Next.js renders this between route segments while server components
 * for the next page are streaming. Mascot + rotating phrase is a friendlier
 * idle than a grey skeleton grid for the brief route-switch window.
 */
export default function Loading() {
  return (
    <div
      className="px-4 sm:px-6 py-16 sm:py-24 max-w-7xl mx-auto flex items-center justify-center min-h-[40vh]"
      aria-busy="true"
      aria-live="polite"
    >
      <MascotLoader size="lg" />
    </div>
  );
}
