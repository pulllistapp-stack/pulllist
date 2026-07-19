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
      // Second CloudFront distribution used by pokemon.com for set
      // logos and expansion marketing artwork (`/assets/img/global/
      // logos/en-us/thirty.png` etc.). Wired in for the 30th
      // Celebration (me30) set logo.
      { protocol: "https", hostname: "d1i787aglh9bmb.cloudfront.net" },
      // Shopify CDN — used for pre-release EN set logos we pull from
      // partner storefronts (e.g. the Pitch Black / me5 logo). Broad
      // hostname because Shopify serves every merchant off the same
      // subdomain with paths keyed by shop id.
      { protocol: "https", hostname: "cdn.shopify.com" },
      // Scrydex — hosts SV / MEV era set logos that neither pokemontcg.io
      // nor pokemon.com's CDN carry (Chaos Rising me4, Perfect Order me3,
      // Ascended Heroes me2pt5, etc.). SetCard renders these fine because
      // it uses <Image unoptimized>; the Master Set modal/detail also
      // needs the hostname allowlisted for the optimizer's ping-check.
      { protocol: "https", hostname: "images.scrydex.com" },
      // ─── KR set logo sources (2026-07-19) ────────────────────────
      // pokemonstore.co.kr official store CDN — hero product photos
      // captured by backfill_kr_logos_pokemonstore.py for the current-
      // stock SV/MEGA sets (~58 rows).
      { protocol: "https", hostname: "shopby-images.cdn-nhncommerce.com" },
      // Naver Smart Store seller uploads — biggest single source for
      // KR sets (~60) captured by backfill_kr_logos_naver.py. Two
      // hostname flavours ship the same tree.
      { protocol: "https", hostname: "shop1.phinf.naver.net" },
      { protocol: "https", hostname: "shop-phinf.pstatic.net" },
      // Naver blog + café attachments — user-uploaded product photos
      // for older SM/S/BW/XY-era sets the store no longer carries.
      { protocol: "https", hostname: "blogfiles.naver.net" },
      { protocol: "https", hostname: "cafefiles.naver.net" },
      // Kream — Naver-owned resale platform. Handful of KR chase-set
      // photos it indexes better than the Smart Store.
      { protocol: "https", hostname: "kream-phinf.pstatic.net" },
      // Coupang thumbnails — surface on Naver Image Search even
      // though the listing is on Coupang. Referer-agnostic.
      { protocol: "https", hostname: "thumbnail.coupangcdn.com" },
      // Namuwiki article thumbnails — LO hand-supplied a few (SV6
      // 변환의 가면 etc.). Path segments are opaque content hashes
      // so whole-hostname allowlist is the only viable pattern.
      { protocol: "https", hostname: "i.namu.wiki" },
      // collectory.cc CDN — pre-2016 KR set covers captured via
      // import_kr_from_collectory.py --include-new-sets.
      { protocol: "https", hostname: "cdn.collectory.cc" },
      // Long tail of smaller KR-market retailers whose SEO put a
      // set photo at the top of the search results for one or two
      // niche titles. Kept as an explicit allowlist so a future
      // rescrape can widen it deliberately rather than by accident.
      { protocol: "https", hostname: "image.g9.co.kr" },
      { protocol: "https", hostname: "tcgbox.co.kr" },
      { protocol: "https", hostname: "img.w-shopping.co.kr" },
      { protocol: "https", hostname: "i3.ruliweb.com" },
      { protocol: "https", hostname: "static.mercdn.net" },
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
