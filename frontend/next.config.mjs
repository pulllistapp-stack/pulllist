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
      // Bulbapedia / Bulbagarden archives — JP set logos (CC-BY-NC-SA 2.5,
      // credit on /about). Used when TCGdex returns logo: null for a set,
      // which is every JP set as of import.
      { protocol: "https", hostname: "archives.bulbagarden.net" },
      // Limitless TCG card images — fills SwSh-era and select SV sets that
      // TCGdex's /ja API returns metadata-only for (S11a, S10b, SV5M, etc.).
      { protocol: "https", hostname: "limitlesstcg.nyc3.cdn.digitaloceanspaces.com" },
      { protocol: "https", hostname: "s3.limitlesstcg.com" },
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
};

export default nextConfig;
