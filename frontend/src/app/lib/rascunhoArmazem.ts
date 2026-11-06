import { deleteDraft, getDraft } from "./api";
import { dataDaApi } from "./datas";
import { lerLocal, removerLocal } from "./rascunhoLocal";
import type { Armazem } from "./rascunho";

/** Adapter de produção do Rascunho: API do servidor + cópia local (localStorage) de quem está logado. */
export function armazemReal(dono: string): Armazem {
  return {
    lerServidor: async (id) => {
      const d = await getDraft(id);
      return { dados: d.form_data, passo: d.current_step, atualizadoEm: dataDaApi(d.updated_at).getTime(), versao: d.updated_at };
    },
    lerLocal: (id) => {
      const l = lerLocal(id, dono);
      return l ? { dados: l.form_data, passo: l.current_step, atualizadoEm: dataDaApi(l.updated_at).getTime(), versao: null } : null;
    },
    apagarServidor: async (id) => void (await deleteDraft(id)),
    apagarLocal: removerLocal,
  };
}
