import type { Metadata } from "next";
import "./globals.css";
import { Shell } from "../components/Shell";

export const metadata: Metadata = {
  title: "Tennis Quant | Terminal de investigação",
  description: "Probabilidades, preços justos e validação quantitativa de ténis com proveniência verificável.",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-PT">
      <body><Shell>{children}</Shell></body>
    </html>
  );
}

