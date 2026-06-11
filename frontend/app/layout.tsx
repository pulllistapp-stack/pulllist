import type { Metadata } from "next";

import { AuthProvider } from "@/components/AuthProvider";
import { CollectionProvider } from "@/components/CollectionProvider";
import { TopNav } from "@/components/TopNav";

import "./globals.css";

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
    <html lang="en">
      <body className="bg-bg text-text-primary min-h-screen">
        <AuthProvider>
          <CollectionProvider>
            <TopNav />
            {children}
          </CollectionProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
