import { redirect } from "next/navigation";

/**
 * /me/collection was a near-duplicate of /portfolio. The config-level
 * redirect in next.config.mjs catches direct navigation; this file
 * exists so Next.js 16's typed-routes validator stops failing the build
 * (it generates a typecheck stub for every referenced route, including
 * those covered only by config redirects). Server-side redirect here
 * matches the config redirect's behaviour for any path that slips past.
 */
export default function MeCollectionRedirect() {
  redirect("/portfolio");
}
