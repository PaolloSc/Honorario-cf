"""Converte os Dados do contrato salvos (rascunhos e versoes) para o formato atual (ticket 04).

    CONVERTER_DATABASE_URL=<url> python scripts/converter_formato.py            # dry-run (padrao): nada e gravado
    CONVERTER_DATABASE_URL=<url> python scripts/converter_formato.py --apply --ok "OK-DO-USUARIO" --backup <branch>

A conversao e a mesma funcao do wizard (frontend/scripts/converter-formato.ts -> normalizarFormData),
idempotente. Relatorio so com contagens e nomes de campo: nunca imprime valores nem dados pessoais.
Trava de seguranca: uma VERSAO so e convertida se o DOCX regerado do formato novo tiver o mesmo texto
do regerado do formato antigo (a vigencia no pro-labore, por ex., ressuscitaria uma clausula em
contrato antigo). As que diferem ficam como estao e sao listadas no relatorio; a tela continua
convertendo ao abrir. Rascunhos nao tem DOCX e sao sempre convertidos.
So converte contratos de honorarios; consumidor aereo e complementares tem outros formatos.

REGRA (docs/adr/0002): em producao, so com branch de backup no Neon, dry-run mostrado e ok final
explicito do responsavel. --apply exige --ok e --backup; sem eles o script recusa.
"""
import argparse
import copy
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import psycopg2

RAIZ = Path(__file__).resolve().parents[2]
CONVERSOR = RAIZ / "frontend" / "scripts" / "converter-formato.ts"
TABELAS = {
    "versao": ("contract_versions", "form_data_json"),
    "rascunho": ("contract_drafts", "form_data_json"),
}


def converter(itens: list[dict]) -> list[dict]:
    if not itens:
        return []
    r = subprocess.run(
        ["node", "--experimental-strip-types", "--no-warnings", str(CONVERSOR)],
        input=json.dumps(itens).encode(), capture_output=True, cwd=RAIZ / "frontend",
    )
    if r.returncode:
        sys.exit("conversor falhou: " + r.stderr.decode()[-500:])
    return json.loads(r.stdout)


def motivos(antes: dict, depois: dict) -> list[str]:
    """Categorias da mudanca, sem valores."""
    out = []
    ac_a, ac_d = antes.get("acessorios") or {}, depois.get("acessorios") or {}
    if not ac_a.get("vigencia_inicio") and ac_d.get("vigencia_inicio"):
        out.append("vigencia saiu do pro-labore")
    pa, pd = antes.get("participacao") or {}, depois.get("participacao") or {}
    if any(pa.get(k) not in (None, "", [], {}) for k in ("para_quem", "natureza", "percentual_ou_valor")):
        out.append("participacao no formato antigo (com valor)")
    elif any(k in pa for k in ("para_quem", "natureza", "percentual_ou_valor", "contato_financeiro_cliente")):
        out.append("participacao com chaves antigas vazias")
    if "versao_formato" not in antes:
        out.append("sem numero de versao")
    perdidos = sorted(k for k in ac_a if k not in ac_d and ac_a[k] is not None)
    if perdidos:
        out.append("acessorios perdidos: " + ",".join(perdidos))
    topo = sorted(k for k in antes if k not in depois)
    if topo:
        out.append("topo perdido: " + ",".join(topo))
    resto = [k for k in depois if k not in ("versao_formato",) and antes.get(k) != depois.get(k)]
    if set(resto) - {"acessorios", "participacao", "escopos"}:
        out.append("outros campos: " + ",".join(sorted(set(resto) - {"acessorios", "participacao", "escopos"})))
    return out or ["so versao_formato"]


def texto_docx(form: dict) -> str:
    from docx import Document
    from app.services.contrato_carregado import parse_form_data
    # copia: os validadores do backend completam campos NO PROPRIO dict e gravariam essas chaves
    data, gen = parse_form_data(copy.deepcopy(form))
    _, caminho = gen.generate(data)
    return "\n".join(p.text for p in Document(caminho).paragraphs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--ok", default="")
    ap.add_argument("--backup", default="")
    a = ap.parse_args()
    if a.apply and (a.ok != "OK-DO-USUARIO" or not a.backup):
        sys.exit("RECUSADO: --apply exige --backup <branch Neon> e --ok OK-DO-USUARIO (ok final do responsavel).")
    url = os.environ.get("CONVERTER_DATABASE_URL")
    if not url:
        sys.exit("defina CONVERTER_DATABASE_URL")

    conn = psycopg2.connect(url)
    conn.set_session(readonly=not a.apply)
    cur = conn.cursor()
    itens, origem = [], {}
    for tipo, (tabela, coluna) in TABELAS.items():
        cur.execute(f"select id, {coluna} from {tabela}")
        for id_, bruto in cur.fetchall():
            try:
                dados = json.loads(bruto)
            except Exception:
                print(f"ilegivel: {tipo} #{id_}")
                continue
            if (dados.get("tipo_contrato") or "honorarios") != "honorarios":
                origem[(tipo, id_)] = None
                continue
            chave = f"{tipo}:{id_}"
            itens.append({"chave": chave, "dados": dados})
            origem[(tipo, id_)] = dados

    convertidos = {i["chave"]: i["dados"] for i in converter(itens)}
    resumo, mudariam = Counter(), []
    for it in itens:
        tipo, id_ = it["chave"].split(":")
        depois = convertidos[it["chave"]]
        if json.dumps(depois, sort_keys=True) == json.dumps(it["dados"], sort_keys=True):
            resumo[(tipo, "sem mudanca")] += 1
            continue
        for m in motivos(it["dados"], depois):
            resumo[(tipo, m)] += 1
        resumo[(tipo, "MUDARIA")] += 1
        mudariam.append((tipo, int(id_), it["dados"], depois))
    for tipo, id_ in [k for k, v in origem.items() if v is None]:
        resumo[(tipo, "outro tipo de contrato (ignorado)")] += 1

    print(f"{'APLICANDO' if a.apply else 'DRY-RUN (nada gravado)'} | honorarios lidos: {len(itens)}")
    for (tipo, m), n in sorted(resumo.items()):
        print(f"  {tipo:9} {m}: {n}")

    os.environ.setdefault("OUTPUT_DIR", str(RAIZ / "backend" / ".dryrun_docx"))
    sys.path.insert(0, str(RAIZ / "backend"))
    seguros, pulados, erros, causas = [], 0, 0, Counter()
    for item in mudariam:
        tipo, id_, antes, depois = item
        if tipo == "rascunho":
            seguros.append(item)
            continue
        try:
            if texto_docx(antes) == texto_docx(depois):
                seguros.append(item)
            else:
                pulados += 1
        except Exception as e:
            erros += 1  # nao da para provar que o DOCX nao muda: nao converte
            causas[type(e).__name__] += 1
    print(f"  versoes puladas (DOCX regerado mudaria): {pulados} | sem como provar (erro): {erros} | a converter: {len(seguros)} de {len(mudariam)}")
    if causas:
        print("  causas dos erros (so o tipo):", dict(causas))
    mudariam = seguros

    if a.apply:
        for tipo, id_, _, depois in mudariam:
            tabela, coluna = TABELAS[tipo]
            cur.execute(f"update {tabela} set {coluna}=%s where id=%s", (json.dumps(depois, ensure_ascii=False), id_))
        conn.commit()
        print(f"gravados: {len(mudariam)}")
    conn.close()


if __name__ == "__main__":
    main()
