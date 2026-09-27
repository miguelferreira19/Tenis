import type { Metadata } from "next";
import "./globals.css";
import { Shell } from "../components/Shell";

export const metadata: Metadata = {
  title: "Tennis Quant | Assistente de análise de ténis",
  description: "Jogos atuais, probabilidades exploratórias, resultados recentes e fontes verificáveis.",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-PT">
      <body><Shell>{children}</Shell></body>
    </html>
  );
}

