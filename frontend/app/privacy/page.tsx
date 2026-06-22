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
          Last updated: 2026-06-21
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
              First-party tracking pixels on the open web outside PullList.
              (Third-party ad networks may still set their own cookies on
              your browser while you visit our pages — see the Advertising
              section below.)
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
            We do not sell your account data (email, collection contents,
            wishlist, etc.). Third-party advertisers do load on our pages
            and use their own cookies — see the Advertising section for
            details on what they do and how to opt out.
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

        <Section title="Advertising (Google AdSense)">
          <p>
            PullList shows advertisements served by Google AdSense and its
            partner ad networks. To make ads work, third-party vendors
            including Google use cookies to:
          </p>
          <ul className="list-disc pl-5 mt-2 space-y-1">
            <li>
              Serve ads based on your prior visits to this site or other
              sites on the internet.
            </li>
            <li>
              Measure ad performance (impressions, clicks).
            </li>
            <li>
              Detect fraud and abuse (invalid clicks, bot traffic).
            </li>
          </ul>
          <p className="mt-3">
            You can opt out of personalized advertising by visiting{" "}
            <a
              href="https://www.google.com/settings/ads"
              target="_blank"
              rel="noopener noreferrer"
              className="text-teal-500 underline"
            >
              Google Ads Settings
            </a>
            . You can opt out of third-party vendor cookies more broadly at{" "}
            <a
              href="https://www.aboutads.info/choices/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-teal-500 underline"
            >
              aboutads.info/choices
            </a>{" "}
            (US) or{" "}
            <a
              href="https://www.youronlinechoices.eu/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-teal-500 underline"
            >
              youronlinechoices.eu
            </a>{" "}
            (EU). Disabling cookies in your browser also blocks ad
            personalization; the ads themselves will still appear but they
            will be untargeted.
          </p>
          <p className="mt-3">
            For Google&apos;s own data handling, see the{" "}
            <a
              href="https://policies.google.com/technologies/ads"
              target="_blank"
              rel="noopener noreferrer"
              className="text-teal-500 underline"
            >
              Google Advertising Privacy Notice
            </a>
            .
          </p>
        </Section>

        <Section title="Who we share data with">
          <p className="mb-2">
            We rely on the following third-party processors. Naming them
            here is required under GDPR Art. 13 / CCPA / Korea PIPA —
            you have a right to know where your data lives.
          </p>
          <ul className="list-disc pl-5 space-y-1">
            <li>
              <strong className="text-text-primary">Neon</strong> — Postgres
              database hosting (USA). Holds your account, collection, and
              wishlist.
            </li>
            <li>
              <strong className="text-text-primary">Render</strong> — backend
              API hosting (USA). Processes requests; does not store account
              data beyond runtime.
            </li>
            <li>
              <strong className="text-text-primary">Vercel</strong> —
              frontend hosting + edge CDN (USA). Serves the site.
            </li>
            <li>
              <strong className="text-text-primary">Google (Sign-In)</strong>{" "}
              — only if you sign in with Google. Receives your sign-in
              event but not your collection.
            </li>
            <li>
              <strong className="text-text-primary">Google (AdSense)</strong>{" "}
              — serves advertisements on our pages. Uses cookies for ad
              personalization, measurement, and fraud detection. See the
              Advertising section above for opt-out links.
            </li>
            <li>
              <strong className="text-text-primary">Impact (TCGplayer)</strong>{" "}
              + <strong className="text-text-primary">eBay Partner Network</strong>{" "}
              — affiliate referral tracking. Sees only that you clicked
              from pulllist.org, not your account info.
            </li>
          </ul>
          <p className="mt-3">
            Each of these is bound by their own terms to keep data secure
            and to use it only to provide their service to PullList. We do
            not share your account email or collection contents with
            anyone outside this list.
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
          <p>We use:</p>
          <ul className="list-disc pl-5 mt-2 space-y-1">
            <li>
              <strong className="text-text-primary">First-party</strong> —
              one cookie called{" "}
              <code className="font-mono text-xs bg-bg-surface border border-border rounded px-1 mx-1">
                pulllist_token
              </code>
              to keep you signed in.
            </li>
            <li>
              <strong className="text-text-primary">Third-party (advertising)</strong>{" "}
              — Google AdSense and its partner networks set cookies to
              serve and measure ads. Details and opt-out links are in the
              Advertising section above.
            </li>
          </ul>
          <p className="mt-3">
            You can disable cookies in your browser settings. PullList&apos;s
            account features (sign-in, collection) will stop working without
            the first-party cookie; ads will still appear but will not be
            personalized.
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
