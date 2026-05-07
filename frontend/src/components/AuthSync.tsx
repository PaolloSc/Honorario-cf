"use client";

import { useSession } from "next-auth/react";
import { useEffect } from "react";
import { setAccessToken } from "@/app/lib/api";

export default function AuthSync({ children }: { children: React.ReactNode }) {
  const { data: session } = useSession();

  useEffect(() => {
    setAccessToken(session?.accessToken || null);
  }, [session?.accessToken]);

  return <>{children}</>;
}
