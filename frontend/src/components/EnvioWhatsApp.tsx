"use client";

import { useState } from "react";
import QRCode from "qrcode";

// Envio do link de assinatura do DocuSeal pelo WhatsApp de quem está usando o
// sistema — sem gateway: o wa.me abre o aplicativo (ou o WhatsApp Web) com a
// mensagem pronta. O QR cobre quem não tem WhatsApp conectado no computador:
// a câmera do celular abre a mesma conversa. O QR é gerado aqui no navegador
// para o link de assinatura não passar por serviço de terceiros.
export default function EnvioWhatsApp({
  nome,
  link,
  whatsapp,
}: {
  nome: string;
  link: string;
  whatsapp: string;
}) {
  const [qr, setQr] = useState<string | null>(null);
  const [copiado, setCopiado] = useState(false);

  if (!link) return null;

  const mensagem =
    `Olá, ${nome}! Segue o link para assinar o contrato de honorários com o ` +
    `Carvalho & Furtado Advogados: ${link}`;
  // Sem número cadastrado, o wa.me abre o WhatsApp para escolher o contato.
  const url = `https://wa.me/${whatsapp.replace(/\D/g, "")}?text=${encodeURIComponent(mensagem)}`;

  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(mensagem);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      setCopiado(false);
    }
  };

  const alternarQr = async () => {
    if (qr) return setQr(null);
    setQr(await QRCode.toDataURL(url, { width: 200, margin: 1 }));
  };

  const botao =
    "inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded border border-border bg-card text-foreground hover:bg-background transition";

  return (
    <div className="mt-1.5">
      <div className="flex flex-wrap gap-2">
        <a href={url} target="_blank" rel="noopener noreferrer" className={botao}>
          Enviar pelo WhatsApp
        </a>
        <button type="button" onClick={copiar} className={botao}>
          {copiado ? "Mensagem copiada" : "Copiar mensagem"}
        </button>
        <button type="button" onClick={alternarQr} className={botao} aria-expanded={Boolean(qr)}>
          {qr ? "Esconder QR code" : "QR code"}
        </button>
      </div>
      {qr && (
        <div className="mt-2 inline-flex flex-col items-center gap-1 p-2 bg-white border border-border rounded">
          <img src={qr} alt={`QR code para enviar o link de assinatura a ${nome} pelo WhatsApp`} width={200} height={200} />
          <span className="text-[11px] text-muted">Aponte a câmera do celular</span>
        </div>
      )}
      {!whatsapp && (
        <p className="mt-1 text-[11px] text-muted">
          Sem WhatsApp cadastrado: o WhatsApp abre para você escolher o contato.
        </p>
      )}
    </div>
  );
}
