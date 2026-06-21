"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Image from "next/image";

import { cn } from "@/lib/utils";

type Props = {
  src: string;
  alt: string;
  /** Inner content rendered on top of the image (shimmer / stars / etc).
   *  The wrapper div is what receives mouse events. */
  children?: React.ReactNode;
  /** Multiplier for the loupe view. 2.5x feels right for trading cards. */
  zoom?: number;
  /** Pixel diameter of the loupe circle. */
  loupeSize?: number;
  /** Optional className for the outer wrapper (slot in tilt/shadow styling). */
  className?: string;
  /** Image sizes attribute, passed through to next/image. */
  sizes?: string;
};

/**
 * Click-to-toggle magnifier loupe. Default state: nothing changes — the
 * card image behaves exactly like before (hover tilt + shimmer still
 * fire). One click activates a small circular loupe that follows the
 * cursor showing a zoomed view of the card. Click again or press Esc to
 * exit.
 *
 * The loupe is a sibling div with `background-image: url(src)` sized at
 * `zoom * 100%` and re-positioned per frame to keep the focus point
 * under the cursor. Cheaper than a portal and stays inside the card
 * bounding box so we don't fight overflow rules.
 */
/** Vertical gap between cursor and the loupe's nearest edge.
 *  Keeps the cursor visible just below the loupe so users always see
 *  what they're pointing at. */
const CURSOR_GAP_PX = 12;

export function ImageMagnifier({
  src,
  alt,
  children,
  zoom = 2.5,
  loupeSize = 130,
  className,
  sizes,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [active, setActive] = useState(false);
  const [mounted, setMounted] = useState(false);

  // React portal targets need to exist before render; SSR'd HTML can't
  // include them. Toggle a flag on mount so the portal only renders
  // client-side after document.body is available.
  useEffect(() => {
    setMounted(true);
  }, []);
  // Cursor position. `local` is relative to the image (for background-position
  // math), `viewport` is clientX/clientY (for `position: fixed` loupe placement
  // so it escapes the card container's overflow-hidden box).
  const [pos, setPos] = useState<
    | { localX: number; localY: number; viewportX: number; viewportY: number }
    | null
  >(null);

  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setActive(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active]);

  const updatePos = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = containerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    setPos({
      localX: e.clientX - rect.left,
      localY: e.clientY - rect.top,
      viewportX: e.clientX,
      viewportY: e.clientY,
    });
  };

  const onMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!active) return;
    updatePos(e);
  };

  const onMouseLeave = () => {
    if (!active) return;
    setPos(null);
  };

  const onClick = (e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
    setActive((prev) => !prev);
    if (!active) updatePos(e);
    else setPos(null);
  };

  // Loupe positioning math: cursor sits at the loupe center, background
  // image aligned so the same physical point on the card sits under the
  // cursor at zoom×.
  const rect = containerRef.current?.getBoundingClientRect();
  const bgWidth = (rect?.width ?? 0) * zoom;
  const bgHeight = (rect?.height ?? 0) * zoom;
  const bgX = pos ? -(pos.localX * zoom - loupeSize / 2) : 0;
  const bgY = pos ? -(pos.localY * zoom - loupeSize / 2) : 0;

  return (
    <div
      ref={containerRef}
      onClick={onClick}
      onMouseMove={onMouseMove}
      onMouseLeave={onMouseLeave}
      className={cn(
        "relative",
        active ? "cursor-zoom-out" : "cursor-zoom-in",
        className,
      )}
      title={active ? "Click to exit zoom (Esc)" : "Click to zoom"}
    >
      <Image
        src={src}
        alt={alt}
        fill
        priority
        className="object-cover select-none"
        sizes={sizes}
        unoptimized
        draggable={false}
      />
      {children}

      {/* Loupe — rendered via portal directly under document.body so
       *  it escapes any parent's overflow-hidden box AND any parent's
       *  transform (the card hero applies a hover tilt, which would
       *  otherwise scope `position: fixed` to that transformed
       *  ancestor and re-introduce clipping).
       *
       *  Positioned ABOVE the cursor with a small gap so the user
       *  always sees what they're pointing at — the magnified content
       *  sits like a tooltip just above the pointer. Clamped against
       *  the viewport edges so it never goes off-screen near the top. */}
      {active && pos && mounted &&
        createPortal(
          <div
            aria-hidden
            className="pointer-events-none fixed z-[9999] rounded-full border-2 border-white shadow-[0_8px_24px_rgba(0,0,0,0.5),inset_0_0_0_1px_rgba(0,0,0,0.4)] ring-2 ring-black/30"
            style={{
              width: loupeSize,
              height: loupeSize,
              left: Math.max(
                8,
                Math.min(
                  window.innerWidth - loupeSize - 8,
                  pos.viewportX - loupeSize / 2,
                ),
              ),
              top: Math.max(
                8,
                pos.viewportY - loupeSize - CURSOR_GAP_PX,
              ),
              backgroundImage: `url("${src}")`,
              backgroundRepeat: "no-repeat",
              backgroundSize: `${bgWidth}px ${bgHeight}px`,
              backgroundPosition: `${bgX}px ${bgY}px`,
            }}
          />,
          document.body,
        )}
    </div>
  );
}
