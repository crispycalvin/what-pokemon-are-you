/** @type {import('next').NextConfig} */
const nextConfig = {
  // Pokémon sprites live on GitHub's raw CDN; whitelist for next/image.
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "raw.githubusercontent.com",
        pathname: "/PokeAPI/sprites/**",
      },
    ],
  },
};

export default nextConfig;
