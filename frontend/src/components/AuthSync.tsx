"use client";

import { useSession } from "next-auth/react";
import { setAccessToken } from "@/app/lib/api";

export default function AuthSync({ children }: { children: React.ReactNode }) {
  const { data: session } = useSession();

  // Set token synchronously during render (not useEffect) so child
  // components' effects already have the token available.
  setAccessToken(session?.accessToken || null);

  return <>{children}</>;
}
