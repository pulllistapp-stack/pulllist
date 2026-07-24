import { cookies, headers } from "next/headers";
import { NextResponse } from "next/server";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

const TOKEN_COOKIE = "pulllist_token";

/**
 * Edge-side visit forwarder. The browser fires `POST /api/track-visit`
 * with `{ session_id, path, referrer, device }`; we enrich with country /
 * region / city from Vercel's edge-injected headers (`x-vercel-ip-*`)
 * — free, no external geo API — and forward to the backend with the
 * user's auth token attached so the backend can attribute the visit.
 *
 * Returns 204 immediately on errors so a broken tracker never blocks a
 * page render; visit gaps are acceptable, app slowness isn't.
 */
export async function POST(req: Request): Promise<NextResponse> {
  let body: {
    session_id?: string;
    path?: string;
    referrer?: string | null;
    device?: string | null;
  };
  try {
    body = await req.json();
  } catch {
    return new NextResponse(null, { status: 204 });
  }

  if (!body.session_id || !body.path) {
    return new NextResponse(null, { status: 204 });
  }

  const h = await headers();
  const country = h.get("x-vercel-ip-country");
  const region = h.get("x-vercel-ip-country-region");
  const city = h.get("x-vercel-ip-city");
  // Forward the real client UA so backend bot detection
  // (app.services.bot_detect) can classify crawlers. Without this,
  // fetch() uses Node's default 'undici' UA and every visit looks the
  // same to the backend — bot_name would stay null forever.
  const userAgent = h.get("user-agent") ?? "";

  const token = (await cookies()).get(TOKEN_COOKIE)?.value;

  const payload = {
    session_id: body.session_id,
    path: body.path,
    referrer: body.referrer ?? null,
    device: body.device ?? null,
    country: country || null,
    region: region || null,
    // Vercel returns URL-encoded city ('San%20Francisco') — decode for storage
    city: city ? safeDecode(city) : null,
  };

  try {
    await fetch(`${API_BASE}/visits`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "User-Agent": userAgent,
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(payload),
      // Don't block the response on backend latency
      cache: "no-store",
    });
  } catch {
    // Swallow — visit logging is best-effort
  }

  return new NextResponse(null, { status: 204 });
}

function safeDecode(s: string): string {
  try {
    return decodeURIComponent(s);
  } catch {
    return s;
  }
}
