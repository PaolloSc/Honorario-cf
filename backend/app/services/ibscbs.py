"""Bloco IBS/CBS da NFS-e: o que sai na nota conforme o regime, a data e o tomador.

Orientacao do contador (PDF de 12/11/2026), escritorio optante do Simples Nacional:
- competencia (dCompet da DPS, nao a data de emissao) ate 31/12/2026: bloco IBS/CBS em BRANCO (sem bloco, sem aliquotas de teste; LC 214, art. 348, III, "c");
- competencia a partir de 01/01/2027 (Ato Conjunto RFB/CGIBS 4/2026): CST 200, cClassTrib 200052 (profissoes
  intelectuais, reducao de 30%, LC 214 art. 127), cIndOp 100301. Vale para as NBS 1.1301.10/20/90 e
  1.1303.10/20 e para tomador PF no Brasil;
- tomador no exterior: CST 410, cClassTrib 410004 (exportacao, art. 8 da LC 214).
Fora do Simples a regra nao foi orientada: vale o que esta configurado no servico (padroes antigos).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

SIMPLES_NACIONAL = {"2", "3"}  # opSimpNac: 2 MEI, 3 ME/EPP
INICIO_SIMPLES = date(2027, 1, 1)

C_IND_OP = "100301"
CST_PROFISSAO_INTELECTUAL, C_CLASS_PROFISSAO_INTELECTUAL = "200", "200052"
CST_EXPORTACAO, C_CLASS_EXPORTACAO = "410", "410004"


@dataclass(frozen=True)
class BlocoIbsCbs:
    incluir: bool
    c_ind_op: str
    cst: str
    c_class_trib: str

    def como_dict(self) -> dict:
        return {"incluir": self.incluir, "c_ind_op": self.c_ind_op, "cst": self.cst, "c_class_trib": self.c_class_trib}


def resolver(
    op_simp_nac: str | None, competencia: date, *, exterior: bool = False,
    incluir_config: bool = False, c_ind_op: str | None = None, cst: str | None = None, c_class_trib: str | None = None,
) -> BlocoIbsCbs:
    if op_simp_nac in SIMPLES_NACIONAL:
        if competencia < INICIO_SIMPLES:
            return BlocoIbsCbs(False, "", "", "")
        if exterior:
            return BlocoIbsCbs(True, C_IND_OP, CST_EXPORTACAO, C_CLASS_EXPORTACAO)
        return BlocoIbsCbs(True, C_IND_OP, CST_PROFISSAO_INTELECTUAL, C_CLASS_PROFISSAO_INTELECTUAL)
    # Regime nao orientado: o servico manda, com os padroes de sempre.
    return BlocoIbsCbs(incluir_config, c_ind_op or C_IND_OP, cst or "000", c_class_trib or "000001")
