"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { api } from "@/lib/api/client";

const nav = [
  ["Inbox", "/inbox"],
  ["Pipeline", "/pipeline"],
  ["Messages", "/messages"],
  ["Runs", "/runs"],
  ["Analytics", "/analytics"],
  ["Settings", "/settings"],
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [marketplaceUnavailable, setMarketplaceUnavailable] = useState(false);

  useEffect(() => {
    let active = true;
    api.health()
      .then((health) => {
        if (active) {
          setMarketplaceUnavailable(health.dependencies.marketplace === "unavailable");
        }
      })
      .catch(() => {
        if (active) setMarketplaceUnavailable(true);
      });
    return () => {
      active = false;
    };
  }, []);
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="brand" href="/inbox" aria-label="GigBid home">
          <span className="brand-mark">G</span>
          <span>
            <strong>GigBid</strong>
            <small>Freelancer copilot</small>
          </span>
        </Link>
        <nav aria-label="Primary navigation">
          {nav.map(([label, href]) => (
            <Link
              className={pathname.startsWith(href) ? "nav-link active" : "nav-link"}
              href={href}
              key={href}
            >
              {label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-status">
          <span className="status-dot" aria-hidden="true" />
          <span>
            <strong>Open profile</strong>
            <small>Human approval required</small>
          </span>
        </div>
      </aside>
      <main className="main-content">
        {marketplaceUnavailable ? (
          <div className="degraded-banner" role="status">
            Marketplace unavailable. New work is paused safely and can resume after recovery.
          </div>
        ) : null}
        {children}
      </main>
    </div>
  );
}

