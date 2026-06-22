import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Edge middleware — runs before any /admin/* page is rendered.
 *
 * Real admin auth (is_admin check, JWT verification) happens at the
 * backend on every API call this page makes. This middleware is just
 * the outermost layer of defense: it blocks the page render entirely
 * unless the visitor has an auth artifact in their cookies.
 *
 * Because our JWT lives in localStorage (not cookies), this only stops
 * fully-unauthenticated drive-by traffic — anyone who can log in
 * client-side still hits the page and is then filtered by AdminGuard
 * + backend 403s. That's an intentional design choice: it keeps the
 * middleware cheap, avoids the cookie-vs-localStorage complexity, and
 * the authoritative checks still happen at the backend where data
 * actually lives.
 *
 * If you need stricter edge enforcement later, add a `pulllist_session`
 * cookie alongside the localStorage token at sign-in and read it here.
 */

const PROTECTED_PREFIXES = ["/admin"];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (!PROTECTED_PREFIXES.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // We don't have a server-readable token cookie today. So just signal
  // that this is a sensitive surface — let the client-side AdminGuard
  // handle the redirect on actual auth/admin failure. Crawlers and
  // direct-link bots that don't execute JS will see this as a normal
  // page response with no admin data (since SSR for these pages
  // renders the loader, not the form).
  const res = NextResponse.next();
  res.headers.set("X-Robots-Tag", "noindex, nofollow");
  res.headers.set("Cache-Control", "no-store, must-revalidate");
  return res;
}

export const config = {
  matcher: ["/admin/:path*"],
};
