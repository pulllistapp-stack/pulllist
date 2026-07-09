import Link from "next/link";

export const metadata = {
  title: "Legal · PullList",
  description:
    "Affiliate disclosure, data attributions, and trademark notice for PullList.",
};

/**
 * All the long-form disclosure text that used to live in the site
 * footer. Keeping this on its own page (linked from the footer + About)
 * satisfies the FTC's "clear and conspicuous" requirement for affiliate
 * disclosure and the attribution obligations for the CC-licensed data
 * we consume, without making every page footer a wall of small print.
 */
export default function LegalPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-14">
      <nav className="mb-6 text-sm text-text-secondary">
        <Link href="/" className="hover:text-text-primary">
          Home
        </Link>
        <span className="mx-2 text-text-tertiary">/</span>
        <span className="text-text-primary">Legal &amp; attributions</span>
      </nav>

      <h1 className="text-3xl font-extrabold tracking-tight mb-3">
        Legal &amp; attributions
      </h1>
      <p className="text-sm text-text-secondary mb-10">
        The disclosures, credits, and trademark notice for PullList.
      </p>

      <section className="mb-10">
        <h2 className="text-lg font-bold mb-2">Affiliate disclosure</h2>
        <p className="text-sm text-text-secondary leading-relaxed">
          PullList participates in affiliate programs with{" "}
          <span className="font-medium text-text-primary">TCGplayer</span> and the{" "}
          <span className="font-medium text-text-primary">
            eBay Partner Network
          </span>
          . When you click an outbound &ldquo;Buy&rdquo; or listing link on our
          site and complete a qualifying purchase, we may earn a small commission
          at no extra cost to you. Affiliate links carry an{" "}
          <span className="rounded bg-bg-surface border border-border px-1 font-mono text-[10px]">
            Ad
          </span>{" "}
          tag wherever they appear inline so you can see them at a glance.
        </p>
      </section>

      <section className="mb-10">
        <h2 className="text-lg font-bold mb-2">Data attributions</h2>
        <ul className="text-sm text-text-secondary leading-relaxed space-y-2 list-disc pl-5">
          <li>
            Card metadata (EN) — {" "}
            <a
              href="https://pokemontcg.io"
              target="_blank"
              rel="noopener noreferrer"
              className="text-text-primary underline decoration-dotted"
            >
              pokemontcg.io
            </a>{" "}
            under{" "}
            <a
              href="https://creativecommons.org/licenses/by/4.0/"
              target="_blank"
              rel="noopener noreferrer"
              className="underline decoration-dotted"
            >
              CC BY 4.0
            </a>
            .
          </li>
          <li>
            JP catalog — {" "}
            <a
              href="https://tcgdex.dev"
              target="_blank"
              rel="noopener noreferrer"
              className="text-text-primary underline decoration-dotted"
            >
              TCGdex
            </a>{" "}
            (MIT) and{" "}
            <a
              href="https://limitlesstcg.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-text-primary underline decoration-dotted"
            >
              Limitless TCG
            </a>
            .
          </li>
          <li>
            JP set logos and select vintage card scans — {" "}
            <a
              href="https://archives.bulbagarden.net"
              target="_blank"
              rel="noopener noreferrer"
              className="text-text-primary underline decoration-dotted"
            >
              Bulbagarden Archives / Bulbapedia
            </a>{" "}
            under{" "}
            <a
              href="https://creativecommons.org/licenses/by-nc-sa/2.5/"
              target="_blank"
              rel="noopener noreferrer"
              className="underline decoration-dotted"
            >
              CC BY-NC-SA 2.5
            </a>
            .
          </li>
          <li>
            Live pricing signals — TCGplayer and eBay APIs, refreshed on our
            own schedule.
          </li>
        </ul>
      </section>

      <section className="mb-10">
        <h2 className="text-lg font-bold mb-2">Trademarks</h2>
        <p className="text-sm text-text-secondary leading-relaxed">
          Pokémon and all related characters, names, and logos are trademarks of{" "}
          <span className="text-text-primary">Nintendo</span>,{" "}
          <span className="text-text-primary">Creatures Inc.</span>,{" "}
          <span className="text-text-primary">GAME FREAK inc.</span>, and{" "}
          <span className="text-text-primary">
            The Pokémon Company International
          </span>
          . Wizards of the Coast owns the trademarks on older Pokémon TCG sets.
          PullList is a fan-built collection tracker — unaffiliated with, not
          endorsed by, and not sponsored by any of these companies.
        </p>
      </section>

      <section className="mb-10">
        <h2 className="text-lg font-bold mb-2">User-uploaded content</h2>
        <p className="text-sm text-text-secondary leading-relaxed mb-3">
          Some PullList features (currently: master-set binder covers) let you
          upload images. By uploading, you represent that you own or have
          permission to use the image, and you grant PullList a limited right
          to display it back to you and to anyone with whom you share a link
          to your master set.
        </p>
        <p className="text-sm text-text-secondary leading-relaxed">
          Please don&apos;t upload copyrighted artwork you don&apos;t have
          rights to. If you&apos;re unsure, use one of your own photos or the
          default mascot cover.
        </p>
      </section>

      <section className="mb-10">
        <h2 className="text-lg font-bold mb-2">DMCA / takedown</h2>
        <p className="text-sm text-text-secondary leading-relaxed mb-3">
          If you believe content on PullList (including a user-uploaded binder
          cover) infringes your copyright, send a takedown notice to{" "}
          <a
            href="mailto:takedown@pulllist.app"
            className="text-text-primary underline decoration-dotted"
          >
            takedown@pulllist.app
          </a>{" "}
          with:
        </p>
        <ul className="text-sm text-text-secondary leading-relaxed space-y-1 list-disc pl-5">
          <li>Your contact information (name, email, phone).</li>
          <li>A description of the copyrighted work.</li>
          <li>
            The URL(s) on PullList where the infringing content appears.
          </li>
          <li>
            A statement, under penalty of perjury, that you have a good-faith
            belief the use is unauthorized and that the information in the
            notice is accurate.
          </li>
          <li>Your physical or electronic signature.</li>
        </ul>
        <p className="mt-3 text-sm text-text-secondary leading-relaxed">
          We remove or disable access to reported content promptly on receipt
          of a complete notice and, where appropriate, forward the notice to
          the user who uploaded it.
        </p>
      </section>

      <section>
        <h2 className="text-lg font-bold mb-2">Copyright</h2>
        <p className="text-sm text-text-secondary leading-relaxed">
          © {new Date().getFullYear()} PullList. Our own site design, code,
          and editorial content are ours; third-party card images, set logos,
          and price data belong to their respective owners as listed above.
        </p>
      </section>
    </main>
  );
}
