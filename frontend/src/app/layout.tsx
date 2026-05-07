import type { Metadata } from "next";
import { Lexend_Zetta } from "next/font/google";
import Logo from "@/components/ui/Logo";
import Providers from "@/components/Providers";
import UserMenu from "@/components/UserMenu";
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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="pt-BR"
      className={`${lexendZetta.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <Providers>
          <header className="bg-primary-dark text-white shadow-md">
            <div className="max-w-5xl mx-auto px-6 py-5 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <a href="/" className="flex items-center gap-4">
                  <Logo variant="light" className="h-10 w-auto" showSubtitle={false} />
                </a>
                <div className="leading-tight hidden sm:block">
                  <p className="text-xs text-brand-verde-claro/90 font-sans">
                    Automacao de Contratos de Honorarios
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-6">
                <nav className="hidden sm:flex items-center gap-6 text-sm font-medium">
                  <a href="/" className="text-brand-verde-claro/80 hover:text-white transition">
                    Novo Contrato
                  </a>
                  <a href="/contracts" className="text-brand-verde-claro/80 hover:text-white transition">
                    Contratos
                  </a>
                </nav>
                <UserMenu />
              </div>
            </div>
          </header>

          <main className="flex-1">{children}</main>

          <footer className="bg-primary-dark text-brand-verde-claro/90 mt-12">
            <div className="max-w-5xl mx-auto px-6 py-6 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs">
              <div className="flex items-center gap-2">
                <Logo variant="light" className="h-5 w-auto" showSubtitle={false} />
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
