export { auth as middleware } from "@/auth";

export const config = {
  matcher: [
    /*
     * Protect all routes except:
     * - /login
     * - /api/auth (NextAuth routes)
     * - /_next (static files)
     * - /favicon.ico, /logo-cf*
     */
    "/((?!login|api/auth|_next|favicon\\.ico|logo-cf).*)",
  ],
};
