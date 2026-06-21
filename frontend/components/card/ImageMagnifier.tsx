"use client";

import { useEffect, useRef, useState } from "react";
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
  // Cursor position relative to the image (in pixels). null = off-image.
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);

  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setActive(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active]);

  const onMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!active) return;
    const el = containerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    setPos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
  };

  const onMouseLeave = () => {
    if (!active) return;
    setPos(null);
  };

  const onClick = (e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
    setActive((prev) => !prev);
    if (!active) {
      // Seed initial position so the loupe shows immediately
      const el = containerRef.current;
      if (el) {
        const rect = el.getBoundingClientRect();
        setPos({
          x: e.clientX - rect.left,
          y: e.clientY - rect.top,
        });
      }
    } else {
      setPos(null);
    }
  };

  // Loupe positioning math: we want the cursor to sit at the loupe's
  // center, and the background image to be aligned so the same physical
  // point on the card sits under the cursor at zoom×.
  const rect = containerRef.current?.getBoundingClientRect();
  const bgWidth = (rect?.width ?? 0) * zoom;
  const bgHeight = (rect?.height ?? 0) * zoom;
  const bgX = pos ? -(pos.x * zoom - loupeSize / 2) : 0;
  const bgY = pos ? -(pos.y * zoom - loupeSize / 2) : 0;

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

      {/* Loupe */}
      {active && pos && (
        <div
          aria-hidden
          className="pointer-events-none absolute z-30 rounded-full border-2 border-white shadow-[0_8px_24px_rgba(0,0,0,0.5),inset_0_0_0_1px_rgba(0,0,0,0.4)] ring-2 ring-black/30"
          style={{
            width: loupeSize,
            height: loupeSize,
            left: pos.x - loupeSize / 2,
            top: pos.y - loupeSize / 2,
            backgroundImage: `url("${src}")`,
            backgroundRepeat: "no-repeat",
            backgroundSize: `${bgWidth}px ${bgHeight}px`,
            backgroundPosition: `${bgX}px ${bgY}px`,
          }}
        />
      )}
    </div>
  );
}
