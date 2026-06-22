import { Mail, MessageSquare, Shield } from "lucide-react";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Contact · PullList",
  description:
    "How to reach the PullList team for support, privacy questions, partnership inquiries, or bug reports.",
};

export default function ContactPage() {
  return (
    <main className="max-w-3xl mx-auto px-4 py-12">
      <header className="mb-10">
        <p className="font-mono text-xs uppercase tracking-widest text-text-tertiary">
          Get in touch
        </p>
        <h1 className="mt-1 text-4xl font-extrabold tracking-tight text-text-primary">
          Contact
        </h1>
        <p className="mt-3 text-sm text-text-secondary leading-relaxed max-w-xl">
          PullList is built by a small team. The fastest way to reach us is
          email — pick the address that matches what you need below and we
          will get back to you within a couple of days.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 mb-10">
        <Card
          icon={<MessageSquare className="h-5 w-5 text-accent-yellow" />}
          title="General questions"
          email="hello@pulllist.org"
          body="Feature requests, bug reports, missing cards, or anything you can't find elsewhere on the site."
        />
        <Card
          icon={<Shield className="h-5 w-5 text-teal-400" />}
          title="Privacy & data"
          email="hello@pulllist.org"
          body="Request your data, ask for deletion, or report a privacy concern. We respond to GDPR / CCPA / personal-data requests here."
        />
        <Card
          icon={<Mail className="h-5 w-5 text-accent-green" />}
          title="Partnerships"
          email="hello@pulllist.org"
          body="Affiliate inquiries, integrations, content collaborations, or anything commercial."
        />
        <Card
          icon={<Mail className="h-5 w-5 text-accent-red" />}
          title="Legal & DMCA"
          email="hello@pulllist.org"
          body="Copyright or trademark concerns. Include the URL of the page in question and a description of the issue — we'll review and respond within 48 hours."
        />
      </div>

      <section className="rounded-card border border-border bg-bg-surface p-6 text-sm text-text-secondary leading-relaxed">
        <h2 className="text-lg font-bold text-text-primary mb-2">
          About this site
        </h2>
        <p>
          PullList is an independent Pokémon TCG catalog and collection
          tracker. We are not affiliated with Nintendo, The Pokémon Company,
          Creatures Inc., GAME FREAK Inc., TCGplayer, or eBay. Card images
          and names are property of their respective owners and used here
          under fair-use / nominative-use principles for the purpose of
          identification and price tracking.
        </p>
        <p className="mt-3">
          See our{" "}
          <a href="/about" className="text-teal-500 underline">
            About
          </a>{" "}
          page for more on the project, the{" "}
          <a href="/privacy" className="text-teal-500 underline">
            Privacy Policy
          </a>{" "}
          for data handling, and the{" "}
          <a href="/terms" className="text-teal-500 underline">
            Terms
          </a>{" "}
          for service conditions.
        </p>
      </section>
    </main>
  );
}

function Card({
  icon,
  title,
  email,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  email: string;
  body: string;
}) {
  return (
    <div className="rounded-card border border-border bg-bg-surface p-5">
      <div className="flex items-center gap-2 mb-2">
        <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-bg">
          {icon}
        </span>
        <h2 className="text-sm font-bold text-text-primary">{title}</h2>
      </div>
      <p className="text-xs text-text-secondary leading-relaxed">{body}</p>
      <a
        href={`mailto:${email}`}
        className="mt-3 inline-flex items-center gap-1.5 text-sm font-mono text-teal-500 hover:text-teal-400"
      >
        {email}
      </a>
    </div>
  );
}
