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
