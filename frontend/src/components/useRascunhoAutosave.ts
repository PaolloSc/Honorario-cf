"use client";

import { deleteDraft, saveDraft } from "@/app/lib/api";
import { gravarLocal, removerLocal } from "@/app/lib/rascunhoLocal";
import { useCallback, useEffect, useRef, useState } from "react";

export type EstadoRascunho = "ocioso" | "salvando" | "salvo" | "falhou";

const ESPERA_MS = 1200;

interface Opcoes {
  ativo: boolean; // false enquanto restaura um rascunho ou em modo edição
  draftId: string;
  formData: Record<string, unknown>;
  step: number;
  temConteudo: boolean; // não grava formulário em branco
}

/**
 * Salva o rascunho no servidor ~1s depois da última alteração, e de novo ao sair da
 * aba. Se o servidor falhar, a cópia local fica de buffer e o aviso na tela diz que
 * o rascunho ainda NÃO está seguro.
 */
export function useRascunhoAutosave({ ativo, draftId, formData, step, temConteudo }: Opcoes) {
  const [estado, setEstado] = useState<EstadoRascunho>("ocioso");
  const [salvoEm, setSalvoEm] = useState<Date | null>(null);
  const pendente = useRef(false); // há alteração ainda não confirmada pelo servidor
  const parado = useRef(false); // contrato gerado ou rascunho descartado
  const ultimo = useRef({ draftId, formData, step });
  ultimo.current = { draftId, formData, step };

  const enviar = useCallback(async (keepalive = false) => {
    if (parado.current) return;
    const { draftId: id, formData: dados, step: passo } = ultimo.current;
    gravarLocal(id, dados, passo);
    setEstado("salvando");
    try {
      await saveDraft(id, dados, passo, { keepalive });
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
    } catch {
      setEstado("falhou");
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
    const id = ultimo.current.draftId;
    removerLocal(id);
    setEstado("ocioso");
    setSalvoEm(null);
    await deleteDraft(id).catch(() => undefined);
  }, []);

  /** Volta a salvar — chamado ao começar/retomar outro rascunho. */
  const retomar = useCallback(() => {
    parado.current = false;
    pendente.current = false;
    setEstado("ocioso");
    setSalvoEm(null);
  }, []);

  const salvarAgora = useCallback(() => enviar(), [enviar]);

  return { estado, salvoEm, descartar, retomar, salvarAgora };
}
