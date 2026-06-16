import Image from "next/image";

import { cn } from "@/lib/utils";

export function MascotMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "relative inline-block overflow-hidden rounded-full ring-2 ring-amber-300/60",
        className,
      )}
    >
      <Image
        src="/pullist-mascot.png"
        alt="PullList mascot"
        fill
        className="object-cover"
        sizes="80px"
        unoptimized
      />
    </span>
  );
}
