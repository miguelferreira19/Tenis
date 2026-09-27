"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

const nav = [
  { href: "/", label: "Visão geral", icon: "◫" },
  { href: "/jogos", label: "Jogos", icon: "◈" },
  { href: "/mercados", label: "Mercados", icon: "⌁" },
  { href: "/modelos", label: "Modelos", icon: "▥" },
  { href: "/dados", label: "Dados e fontes", icon: "▤" },
];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return <div className="app-shell">
    <aside className="sidebar">
      <Link href="/" className="brand" aria-label="Tennis Quant, início">
        <span className="brand-mark"><span className="ball" /></span>
        <span><strong>TENNIS<br/>QUANT</strong><small>RESEARCH TERMINAL</small></span>
      </Link>
      <div className="sidebar-section">WORKSPACE <span>01 / TÉNIS</span></div>
      <nav aria-label="Navegação principal">
        {nav.map(item => <Link key={item.href} href={item.href}
          className={`nav-link ${pathname === item.href || (item.href === "/jogos" && pathname.startsWith("/jogos/")) ? "active" : ""}`}>
          <span className="nav-icon" aria-hidden>{item.icon}</span>{item.label}<span className="nav-arrow">↗</span>
        </Link>)}
      </nav>
      <div className="sidebar-bottom">
        <div className="status-lamp"><i/> AMBIENTE DE INVESTIGAÇÃO</div>
        <p>Probabilidades auditáveis.<br/>Sem sinais aprovados para aposta.</p>
        <span className="version">TQ / V0.1</span>
      </div>
    </aside>
    <div className="main-wrap">
      <header className="topbar"><div><span className="topbar-label">TENNIS / QUANTITATIVE INTELLIGENCE</span><span className="topbar-mobile">TENNIS QUANT</span></div><div className="topbar-right"><span className="topbar-dot"/> DADOS HISTÓRICOS <span className="topbar-sep">/</span> PT-PT</div></header>
      <main className="main-content">{children}</main>
    </div>
  </div>;
}

