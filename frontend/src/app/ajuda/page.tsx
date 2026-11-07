import { TOURS } from "@/app/lib/tutorial";

export const metadata = { title: "Como usar" };

// Mesmos textos do tour guiado, numa página só.
export default function ComoUsarPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="font-display text-2xl font-semibold text-primary-dark tracking-wide">Como usar</h1>
      <p className="text-sm text-muted mt-1 mb-8">
        Em cada tela, o botão <strong>?</strong> no canto de baixo abre o passo a passo daquela tela.
      </p>
      {TOURS.map((t) => (
        <section key={t.chave} className="mb-8">
          <h2 className="font-display text-lg font-semibold text-foreground mb-3">{t.nome}</h2>
          <dl className="space-y-3">
            {t.passos.map((p) => (
              <div key={p.titulo} className="rounded-lg border border-border bg-card p-4">
                <dt className="font-medium text-foreground">{p.titulo}</dt>
                <dd className="text-sm text-muted mt-1">{p.texto}</dd>
              </div>
            ))}
          </dl>
        </section>
      ))}
    </div>
  );
}
