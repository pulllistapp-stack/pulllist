import Link from "next/link";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Service · PullList",
  description: "The rules for using PullList.",
};

export default function TermsPage() {
  return (
    <main className="max-w-3xl mx-auto px-4 py-12">
      <header className="mb-8">
        <p className="font-mono text-xs uppercase tracking-widest text-text-tertiary">
          Legal
        </p>
        <h1 className="mt-1 text-4xl font-extrabold tracking-tight text-text-primary">
          Terms of Service
        </h1>
        <p className="mt-2 text-sm text-text-tertiary">
          Last updated: 2026-06-18
        </p>
      </header>

      <div className="space-y-8 text-sm text-text-secondary leading-relaxed">
        <Section title="The deal">
          <p>
            PullList is provided as-is, free of charge. By using the site you
            agree to these terms. If you don&apos;t agree, please don&apos;t
            use it.
          </p>
        </Section>

        <Section title="Your account">
          <ul className="list-disc pl-5 space-y-1">
            <li>One account per person. Bots and scrapers are not welcome.</li>
            <li>
              Don&apos;t share your account credentials. You&apos;re responsible for
              activity on your account.
            </li>
            <li>
              You can <Link href="/me/settings" className="text-teal-500 underline">delete your account</Link>{" "}
              any time. It&apos;s irreversible.
            </li>
          </ul>
        </Section>

        <Section title="What you can do">
          <ul className="list-disc pl-5 space-y-1">
            <li>Track your personal collection and wishlist.</li>
            <li>Share your portfolio publicly using your share token.</li>
            <li>Use the data for personal collecting decisions.</li>
            <li>
              Click outbound links to TCGplayer and eBay. We may earn a small
              commission - see{" "}
              <Link href="/privacy" className="text-teal-500 underline">
                Privacy
              </Link>
              .
            </li>
          </ul>
        </Section>

        <Section title="What you can't do">
          <ul className="list-disc pl-5 space-y-1">
            <li>
              Resell, redistribute, or republish the price/catalog data
              directly. The data is sourced from third parties (pokemontcg.io,
              TCGplayer, eBay, Cardmarket) under their own terms.
            </li>
            <li>
              Scrape the site or run automated requests against the API at a
              rate that affects others.
            </li>
            <li>
              Use PullList to do anything illegal or to harass other
              collectors.
            </li>
            <li>
              Frame PullList as your own product or remove our branding.
            </li>
          </ul>
        </Section>

        <Section title="Prices and accuracy">
          <p>
            Prices shown on PullList are pulled from third-party sources and
            cached. They are <strong className="text-text-primary">indicative, not authoritative</strong>.
            Don&apos;t make a transaction decision based solely on a number
            you saw here - check the source before you buy or sell.
          </p>
        </Section>

        <Section title="Pokémon trademarks">
          <p>
            Pokémon and all related characters, marks, and assets are
            trademarks of Nintendo / Creatures Inc. / GAME FREAK inc.
            PullList is unaffiliated with The Pokémon Company.
          </p>
        </Section>

        <Section title="Disclaimer of warranties">
          <p>
            The service is provided &quot;as is&quot;, without warranties of
            any kind. We don&apos;t guarantee uptime, accuracy of prices,
            availability of any specific feature, or that your data will
            never be lost. We do back up the database, but please keep your
            own copy of anything irreplaceable.
          </p>
        </Section>

        <Section title="Liability">
          <p>
            To the maximum extent permitted by law, PullList and its
            operators are not liable for any indirect, incidental,
            consequential, or special damages arising from your use of the
            site, including losses on Pokémon card transactions informed by
            prices shown here.
          </p>
        </Section>

        <Section title="Changes to these terms">
          <p>
            We may update these terms. Material changes will be flagged on
            the homepage and via email. Continuing to use the site after a
            change means you accept the new terms.
          </p>
        </Section>

        <Section title="Governing law">
          <p>
            These terms are governed by the laws of the Republic of Korea.
            Disputes go to the Seoul Central District Court.
          </p>
        </Section>

        <Section title="Contact">
          <p>
            Email:{" "}
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
