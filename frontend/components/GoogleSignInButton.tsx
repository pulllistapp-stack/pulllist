"use client";

import Script from "next/script";
import { useEffect, useId, useRef, useState } from "react";

import { useAuth } from "@/components/AuthProvider";

/**
 * Renders Google's official "Sign in with Google" button via the Identity
 * Services library. On success Google posts the ID token via a callback;
 * we forward it to /auth/google which mints a PullList JWT.
 *
 * The library is loaded once from accounts.google.com/gsi/client - this
 * component handles the script-ready handshake and exposes the same UX
 * on /login and /signup. No client secret is required: ID token signature
 * is verified server-side against Google's public keys.
 */
type Props = {
  onSuccess?: () => void;
  onError?: (message: string) => void;
  text?: "signin_with" | "signup_with" | "continue_with";
  width?: number;
};

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential: string }) => void;
            ux_mode?: "popup" | "redirect";
            auto_select?: boolean;
            cancel_on_tap_outside?: boolean;
          }) => void;
          renderButton: (
            element: HTMLElement,
            options: {
              type?: "standard" | "icon";
              theme?: "outline" | "filled_blue" | "filled_black";
              size?: "large" | "medium" | "small";
              text?: "signin_with" | "signup_with" | "continue_with" | "signin";
              shape?: "rectangular" | "pill" | "circle" | "square";
              logo_alignment?: "left" | "center";
              width?: number;
            },
          ) => void;
        };
      };
    };
  }
}

export function GoogleSignInButton({
  onSuccess,
  onError,
  text = "continue_with",
  width = 360,
}: Props) {
  const { loginWithGoogle } = useAuth();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [scriptReady, setScriptReady] = useState(false);
  const buttonId = useId();
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

  useEffect(() => {
    if (!scriptReady || !clientId || !containerRef.current) return;
    if (!window.google?.accounts?.id) return;

    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: async (response: { credential: string }) => {
        try {
          await loginWithGoogle(response.credential);
          onSuccess?.();
        } catch (err) {
          onError?.(err instanceof Error ? err.message : "Google sign-in failed");
        }
      },
      // Popup keeps users on our domain so existing in-page errors and the
      // post-auth redirect still work without a full page refresh.
      ux_mode: "popup",
      auto_select: false,
      cancel_on_tap_outside: true,
    });

    window.google.accounts.id.renderButton(containerRef.current, {
      type: "standard",
      theme: "outline",
      size: "large",
      text,
      shape: "pill",
      logo_alignment: "left",
      width,
    });
  }, [scriptReady, clientId, loginWithGoogle, onSuccess, onError, text, width]);

  if (!clientId) {
    // Safe fallback: never show a broken/disabled button in prod; if the
    // env var is missing the page just hides this option.
    return null;
  }

  return (
    <>
      <Script
        src="https://accounts.google.com/gsi/client"
        strategy="afterInteractive"
        onLoad={() => setScriptReady(true)}
      />
      <div
        id={buttonId}
        ref={containerRef}
        className="flex justify-center min-h-[42px]"
      />
    </>
  );
}
