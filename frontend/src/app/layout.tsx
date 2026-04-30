import type { Metadata } from "next";
import { Lexend_Zetta } from "next/font/google";
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
        <header className="bg-primary-dark text-white shadow-md">
          <div className="max-w-5xl mx-auto px-6 py-5 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                aria-hidden
                className="w-11 h-11 rounded-md bg-primary-light text-primary-dark flex items-center justify-center font-display font-bold text-lg shadow-sm"
              >
                C&amp;F
              </div>
              <div className="leading-tight">
                <p className="font-display font-semibold text-base tracking-wide">
                  Carvalho &amp; Furtado Advogados
                </p>
                <p className="text-xs text-brand-verde-claro/90 font-sans">
                  Automação de Contratos de Honorários
                </p>
              </div>
            </div>
            <span className="hidden sm:inline-flex items-center gap-2 text-xs font-medium text-brand-verde-claro/80 uppercase tracking-widest">
              Sistema Interno
            </span>
          </div>
        </header>

        <main className="flex-1">{children}</main>

        <footer className="bg-primary-dark text-brand-verde-claro/90 mt-12">
          <div className="max-w-5xl mx-auto px-6 py-6 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs">
            <p className="font-display tracking-wide">
              © {new Date().getFullYear()} Carvalho &amp; Furtado Advogados
            </p>
            <p className="font-sans">
              Documento de uso interno — Confidencial
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
