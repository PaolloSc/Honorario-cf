import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";

export async function middleware(req: NextRequest) {
  // Dev bypass: cookie dev_session presente → libera (apenas se NEXT_PUBLIC_DEV_MODE=true)
  if (
    process.env.NEXT_PUBLIC_DEV_MODE === "true" &&
    req.cookies.get("dev_session")
  ) {
    return NextResponse.next();
  }
  // @ts-expect-error — auth() retorna handler compatível
  return auth(req);
}

export const config = {
  matcher: [
    "/((?!login|financeiro/login|financeiro/dev-login|api/auth|_next|favicon\\.ico|logo-cf|brand).*)",
  ],
};
