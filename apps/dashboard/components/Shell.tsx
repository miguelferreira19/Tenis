"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";
import { STATIC } from "../lib/api";

const nav = [
  { href: "/hoje", label: "Próximos jogos", icon: "◷", group: "ATUALIDADE" },
  { href: "/recentes", label: "Resultados recentes", icon: "◈", group: "ATUALIDADE" },
  { href: "/combinadas", label: "Combinadas", icon: "⊞", group: "ATUALIDADE" },
  { href: "/resumo", label: "Visão geral", icon: "◫", group: "INVESTIGAÇÃO", archive: true },
  { href: "/jogos", label: "Arquivo histórico", icon: "◈", group: "INVESTIGAÇÃO", archive: true },
  { href: "/modelos", label: "Modelos e validação", icon: "▥", group: "INVESTIGAÇÃO" },
  { href: "/backtests", label: "Backtests", icon: "▤", group: "INVESTIGAÇÃO" },
  { href: "/mercados", label: "Mercados e odds", icon: "⌁", group: "INVESTIGAÇÃO" },
  { href: "/dados", label: "Dados e fontes", icon: "▤", group: "INVESTIGAÇÃO" },
].filter(item => !(STATIC && item.archive)); // o arquivo precisa da API Python: só em local

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname().replace(/\/$/, "") || "/"; // trailingSlash no site estático
  return <div className="app-shell">
    <aside className="sidebar">
      <Link href="/" className="brand" aria-label="Tennis Quant, início">
        <span className="brand-mark"><span className="ball" /></span>
        <span><strong>TENNIS<br/>QUANT</strong><small>RESEARCH TERMINAL</small></span>
      </Link>
      <nav aria-label="Navegação principal">
        {nav.map((item, index) => <div key={item.href} className="nav-item-wrap">{(index === 0 || nav[index - 1].group !== item.group) && <div className="sidebar-section">{item.group}</div>}<Link href={item.href}
          className={`nav-link ${pathname === item.href || (item.href === "/jogos" && pathname.startsWith("/jogos/")) ? "active" : ""}`}>
          <span className="nav-icon" aria-hidden>{item.icon}</span>{item.label}<span className="nav-arrow">↗</span>
        </Link></div>)}
      </nav>
      <div className="sidebar-bottom">
        <div className="status-lamp"><i/> AMBIENTE DE INVESTIGAÇÃO</div>
        <p>Probabilidades auditáveis.<br/>Sem sinais aprovados para aposta.</p>
        <span className="version">TQ / V0.3</span>
      </div>
    </aside>
    <div className="main-wrap">
      <header className="topbar"><div><span className="topbar-label">TENNIS / QUANTITATIVE INTELLIGENCE</span><span className="topbar-mobile">TENNIS QUANT</span></div><div className="topbar-right"><span className="topbar-dot"/> INVESTIGAÇÃO <span className="topbar-sep">/</span> PT-PT</div></header>
      <main className="main-content">{children}</main>
    </div>
  </div>;
}

