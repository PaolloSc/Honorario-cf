"use client";

import { SessionProvider } from "next-auth/react";
import AuthSync from "@/components/AuthSync";

export default function Providers({ children }: { children: React.ReactNode }) {
  // refetch a cada 5min mantem o token Azure renovado (o refresh vive no callback jwt)
  return (
    <SessionProvider refetchInterval={300} refetchOnWindowFocus={true}>
      <AuthSync>{children}</AuthSync>
    </SessionProvider>
  );
}
