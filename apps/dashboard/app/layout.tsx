import type { Metadata } from "next";
import "./globals.css";
import { Shell } from "../components/Shell";
import { BASE } from "../lib/api";

export const metadata: Metadata = {
  title: "Tennis Quant | Plano de múltiplas",
  description: "Múltiplas curtas de favoritos de ténis na Betclic: que jogos, quanto apostar e que futuro esperar, com previsões baseadas em histórico.",
  icons: { icon: `${BASE}/favicon.svg` },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-PT">
      <body><Shell>{children}</Shell></body>
    </html>
  );
}

