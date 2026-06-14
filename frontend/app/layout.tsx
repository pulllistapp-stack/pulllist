import type { Metadata } from "next";
import { DM_Sans, JetBrains_Mono } from "next/font/google";

import { AuthProvider } from "@/components/AuthProvider";
import { CollectionProvider } from "@/components/CollectionProvider";
import { Footer } from "@/components/Footer";
import { ThemeProvider } from "@/components/theme-provider";
import { TopNav } from "@/components/TopNav";

import "./globals.css";

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
});
const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "PullList — Pokémon TCG catalog & collection tracker",
  description:
    "Find Pokémon TCG sealed product in stock near you, in real time. Catalog every card, every set, every restock.",
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
      <body className="bg-bg text-text-primary min-h-screen">
        <ThemeProvider>
          <AuthProvider>
            <CollectionProvider>
              <TopNav />
              {children}
              <Footer />
            </CollectionProvider>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
