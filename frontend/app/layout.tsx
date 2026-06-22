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
};

export const metadata: Metadata = {
  title: "PullList — Pokémon TCG catalog & collection tracker",
  description:
    "Track every Pokémon TCG pull. Live prices, daily history, instant scanning, every set indexed.",
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
      <body className="bg-bg text-text-primary min-h-screen">
        <ThemeProvider>
          <AuthProvider>
            <CollectionProvider>
              <WishlistProvider>
                <PWARegister />
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
