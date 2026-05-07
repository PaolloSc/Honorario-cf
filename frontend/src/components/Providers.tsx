"use client";

import { SessionProvider } from "next-auth/react";
import AuthSync from "@/components/AuthSync";

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <AuthSync>{children}</AuthSync>
    </SessionProvider>
  );
}
