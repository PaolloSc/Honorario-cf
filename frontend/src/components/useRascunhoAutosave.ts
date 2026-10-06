"use client";

import { ConflitoError, deleteDraft, saveDraft } from "@/app/lib/api";
import { gravarLocal, removerLocal } from "@/app/lib/rascunhoLocal";
import { useCallback, useEffect, useRef, useState } from "react";

export type EstadoRascunho = "ocioso" | "salvando" | "salvo" | "falhou" | "conflito";

const ESPERA_MS = 1200;

interface Opcoes {
  ativo: boolean; // false enquanto restaura um rascunho
  draftId: string;
  formData: Record<string, unknown>;
  step: number;
  temConteudo: boolean; // não grava formulário em branco
  dono: string; // e-mail de quem está logado — marca a cópia local
}

/**
 * Salva o rascunho no servidor ~1s depois da última alteração, e de novo ao sair da
 * aba. Se o servidor falhar, a cópia local fica de buffer e o aviso na tela diz que
 * o rascunho ainda NÃO está seguro. Se outra aba (ou computador) gravou o mesmo
 * rascunho depois, o servidor responde 409: para de salvar e o estado vira "conflito".
 */
export function useRascunhoAutosave({ ativo, draftId, formData, step, temConteudo, dono }: Opcoes) {
  const [estado, setEstado] = useState<EstadoRascunho>("ocioso");
  const [salvoEm, setSalvoEm] = useState<Date | null>(null);
  const pendente = useRef(false); // há alteração ainda não confirmada pelo servidor
  const parado = useRef(false); // contrato gerado, rascunho descartado ou conflito
  const versao = useRef<string | null>(null); // updated_at do servidor que esta aba conhece
  const emVoo = useRef(false);
  const deNovo = useRef(false);
  const ultimo = useRef({ draftId, formData, step, dono });
  ultimo.current = { draftId, formData, step, dono };

  const enviar = useCallback(async (keepalive = false): Promise<void> => {
    if (parado.current) return;
    // Um PUT por vez: o segundo levaria a versão velha e daria 409 contra a própria aba.
    // ponytail: o reenvio espera o PUT em voo; se a aba fechar nesse meio, perde ~1s de edição.
    if (emVoo.current) {
      deNovo.current = true;
      return;
    }
    emVoo.current = true;
    const { draftId: id, formData: dados, step: passo, dono: email } = ultimo.current;
    gravarLocal(id, dados, passo, email);
    setEstado("salvando");
    try {
      const r = await saveDraft(id, dados, passo, { keepalive, knownUpdatedAt: versao.current });
      versao.current = r.updated_at;
      if (parado.current) {
        // descartado com o PUT em voo: o PUT recriou o que o DELETE acabara de apagar
        await deleteDraft(id).catch(() => undefined);
        return;
      }
      // só confirma se nada mudou durante o envio
      if (ultimo.current.formData === dados && ultimo.current.step === passo) {
        pendente.current = false;
        removerLocal(id);
      }
      setSalvoEm(new Date());
      setEstado("salvo");
    } catch (e) {
      if (e instanceof ConflitoError) {
        // A cópia local daqui é a versão "perdedora": se ficasse, ao recarregar ela
        // pareceria mais nova e sobrescreveria o que a outra aba gravou.
        parado.current = true;
        pendente.current = false;
        deNovo.current = false;
        removerLocal(id);
        setEstado("conflito");
      } else {
        setEstado("falhou");
      }
    } finally {
      emVoo.current = false;
      if (deNovo.current && !parado.current) {
        deNovo.current = false;
        void enviar();
      }
    }
  }, []);

  useEffect(() => {
    if (!ativo || !temConteudo || parado.current) return;
    pendente.current = true;
    const t = setTimeout(() => void enviar(), ESPERA_MS);
    return () => clearTimeout(t);
  }, [ativo, temConteudo, draftId, formData, step, enviar]);

  useEffect(() => {
    if (!ativo) return;
    const aoSair = () => {
      if (document.visibilityState === "hidden" && pendente.current && !parado.current) {
        void enviar(true);
      }
    };
    const aoFechar = (e: BeforeUnloadEvent) => {
      if (pendente.current && !parado.current) e.preventDefault();
    };
    const aoVoltarRede = () => {
      if (pendente.current) void enviar();
    };
    document.addEventListener("visibilitychange", aoSair);
    window.addEventListener("beforeunload", aoFechar);
    window.addEventListener("online", aoVoltarRede);
    return () => {
      document.removeEventListener("visibilitychange", aoSair);
      window.removeEventListener("beforeunload", aoFechar);
      window.removeEventListener("online", aoVoltarRede);
    };
  }, [ativo, enviar]);

  /** Apaga o rascunho (servidor + cópia local) e para de salvar até `retomar()`. */
  const descartar = useCallback(async () => {
    parado.current = true;
    pendente.current = false;
    versao.current = null;
    const id = ultimo.current.draftId;
    removerLocal(id);
    setEstado("ocioso");
    setSalvoEm(null);
    await deleteDraft(id).catch(() => undefined);
  }, []);

  /** Volta a salvar — chamado ao começar/retomar outro rascunho, com a versão do servidor. */
  const retomar = useCallback((versaoServidor: string | null = null) => {
    parado.current = false;
    pendente.current = false;
    versao.current = versaoServidor;
    setEstado("ocioso");
    setSalvoEm(null);
  }, []);

  const salvarAgora = useCallback(() => enviar(), [enviar]);

  return { estado, salvoEm, descartar, retomar, salvarAgora };
}
