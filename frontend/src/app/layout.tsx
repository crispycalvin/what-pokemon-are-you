import type { Metadata } from "next";
import { Inter, Lilita_One } from "next/font/google";
import "./globals.css";

// Inter for body text — clean, readable, self-hosted
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

// Lilita One for the Pokémon-style hero title. Chunky, rounded letterforms
// that closely echo the official Pokémon logo lettering
const lilitaOne = Lilita_One({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-pokemon",
  display: "swap",
});

export const metadata: Metadata = {
  title: "What Pokémon Are You?",
  description:
    "Describe yourself and find the Pokémon whose Pokédex vibe is closest to yours, matched by semantic embeddings.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${lilitaOne.variable}`}>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
