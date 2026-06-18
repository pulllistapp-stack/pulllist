import Link from "next/link";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy · PullList",
  description:
    "What PullList collects, why, who we share it with, and how you can delete it.",
};

export default function PrivacyPage() {
  return (
    <main className="max-w-3xl mx-auto px-4 py-12 prose-pl">
      <header className="mb-8">
        <p className="font-mono text-xs uppercase tracking-widest text-text-tertiary">
          Legal
        </p>
        <h1 className="mt-1 text-4xl font-extrabold tracking-tight text-text-primary">
          Privacy Policy
        </h1>
        <p className="mt-2 text-sm text-text-tertiary">
          Last updated: 2026-06-18
        </p>
      </header>

      <div className="space-y-8 text-sm text-text-secondary leading-relaxed">
        <Section title="What we collect">
          <p>When you create an account, we collect:</p>
          <ul className="list-disc pl-5 mt-2 space-y-1">
            <li>
              <strong className="text-text-primary">Email address</strong> — to
              identify you and let you sign in.
            </li>
            <li>
              <strong className="text-text-primary">Display name and avatar</strong>{" "}
              — optional, populated automatically if you sign in with Google.
            </li>
            <li>
              <strong className="text-text-primary">Google account id</strong>{" "}
              (only if you sign in with Google) — to recognize you across
              sessions. We do not receive your Google password.
            </li>
            <li>
              <strong className="text-text-primary">Password hash</strong>{" "}
              (only if you sign up with email/password) — bcrypt hashed, never
              the plaintext.
            </li>
          </ul>
          <p className="mt-3">When you use the product, we store:</p>
          <ul className="list-disc pl-5 mt-2 space-y-1">
            <li>Your collection entries, wishlist, and any notes you add.</li>
            <li>
              Daily snapshots of your portfolio value (for the growth chart).
            </li>
            <li>Sharing preferences and your share token.</li>
          </ul>
        </Section>

        <Section title="What we do NOT collect">
          <ul className="list-disc pl-5 space-y-1">
            <li>Payment information — PullList is free.</li>
            <li>Phone number or postal address.</li>
            <li>
              Anything Google didn&apos;t hand us in the OAuth scopes
              <code className="font-mono text-xs bg-bg-surface border border-border rounded px-1 mx-1">
                openid email profile
              </code>
              .
            </li>
            <li>
              Your behavior outside PullList. We don&apos;t set tracking
              pixels on the open web.
            </li>
          </ul>
        </Section>

        <Section title="How we use your data">
          <ul className="list-disc pl-5 space-y-1">
            <li>Show you your collection, wishlist, and portfolio value.</li>
            <li>
              Render public portfolios (only if you turn sharing on, only
              under your share token URL).
            </li>
            <li>Send you transactional emails like password resets.</li>
            <li>
              Aggregate, anonymized analytics on which features get used (no
              personal identifiers).
            </li>
          </ul>
          <p className="mt-3">
            We do not sell your data. We do not share it with advertisers.
          </p>
        </Section>

        <Section title="Affiliate links">
          <p>
            Outbound links to TCGplayer and eBay are tagged with our affiliate
            ids. When you buy through them we get a small commission. These
            tags are anonymous - the retailer does not learn anything about
            you from us beyond that you clicked an affiliate link from
            pulllist.org.
          </p>
        </Section>

        <Section title="Who we share data with">
          <ul className="list-disc pl-5 space-y-1">
            <li>
              <strong className="text-text-primary">Neon</strong> (Postgres
              hosting, USA)
            </li>
            <li>
              <strong className="text-text-primary">Render</strong> (backend
              hosting, USA)
            </li>
            <li>
              <strong className="text-text-primary">Vercel</strong> (frontend
              hosting, USA)
            </li>
            <li>
              <strong className="text-text-primary">Google</strong> (only if
              you sign in with Google)
            </li>
          </ul>
          <p className="mt-3">
            All four are bound to keep your data secure and use it only to
            provide infrastructure for PullList.
          </p>
        </Section>

        <Section title="Your rights">
          <p>
            You can <strong className="text-text-primary">delete your account</strong> at any time from{" "}
            <Link href="/me/settings" className="text-teal-500 underline">
              Settings
            </Link>
            . This permanently removes your account, collection, wishlist,
            portfolio history, and any active share tokens. The action is
            irreversible and takes effect immediately.
          </p>
          <p className="mt-3">
            You can also request a copy of your data by emailing
            <a
              href="mailto:hello@pulllist.org"
              className="text-teal-500 underline ml-1"
            >
              hello@pulllist.org
            </a>
            .
          </p>
        </Section>

        <Section title="Cookies">
          <p>
            We use one first-party cookie called
            <code className="font-mono text-xs bg-bg-surface border border-border rounded px-1 mx-1">
              pulllist_token
            </code>
            to keep you signed in. No third-party tracking cookies.
          </p>
        </Section>

        <Section title="Children">
          <p>
            PullList is not directed at children under 13 (under 14 in
            Korea). If you believe a child has signed up, email us and we will
            delete the account.
          </p>
        </Section>

        <Section title="Contact">
          <p>
            Questions about privacy:{" "}
            <a
              href="mailto:hello@pulllist.org"
              className="text-teal-500 underline"
            >
              hello@pulllist.org
            </a>
          </p>
        </Section>
      </div>
    </main>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h2 className="text-lg font-bold text-text-primary mb-2">{title}</h2>
      {children}
    </section>
  );
}
