import type { Metadata, Viewport } from "next";
import { DM_Sans, JetBrains_Mono } from "next/font/google";

import { AuthProvider } from "@/components/AuthProvider";
import { CollectionProvider } from "@/components/CollectionProvider";
import { CookieBanner } from "@/components/CookieBanner";
import { Footer } from "@/components/Footer";
import { PWARegister } from "@/components/PWARegister";
import { ScanFAB } from "@/components/ScanFAB";
import { ThemeProvider } from "@/components/theme-provider";
import { TopNav } from "@/components/TopNav";
import { TrackVisit } from "@/components/TrackVisit";
import { WishlistProvider } from "@/components/WishlistProvider";

import "./globals.css";

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
});
const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#FFFFFF" },
    { media: "(prefers-color-scheme: dark)", color: "#0B0E14" },
  ],
  width: "device-width",
  initialScale: 1,
  // Don't let pinch-zoom break our scan/camera UX, but keep accessibility:
  // maximumScale 5 lets users still zoom for low-vision needs.
  maximumScale: 5,
  // Extend the layout under the notch / dynamic island / rounded corners
  // in standalone PWA + iOS Safari. Every sticky/fixed element then reads
  // env(safe-area-inset-*) so the actual content stays clear.
  viewportFit: "cover",
};

export const metadata: Metadata = {
  metadataBase: new URL("https://www.pulllist.org"),
  title: {
    default: "PullList — Real Pokémon TCG Sold Prices & Collection Tracker",
    template: "%s | PullList",
  },
  description:
    "Real sold-listing PSA / CGC / BGS / TAG prices for every Pokémon TCG card. Live eBay + TCGplayer + Cardmarket, sealed EV, daily history, EN/JP/KR catalogs.",
  keywords: [
    "Pokemon TCG prices",
    "Pokemon card sold prices",
    "PSA 10 Pokemon",
    "Pokemon card tracker",
    "Pokemon TCG collection",
    "sealed booster box EV",
    "Prismatic Evolutions prices",
    "포켓몬 TCG 시세",
  ],
  manifest: "/manifest.json",
  applicationName: "PullList",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "PullList",
  },
  icons: {
    icon: "/pullist-mascot-logo.png",
    apple: "/pullist-mascot-logo.png",
    shortcut: "/pullist-mascot-logo.png",
  },
  formatDetection: {
    telephone: false,
  },
  // Site-wide OpenGraph + Twitter defaults. Per-page metadata (card, set,
  // series, product) overrides these — root defaults show up on any
  // route without its own generateMetadata (home, /trending, /drops, ...).
  openGraph: {
    type: "website",
    siteName: "PullList",
    url: "https://www.pulllist.org",
    title: "PullList — Real Pokémon TCG Sold Prices & Collection Tracker",
    description:
      "Real sold-listing prices for every Pokémon TCG card. PSA / CGC / BGS / TAG, live eBay + TCGplayer, sealed EV, EN/JP/KR catalogs.",
    images: [{ url: "/pullist-mascot-logo.png", alt: "PullList mascot" }],
  },
  twitter: {
    card: "summary_large_image",
    site: "@pulllist",
    title: "PullList — Real Pokémon TCG Sold Prices & Collection Tracker",
    description:
      "Real sold PSA/CGC/BGS/TAG prices, live eBay + TCGplayer, sealed EV, EN/JP/KR — free.",
    images: ["/pullist-mascot-logo.png"],
  },
  other: {
    // impact.com (TCGplayer affiliate program) website ownership verification.
    "impact-site-verification": "f3270a02-b50f-4be8-9ed2-c533176807cf",
    // Hint to iOS that the mascot icon is a regular touch icon (no auto-gloss).
    "apple-mobile-web-app-capable": "yes",
    "mobile-web-app-capable": "yes",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${dmSans.variable} ${jetbrainsMono.variable}`}
    >
      <head>
        {/* Google AdSense — raw <script> rather than next/script so the
            tag lands in the initial server-rendered HTML. AdSense's
            verification crawler reads raw HTML and doesn't execute JS,
            so next/script's afterInteractive injection happened too late
            and failed the ownership check. async keeps it from blocking. */}
        <script
          async
          src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-9440218369165896"
          crossOrigin="anonymous"
        ></script>
      </head>
      <body className="bg-bg text-text-primary min-h-[100dvh]">
        <ThemeProvider>
          <AuthProvider>
            <CollectionProvider>
              <WishlistProvider>
                <PWARegister />
                <TrackVisit />
                <TopNav />
                {children}
                <Footer />
                <ScanFAB />
                <CookieBanner />
              </WishlistProvider>
            </CollectionProvider>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
