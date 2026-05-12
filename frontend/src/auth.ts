import NextAuth from "next-auth";
import MicrosoftEntraID from "next-auth/providers/microsoft-entra-id";

declare module "next-auth" {
  interface Session {
    accessToken?: string;
    user: {
      id?: string;
      name?: string | null;
      email?: string | null;
      image?: string | null;
      role?: string;
    };
  }
}

declare module "@auth/core/jwt" {
  interface JWT {
    accessToken?: string;
    refreshToken?: string;
    expiresAt?: number;
    role?: string;
  }
}

export const { handlers, signIn, signOut, auth } = NextAuth({
  secret: process.env.AUTH_SECRET,
  providers: [
    MicrosoftEntraID({
      clientId: process.env.AZURE_AD_CLIENT_ID!,
      clientSecret: process.env.AZURE_AD_CLIENT_SECRET!,
      issuer: `https://login.microsoftonline.com/${process.env.AZURE_AD_TENANT_ID!}/v2.0`,
      authorization: {
        params: {
          scope: "openid profile email User.Read offline_access",
        },
      },
    }),
  ],
  callbacks: {
    authorized({ auth, request }) {
      const isLoggedIn = !!auth?.user;
      const isOnLogin = request.nextUrl.pathname.startsWith("/login");
      if (isOnLogin) return true;
      return isLoggedIn;
    },
    async jwt({ token, account }) {
      if (account) {
        token.accessToken = account.id_token;
        token.refreshToken = account.refresh_token;
        token.expiresAt = account.expires_at;
        return token;
      }

      // Return token if not expired (with 60s buffer to avoid edge-case expiry during request)
      if (token.expiresAt && Date.now() < (token.expiresAt * 1000 - 60000)) {
        return token;
      }

      // Refresh expired token
      if (token.refreshToken) {
        try {
          const url = `https://login.microsoftonline.com/${process.env.AZURE_AD_TENANT_ID}/oauth2/v2.0/token`;
          const body = new URLSearchParams({
            client_id: process.env.AZURE_AD_CLIENT_ID!,
            client_secret: process.env.AZURE_AD_CLIENT_SECRET!,
            grant_type: "refresh_token",
            refresh_token: token.refreshToken as string,
            scope: "openid profile email User.Read offline_access",
          });
          const res = await fetch(url, { method: "POST", body, headers: { "Content-Type": "application/x-www-form-urlencoded" } });
          const data = await res.json();
          if (data.id_token) {
            token.accessToken = data.id_token;
            token.refreshToken = data.refresh_token ?? token.refreshToken;
            token.expiresAt = Math.floor(Date.now() / 1000) + (data.expires_in ?? 3600);
          }
        } catch (e) {
          console.error("[AUTH] Token refresh failed:", e);
        }
      }

      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string;
      if (token.sub) {
        session.user.id = token.sub;
      }
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
  debug: process.env.NODE_ENV === "development",
  trustHost: true,
  logger: {
    error(error) {
      console.error("[AUTH ERROR]", error);
      if (error.cause) console.error("[AUTH CAUSE]", error.cause);
    },
  },
});
