"use client";

import { useSession, signOut } from "next-auth/react";
import { useState } from "react";

export default function UserMenu() {
  const { data: session } = useSession();
  const [open, setOpen] = useState(false);

  if (!session?.user) return null;

  const initials = (session.user.name || session.user.email || "?")
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="w-9 h-9 rounded-full bg-primary-light text-primary-dark flex items-center justify-center text-xs font-bold hover:ring-2 hover:ring-brand-verde-claro/50 transition"
        title={session.user.name || session.user.email || ""}
      >
        {initials}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-2 w-56 bg-card rounded-lg border border-border shadow-lg z-50 py-2">
            <div className="px-4 py-2 border-b border-border">
              <p className="text-sm font-medium text-foreground truncate">
                {session.user.name}
              </p>
              <p className="text-xs text-muted truncate">
                {session.user.email}
              </p>
            </div>
            <a
              href="/admin"
              className="block px-4 py-2 text-sm text-foreground hover:bg-gray-50 transition"
            >
              Administracao
            </a>
            <button
              onClick={() => signOut({ callbackUrl: "/login" })}
              className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition"
            >
              Sair
            </button>
          </div>
        </>
      )}
    </div>
  );
}
