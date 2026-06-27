import { NextResponse } from "next/server";
import { put } from "@vercel/blob";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

// Vercel Serverless body cap is 4.5MB — anything larger needs the
// client-side upload flow (`handleUploadUrl` + browser direct PUT).
// At friends-beta scale LO's screenshots/cards rarely exceed 1MB,
// so server-side keeps the code simple. Bump or migrate if we hit
// it in practice.
const MAX_BYTES = 4_500_000;

const ALLOWED_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/gif",
  "image/webp",
  "image/avif",
]);

// `<title>-<random>.<ext>` — Blob auto-adds a random suffix when
// addRandomSuffix is true (default), but pre-slugging the original
// filename keeps the URL legible for debugging.
function sanitizeFilename(raw: string): string {
  const base = raw.replace(/\.[^.]+$/, "").toLowerCase();
  const ext = raw.match(/\.[^.]+$/)?.[0]?.toLowerCase() ?? "";
  const slug = base
    .normalize("NFKD")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60) || "image";
  return `${slug}${ext}`;
}

export async function POST(req: Request): Promise<NextResponse> {
  if (!process.env.BLOB_READ_WRITE_TOKEN) {
    return NextResponse.json(
      {
        error:
          "Vercel Blob not configured. Add BLOB_READ_WRITE_TOKEN (Vercel " +
          "dashboard → Storage → Blob → connect to project).",
      },
      { status: 500 },
    );
  }

  // Admin gate — forward the user's bearer to backend /auth/me and
  // bail unless is_admin is true. Keeps unauthenticated traffic
  // from burning the Blob quota.
  const auth = req.headers.get("authorization");
  if (!auth?.startsWith("Bearer ")) {
    return NextResponse.json({ error: "Missing bearer token" }, { status: 401 });
  }
  let isAdmin = false;
  try {
    const me = await fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: auth },
      cache: "no-store",
    });
    if (me.status === 401) {
      return NextResponse.json({ error: "Invalid token" }, { status: 401 });
    }
    if (!me.ok) {
      return NextResponse.json(
        { error: `Auth check failed: ${me.status}` },
        { status: 502 },
      );
    }
    const data = await me.json();
    isAdmin = data?.is_admin === true;
  } catch (e) {
    return NextResponse.json(
      { error: `Auth check failed: ${String(e)}` },
      { status: 502 },
    );
  }
  if (!isAdmin) {
    return NextResponse.json({ error: "Admin only" }, { status: 403 });
  }

  let form: FormData;
  try {
    form = await req.formData();
  } catch (e) {
    return NextResponse.json(
      { error: `Bad multipart body: ${String(e)}` },
      { status: 400 },
    );
  }

  const file = form.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json(
      { error: "Field 'file' missing or not a file" },
      { status: 400 },
    );
  }
  if (!ALLOWED_TYPES.has(file.type)) {
    return NextResponse.json(
      {
        error: `Unsupported type ${file.type}. Use JPEG / PNG / GIF / WEBP / AVIF.`,
      },
      { status: 415 },
    );
  }
  if (file.size > MAX_BYTES) {
    return NextResponse.json(
      {
        error:
          `File too large (${(file.size / 1_000_000).toFixed(1)}MB > 4.5MB). ` +
          "Compress the image (tinypng.com) or crop it before uploading.",
      },
      { status: 413 },
    );
  }

  const filename = sanitizeFilename(file.name || "image");
  try {
    const blob = await put(`news/${filename}`, file, {
      access: "public",
      contentType: file.type,
      // Random suffix prevents collisions across uploads with the
      // same source filename — multiple "card.jpg" don't clobber.
      addRandomSuffix: true,
    });
    return NextResponse.json({ url: blob.url });
  } catch (e) {
    return NextResponse.json(
      { error: `Blob upload failed: ${String(e)}` },
      { status: 502 },
    );
  }
}
