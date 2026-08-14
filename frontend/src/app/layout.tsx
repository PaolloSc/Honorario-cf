import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import { Lexend_Zetta } from "next/font/google";
import Logo from "@/components/ui/Logo";
import NavConsumidor from "@/components/NavConsumidor";
import Providers from "@/components/Providers";
import UserMenu from "@/components/UserMenu";
import { auth } from "@/auth";
import "./globals.css";

const lexendZetta = Lexend_Zetta({
  variable: "--font-lexend-zetta",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "C&F Advogados — Automação de Contratos de Honorários",
  description:
    "Sistema de automação para geração de contratos de honorários advocatícios — Carvalho & Furtado Advogados",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const session = await auth();
  // Login de desenvolvimento usa o cookie dev_session (sem sessao next-auth).
  // O middleware ja o aceita; sem isto o menu some e as telas ficam sem acesso.
  const devSession =
    process.env.NEXT_PUBLIC_DEV_MODE === "true" &&
    !!(await cookies()).get("dev_session");
  const isAuthenticated = !!session?.user || devSession;
  return (
    <html
      lang="pt-BR"
      className={`${lexendZetta.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <Providers>
          <header className="bg-primary-dark text-white shadow-md">
            <div className="px-6 py-5 flex items-center justify-between">
              <Link href="/" className="flex items-center">
                <Logo variant="light" className="h-10 w-auto" showSubtitle={false} />
              </Link>
              <div className="flex items-center gap-6">
                {isAuthenticated && (
                  <nav className="hidden sm:flex items-center gap-6 text-sm font-medium">
                    <Link href="/" className="text-brand-verde-claro/80 hover:text-white transition">
                      Honorários
                    </Link>
                    {/* Restrito: o link so' aparece para a equipe autorizada. */}
                    <NavConsumidor />
                    <Link href="/contracts" className="text-brand-verde-claro/80 hover:text-white transition">
                      Contratos
                    </Link>
                  </nav>
                )}
                <UserMenu />
              </div>
            </div>
          </header>

          <main className="flex-1">{children}</main>

          <footer className="bg-primary-dark text-brand-verde-claro/90 mt-12">
            <div className="max-w-5xl mx-auto px-6 py-6 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs">
              <div className="flex items-center gap-2">
                <Logo variant="light" format="35" className="h-6 w-auto" showSubtitle={false} />
                <span className="font-display tracking-wide">
                  &copy; {new Date().getFullYear()}
                </span>
              </div>
              <p className="font-sans">
                Documento de uso interno — Confidencial
              </p>
            </div>
          </footer>
        </Providers>
      </body>
    </html>
  );
}
