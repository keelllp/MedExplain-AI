"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";

const LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/upload", label: "Upload" },
  { href: "/chat", label: "Chat" },
  { href: "/trends", label: "Trends" },
  { href: "/profile", label: "Profile" },
];

export function TopNav() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-paper/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link
          href={user ? "/dashboard" : "/"}
          className="group flex items-center gap-2.5"
          aria-label="MedExplain AI home"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-brand text-[15px] font-semibold text-white shadow-sm shadow-brand/30 transition-transform group-hover:-rotate-6">
            M
          </span>
          <span className="font-display text-xl font-semibold tracking-tight text-ink">
            MedExplain<span className="text-brand"> AI</span>
          </span>
        </Link>

        <nav className="flex items-center gap-1 text-sm">
          {user ? (
            <>
              <div className="mr-1 hidden items-center gap-1 sm:flex">
                {LINKS.map((l) => {
                  const active = pathname === l.href || pathname.startsWith(`${l.href}/`);
                  return (
                    <Link
                      key={l.href}
                      href={l.href}
                      className={cn(
                        "rounded-full px-3.5 py-1.5 font-medium transition-colors",
                        active
                          ? "bg-brand-tint text-brand-strong"
                          : "text-ink-muted hover:bg-surface-sunken hover:text-ink",
                      )}
                    >
                      {l.label}
                    </Link>
                  );
                })}
              </div>
              <button
                onClick={() => {
                  logout();
                  router.push("/login");
                }}
                className="rounded-full px-3.5 py-1.5 font-medium text-ink-muted transition-colors hover:bg-surface-sunken hover:text-ink"
              >
                Log out
              </button>
            </>
          ) : (
            <>
              <Link
                href="/login"
                className="rounded-full px-3.5 py-1.5 font-medium text-ink-muted transition-colors hover:bg-surface-sunken hover:text-ink"
              >
                Log in
              </Link>
              <Link
                href="/signup"
                className="rounded-full bg-brand px-4 py-1.5 font-medium text-white shadow-sm shadow-brand/25 transition-colors hover:bg-brand-strong"
              >
                Sign up
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
