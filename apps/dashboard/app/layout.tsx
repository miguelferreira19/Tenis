import type { Metadata } from "next";
import "./globals.css";
import { Shell } from "../components/Shell";
import { BASE } from "../lib/api";

export const metadata: Metadata = {
  title: "Tennis Quant | Apostas de hoje",
  description: "Piloto automático de apostas de ténis na Betclic: quais, quanto e resultados, com banca gerida por regras.",
  icons: { icon: `${BASE}/favicon.svg` },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-PT">
      <body><Shell>{children}</Shell></body>
    </html>
  );
}

