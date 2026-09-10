#!/usr/bin/env python3
"""Gera um contrato e imprime o texto numerado, como o advogado o lê.

A numeração das cláusulas não está no texto do .docx — quem numera é o Word,
pela lista multinível. Ler `document.xml` direto mostra as cláusulas SEM número
e induz ao erro. Este script passa pelo mesmo conversor do preview da tela do
contrato, então o que ele imprime é o que sai no Word.

Uso (a partir de backend/):
    uv run python ../.claude/skills/contrato-cf/scripts/dump_contrato.py            # lista os presets
    uv run python ../.claude/skills/contrato-cf/scripts/dump_contrato.py pj-multi
    uv run python ../.claude/skills/contrato-cf/scripts/dump_contrato.py pj-multi --docx /tmp/x.docx
    uv run python ../.claude/skills/contrato-cf/scripts/dump_contrato.py meu_caso.json

Os presets cobrem as formas que mais quebram: honorário único (numeração
corrida) x vários (subcláusulas), com e sem êxito, PJ com dois representantes.
Para um caso do mundo real, salve o payload do wizard num .json e passe o caminho.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "backend"))

_HORA = {
    "valor_hora": 450, "tem_teto_mensal": False, "tem_pacote_horas": False,
    "tem_hora_urgencia": True, "tem_hora_fora_expediente": True,
}
_EXITO = {
    "subtipo": "percentual_fixo", "percentual": 15,
    "base_calculo": "o benefício econômico apurado",
    "incidencia": "beneficio_economico", "forma_pagamento": "conforme_cumprimento",
}
_PF = {
    "tipo": "PF", "nome": "Fulano de Tal", "nacionalidade": "Brasileira",
    "cpf": "123.456.789-00", "profissao": "Engenheiro", "estado_civil": "Casado(a)",
    "endereco": "Rua X, n. 10, Belo Horizonte/MG", "email": "fulano@exemplo.com",
}
_PJ_2_REPS = {
    "tipo": "PJ", "cnpj": "12345678000199", "razao_social": "Exemplo Industria Ltda",
    "endereco": "Av. Afonso Pena, n. 1500, Belo Horizonte/MG",
    "email": "financeiro@exemplo.com.br",
    "representantes": [
        {"nome": "Marina Alves", "nacionalidade": "Brasileira", "profissao": "Empresário",
         "estado_civil": "Casado(a)", "cpf": "111.222.333-44", "email": "marina@exemplo.com.br"},
        {"nome": "Rafael Duarte", "nacionalidade": "Brasileira", "profissao": "Empresário",
         "estado_civil": "Solteiro(a)", "cpf": "555.666.777-88", "email": "rafael@exemplo.com.br"},
    ],
}
_ACESSORIOS = {
    "tem_reembolso": True, "reembolso_limitado": False,
    "tem_penalidade_inadimplemento": True,
}


def _req(contratante: dict, honorarios: list[str], **acessorios) -> dict:
    escopo: dict = {"tipo": "contencioso_representacao", "honorarios": honorarios}
    if "hora_trabalhada" in honorarios:
        escopo["hora_trabalhada"] = dict(_HORA)
    if "exito" in honorarios:
        escopo["exito"] = dict(_EXITO)
    if "pro_labore" in honorarios:
        escopo["pro_labore"] = {"valor_total": 20000, "tem_parcelamento": False}
    return {
        "contratantes": [contratante],
        "incluir_partes_relacionadas": True,
        "escopos": [escopo],
        "acessorios": {**_ACESSORIOS, **acessorios},
        "participacao": {"tem_participacao": False},
    }


PRESETS = {
    # honorário único -> numeração corrida (3.1, 3.2...) e SEM subtítulo
    "pf-hora": lambda: _req(_PF, ["hora_trabalhada"]),
    # vários honorários -> 3.1 / 3.1.1 ... 3.2 / 3.2.1, COM subtítulo
    "pj-multi": lambda: _req(_PJ_2_REPS, ["hora_trabalhada", "exito"]),
    # sem êxito -> 5.6 e a tabela de fases da 8.3 somem
    "pf-sem-exito": lambda: _req(_PF, ["pro_labore"]),
    # êxito sem processo judicial -> 8.3 usa o critério livre, sem tabela de fases
    "exito-extrajudicial": lambda: _req(
        _PF, ["exito"], criterio_extincao_exito="quando da formalização do acordo"
    ),
    # seção extra empurra o Foro (11 -> 12), tudo renumerado sozinho
    "com-clausulas-extras": lambda: _req(
        _PF, ["hora_trabalhada"],
        clausulas_adicionais="As Partes elegem o e-mail como meio válido de comunicação.",
        valor_km=2.40,
    ),
}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        print("Presets:", ", ".join(PRESETS))
        return 1

    alvo = sys.argv[1]
    if alvo in PRESETS:
        req = PRESETS[alvo]()
    else:
        caminho = Path(alvo)
        if not caminho.exists():
            print(f"'{alvo}' não é um preset nem um arquivo. Presets: {', '.join(PRESETS)}")
            return 1
        req = json.loads(caminho.read_text(encoding="utf-8"))

    from app.models.contract import ContratoRequest
    from app.routers.contract import _docx_to_html
    from app.services.contract_generator import ContractGenerator

    _, path = ContractGenerator().generate(ContratoRequest(**req), contract_id=f"DUMP_{alvo}")

    if "--docx" in sys.argv:
        destino = sys.argv[sys.argv.index("--docx") + 1]
        shutil.copy(path, destino)
        print(f"[docx salvo em {destino}]\n")

    html = _docx_to_html(Path(path))
    for tag, corpo in re.findall(r"<(h1|h3|p)>(.*?)</\1>", html, re.S):
        texto = (
            re.sub(r"<[^>]+>", "", corpo)
            .replace("&amp;", "&").replace("&quot;", '"').replace("&#x27;", "'")
        )
        print(("## " if tag != "p" else "   ") + texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
