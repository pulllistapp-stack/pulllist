"use client";

import Image from "next/image";

/**
 * Small closed-binder thumbnail — used on /portfolio/masters list cards
 * so each row shows what the user's actual binder looks like at a glance.
 *
 * Same visual grammar as the full BinderSpread cover (dark shell +
 * diamond quilt + dashed stitching + optional user cover) but stripped
 * to the essentials at ~64x80 so it fits in a list row. If no custom
 * cover, falls back to the default mascot centered on the shell.
 */
export function MiniBinderCover({
  coverImageUrl,
  className = "",
}: {
  coverImageUrl: string | null;
  className?: string;
}) {
  return (
    <div
      className={
        "relative shrink-0 overflow-hidden rounded-md shadow-[0_4px_10px_-2px_rgba(0,0,0,0.5)] " +
        className
      }
      style={{
        background:
          "linear-gradient(160deg, #1a1a1a 0%, #0d0d0d 55%, #222222 100%)",
      }}
      aria-hidden
    >
      {/* User cover if set — foreground image */}
      {coverImageUrl && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={coverImageUrl}
          alt=""
          className="absolute inset-0 h-full w-full object-cover"
        />
      )}

      {/* Diamond quilted texture — tight cycle for the mini scale */}
      <div
        className="absolute inset-0 pointer-events-none mix-blend-multiply opacity-75"
        style={{
          backgroundImage: [
            "repeating-linear-gradient(45deg, rgba(0,0,0,0.4) 0px, rgba(0,0,0,0.4) 0.4px, transparent 0.4px, transparent 3.5px)",
            "repeating-linear-gradient(-45deg, rgba(0,0,0,0.4) 0px, rgba(0,0,0,0.4) 0.4px, transparent 0.4px, transparent 3.5px)",
          ].join(", "),
        }}
      />
      <div
        className="absolute inset-0 pointer-events-none mix-blend-screen opacity-55"
        style={{
          backgroundImage: [
            "repeating-linear-gradient(45deg, transparent 0.4px, rgba(255,255,255,0.45) 0.4px, rgba(255,255,255,0.45) 0.9px, transparent 0.9px, transparent 3.5px)",
            "repeating-linear-gradient(-45deg, transparent 0.4px, rgba(255,255,255,0.45) 0.4px, rgba(255,255,255,0.45) 0.9px, transparent 0.9px, transparent 3.5px)",
          ].join(", "),
        }}
      />

      {/* Default mascot when no custom cover — sits above the quilt */}
      {!coverImageUrl && (
        <div className="absolute inset-0 z-10 flex items-center justify-center">
          <div className="relative h-3/4 w-3/4">
            <Image
              src="/pullist-mascot.png"
              alt=""
              fill
              sizes="80px"
              className="object-contain drop-shadow-[0_2px_4px_rgba(0,0,0,0.6)]"
              unoptimized
            />
          </div>
        </div>
      )}

      {/* Dashed stitch border — dark shadow + light thread pair */}
      <div
        className="absolute inset-[3px] rounded-[3px] pointer-events-none z-20"
        style={{
          border: "1px dashed rgba(0,0,0,0.45)",
          transform: "translate(0.3px, 0.3px)",
        }}
      />
      <div
        className="absolute inset-[3px] rounded-[3px] pointer-events-none z-20"
        style={{ border: "1px dashed rgba(255,255,255,0.55)" }}
      />
    </div>
  );
}
