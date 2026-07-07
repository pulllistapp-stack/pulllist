"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

/**
 * Fires when the user's binder crosses 0 → 100% base completion for
 * the first time. Renders a full-screen confetti burst + a slide-in
 * banner. Both dismiss automatically; the banner accepts a manual
 * dismiss too.
 *
 * canvas-confetti is loaded dynamically so it stays out of the initial
 * bundle for users who never hit 100%.
 */
export function CompletionCelebration({
  setName,
  onDismiss,
}: {
  setName: string;
  onDismiss?: () => void;
}) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const confetti = (await import("canvas-confetti")).default;
      if (cancelled) return;
      // Two-burst golden shower — one from each side, sweeping toward
      // the center. Yellow/gold palette matches the persistent cover
      // treatment that follows.
      const palette = ["#facc15", "#f59e0b", "#fbbf24", "#fde68a", "#22c55e"];
      const shots = [
        { angle: 60, x: 0, y: 0.7 },
        { angle: 120, x: 1, y: 0.7 },
      ];
      shots.forEach((s) => {
        confetti({
          particleCount: 90,
          spread: 70,
          startVelocity: 55,
          angle: s.angle,
          origin: { x: s.x, y: s.y },
          colors: palette,
          scalar: 1.1,
          ticks: 240,
        });
      });
      // Follow-up soft burst from the top-center a moment later.
      window.setTimeout(() => {
        confetti({
          particleCount: 60,
          spread: 130,
          startVelocity: 35,
          origin: { x: 0.5, y: 0 },
          colors: palette,
          gravity: 0.7,
          ticks: 300,
        });
      }, 350);
    })();

    const timer = window.setTimeout(() => setVisible(false), 6500);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, []);

  const dismiss = () => {
    setVisible(false);
    onDismiss?.();
  };

  return (
    <AnimatePresence onExitComplete={onDismiss}>
      {visible && (
        <motion.div
          initial={{ y: -80, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -80, opacity: 0 }}
          transition={{ type: "spring", stiffness: 220, damping: 22 }}
          className="fixed left-1/2 top-6 z-[60] -translate-x-1/2 max-w-md w-[92%]"
          role="status"
          aria-live="polite"
        >
          <button
            type="button"
            onClick={dismiss}
            className="w-full rounded-full border border-accent-yellow/60 bg-gradient-to-r from-amber-500 via-yellow-400 to-amber-500 text-black shadow-[0_10px_30px_-8px_rgba(250,204,21,0.65)] px-4 py-3 text-left flex items-center gap-3"
          >
            <span className="relative flex h-9 w-9 items-center justify-center rounded-full bg-black/15">
              <Sparkles className="h-5 w-5" />
            </span>
            <span className="flex-1 min-w-0">
              <span className="block text-[10px] font-black uppercase tracking-[0.25em] text-black/70">
                Master Complete
              </span>
              <span className="block text-sm font-bold truncate">
                You filled every slot in {setName}!
              </span>
            </span>
            <span className="text-[10px] font-mono uppercase tracking-wider text-black/60">
              Dismiss
            </span>
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
