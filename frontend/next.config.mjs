/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "images.pokemontcg.io" },
      { protocol: "https", hostname: "tcg.pokemon.com" },
      // eBay listing thumbnails for the Live Listings panel
      { protocol: "https", hostname: "i.ebayimg.com" },
      { protocol: "https", hostname: "thumbs.ebaystatic.com" },
      // TCGdex hosts JP card + set asset images for the Japan catalog
      { protocol: "https", hostname: "assets.tcgdex.net" },
      // Google profile pictures for Sign-in-with-Google avatars
      { protocol: "https", hostname: "lh3.googleusercontent.com" },
      // Limitless TCG — JP set logos (s3.limitlesstcg.com) and card images
      // (limitlesstcg.nyc3.cdn). Fills SwSh-era and select SV sets that
      // TCGdex's /ja API returns metadata-only for, plus all JP set logos
      // that TCGdex returns null for.
      { protocol: "https", hostname: "limitlesstcg.nyc3.cdn.digitaloceanspaces.com" },
      { protocol: "https", hostname: "s3.limitlesstcg.com" },
      // pokemon.com static CDN — promo/collection cards that neither
      // pokemontcg.io nor Limitless index (e.g. First Partner Illustration
      // Collection). weserv can't proxy these (blocked by policy), so
      // next/image fetches them server-side directly. Both hostnames serve
      // the same /static-assets/ tree; whitelist both so seed scripts can
      // standardise on either.
      { protocol: "https", hostname: "www.pokemon.com" },
      { protocol: "https", hostname: "assets.pokemon.com" },
      // TCGplayer CDN — promo / supplemental cards seeded via TCGCSV's
      // /tcgplayer/3/{group}/products feed (see seed_promo_group.py).
      // Used for MEP "ME: Mega Evolution Promo" and other promo sets
      // pokemontcg.io doesn't index.
      { protocol: "https", hostname: "tcgplayer-cdn.tcgplayer.com" },
      // Bulbapedia archives — JP vintage card scans for Base Set /
      // Jungle / Fossil / Team Rocket / Gym Heroes / Gym Challenge /
      // Expedition (PMCG1-6, E1) plus JP-only sets VS1 and web1.
      // See backfill_jp_images_bulbapedia.py.
      { protocol: "https", hostname: "archives.bulbagarden.net" },
      // learn-book.com — JP PCG1-9 vintage card images (Holon Research
      // Tower 2004 through Battle at Furthest Ends 2006).
      // See backfill_jp_images_learnbook.py.
      { protocol: "https", hostname: "learn-book.com" },
      // nazonobasho.com — JP e-Card era native scans (E1-E5, 2001-2002).
      // See backfill_jp_images_nazonobasho.py.
      { protocol: "https", hostname: "nazonobasho.com" },
      // images.weserv.nl — public image proxy used to bypass Bulbapedia
      // archives' hot-link protection (they 403 requests with a Referer
      // outside bulbagarden). Applied to JPP-U* Unnumbered Promo images
      // (see import_bulbapedia_unnumbered_jp.py); harmless for other
      // sources that don't need it.
      { protocol: "https", hostname: "images.weserv.nl" },
      // The Pokémon Company's CloudFront CDN — hosts pre-release card
      // images for upcoming EN expansions before TCGCSV /
      // pokemontcg.io / Limitless index them. Used to seed Pitch Black
      // (me5) skeleton pre-launch (see seed_pitchblack_skeleton.py).
      { protocol: "https", hostname: "dz3we2x72f7ol.cloudfront.net" },
    ],
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
  async redirects() {
    return [
      // /me/collection used to be a near-duplicate of /portfolio (same
      // stat cards + vault-by-set listing). Merged into /portfolio; this
      // keeps old bookmarks and inbound links working.
      {
        source: "/me/collection",
        destination: "/portfolio",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
