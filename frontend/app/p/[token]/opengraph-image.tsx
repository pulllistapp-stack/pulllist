/**
 * Dynamic OG image for shared portfolios.
 *
 * Next.js App Router picks up any `opengraph-image.tsx` file as the OG
 * meta image for the surrounding route. We render a 1200×630 PNG via
 * `next/og` that shows the owner's display name, portfolio value (if
 * public), card/set counts, and a brand wordmark — the unfurled card
 * that appears when someone pastes their share link into Discord,
 * Twitter/X, KakaoTalk, Slack, iMessage previews, etc.
 */
import { ImageResponse } from "next/og";
import { readFileSync } from "node:fs";
import path from "node:path";

import type { PublicPortfolio } from "@/lib/api";

export const runtime = "nodejs";
export const alt = "PullList portfolio";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

async function fetchPublic(token: string): Promise<PublicPortfolio | null> {
  try {
    const res = await fetch(`${API_BASE}/p/${encodeURIComponent(token)}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return null;
    return (await res.json()) as PublicPortfolio;
  } catch {
    return null;
  }
}

let cachedMascot: string | null = null;
function mascotDataUrl(): string | null {
  // Read the mascot once per server boot, embed as data URL. Avoids the
  // OG renderer having to hit our own domain at image-generation time.
  if (cachedMascot) return cachedMascot;
  try {
    const filePath = path.join(process.cwd(), "public", "pullist-mascot.png");
    const buf = readFileSync(filePath);
    cachedMascot = `data:image/png;base64,${buf.toString("base64")}`;
    return cachedMascot;
  } catch {
    return null;
  }
}

function fmtValue(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1000) return `$${Math.round(v).toLocaleString("en-US")}`;
  return `$${v.toFixed(2)}`;
}

export default async function PortfolioOG({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const data = await fetchPublic(token);
  const mascot = mascotDataUrl();

  // Fallback card when the portfolio is missing or revoked — still
  // useful so the link doesn't unfurl as a blank thumbnail.
  if (!data) {
    return new ImageResponse(
      (
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            background:
              "linear-gradient(135deg, #FFF8E1 0%, #FFFFFF 50%, #E0F2F1 100%)",
            fontFamily: "system-ui",
          }}
        >
          <div style={{ fontSize: 56, fontWeight: 800, color: "#1F2937" }}>
            PullList
          </div>
          <div
            style={{
              fontSize: 24,
              color: "#6B7280",
              marginTop: 12,
              display: "flex",
            }}
          >
            Portfolio not available
          </div>
        </div>
      ),
      size,
    );
  }

  const valueLabel = fmtValue(data.estimated_value_usd);
  const valueIsPublic = data.estimated_value_usd != null;
  const sub = `${data.unique_cards.toLocaleString("en-US")} cards · ${data.sets_touched} sets touched`;

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          background:
            "linear-gradient(135deg, #FFFBEB 0%, #FFFFFF 45%, #ECFEFF 100%)",
          fontFamily: "system-ui",
          padding: "60px 72px",
          position: "relative",
        }}
      >
        {/* Top row — mascot + brand wordmark */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 36,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 18,
            }}
          >
            {mascot ? (
              <img
                src={mascot}
                width={84}
                height={84}
                style={{
                  borderRadius: 999,
                  background: "rgba(255, 203, 5, 0.15)",
                  padding: 6,
                }}
                alt=""
              />
            ) : null}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                lineHeight: 1,
              }}
            >
              <div
                style={{
                  fontSize: 14,
                  fontWeight: 700,
                  letterSpacing: 4,
                  textTransform: "uppercase",
                  color: "#9CA3AF",
                }}
              >
                Public Vault
              </div>
              <div
                style={{
                  fontSize: 36,
                  fontWeight: 900,
                  color: "#FFCB05",
                  marginTop: 6,
                }}
              >
                PullList
              </div>
            </div>
          </div>
          <div
            style={{
              fontSize: 18,
              color: "#9CA3AF",
              fontFamily: "monospace",
            }}
          >
            pulllist.org
          </div>
        </div>

        {/* Display name */}
        <div
          style={{
            fontSize: 76,
            fontWeight: 900,
            color: "#111827",
            lineHeight: 1.05,
            letterSpacing: -1,
            marginBottom: 18,
            display: "flex",
            flexWrap: "wrap",
          }}
        >
          {data.display_name}
          <span style={{ color: "#9CA3AF", fontWeight: 700 }}>
            &nbsp;· vault
          </span>
        </div>

        {/* Bio (optional, truncated) */}
        {data.bio ? (
          <div
            style={{
              fontSize: 24,
              color: "#4B5563",
              lineHeight: 1.4,
              marginBottom: 28,
              maxWidth: 950,
              display: "-webkit-box",
              overflow: "hidden",
            }}
          >
            {data.bio.length > 110 ? data.bio.slice(0, 107) + "…" : data.bio}
          </div>
        ) : null}

        {/* Spacer */}
        <div style={{ flex: 1, display: "flex" }} />

        {/* Headline value + stats row */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            justifyContent: "space-between",
            gap: 32,
          }}
        >
          <div style={{ display: "flex", flexDirection: "column" }}>
            <div
              style={{
                fontSize: 12,
                fontWeight: 700,
                letterSpacing: 4,
                textTransform: "uppercase",
                color: "#9CA3AF",
                marginBottom: 8,
              }}
            >
              {valueIsPublic ? "Portfolio Value" : "Portfolio Value"}
            </div>
            <div
              style={{
                fontSize: 120,
                fontWeight: 900,
                lineHeight: 1,
                color: valueIsPublic ? "#F59E0B" : "#9CA3AF",
                letterSpacing: -3,
                fontFamily: "monospace",
              }}
            >
              {valueIsPublic ? valueLabel : "Private"}
            </div>
          </div>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "flex-end",
              gap: 10,
            }}
          >
            <div
              style={{
                fontSize: 26,
                fontWeight: 600,
                color: "#374151",
                fontFamily: "monospace",
                display: "flex",
              }}
            >
              {sub}
            </div>
            <div
              style={{
                fontSize: 16,
                color: "#9CA3AF",
                display: "flex",
              }}
            >
              Tracking every pull · catalog + collection + charts
            </div>
          </div>
        </div>

        {/* Brand stripe at very bottom */}
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            height: 8,
            background:
              "linear-gradient(90deg, #FFCB05 0%, #F59E0B 35%, #5BC9C2 100%)",
            display: "flex",
          }}
        />
      </div>
    ),
    size,
  );
}
