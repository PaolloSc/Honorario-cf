"use client";

import { SessionProvider } from "next-auth/react";
import AuthSync from "@/components/AuthSync";

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    // refetch a cada 5min mantem o token Azure renovado (o refresh vive no callback jwt)
    <SessionProvider refetchInterval={300} refetchOnWindowFocus>
      <AuthSync>{children}</AuthSync>
    </SessionProvider>
  );
}
