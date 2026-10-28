"""Apoio ao preenchimento de processos: decodifica o numero CNJ, le partes do Legal One (so leitura)
e importa uma lista de processos por planilha."""
import csv
import io
import logging
import re
import zipfile

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.auth import CurrentUser, get_current_user
from app.services import cnj, legalone_leitura

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/processos", tags=["Processos"])

LIMITE_BYTES = 2_000_000
LIMITE_LINHAS = 500
LIMITE_DESCOMPRIMIDO = 20_000_000  # um .xlsx pequeno pode expandir a centenas de MB (zip bomb)
MSG_INVALIDO = "Número fora do padrão CNJ (20 dígitos) ou com dígito verificador errado"


def _dados(numero: str) -> dict:
    c = cnj.decodificar(numero)
    if not c:
        return {"valido": False, "numero": numero.strip()[:60], "erro": MSG_INVALIDO}
    return {"valido": True, "numero": c.numero, "ano": c.ano, "justica": c.justica, "tribunal": c.tribunal}


@router.get("/cnj")
def consultar_cnj(numero: str, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Tribunal pelo numero e, se o processo ja estiver no Legal One do escritorio, as partes de la'."""
    r = _dados(numero[:60])
    r["legalone"] = None
    if r["valido"]:
        partes = legalone_leitura.partes_do_processo(r["numero"])
        if partes:
            r["legalone"] = {**partes, "descricao": legalone_leitura.descricao(partes)}
    return r


def _cabecalho(linha: list[str]) -> dict[str, int] | None:
    """Mapa coluna->indice se a primeira linha for cabecalho (nenhuma celula e' um numero CNJ)."""
    if any(cnj.normalizar(c) for c in linha):
        return None
    mapa: dict[str, int] = {}
    for i, c in enumerate(linha):
        t = c.strip().lower()
        if re.search(r"n[uú]mero|processo|cnj", t) and "numero" not in mapa:
            mapa["numero"] = i
        elif "tipo" in t:
            mapa["tipo"] = i
        elif re.search(r"descri|partes", t):
            mapa["descricao"] = i
    return mapa if "numero" in mapa else None


def _linhas(nome: str, conteudo: bytes) -> tuple[list[list[str]], int]:
    """(linhas da 1a aba, quantas abas o arquivo tem)."""
    if nome.lower().endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook

        # Antes de abrir: soma o tamanho descomprimido declarado no zip.
        with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
            if sum(i.file_size for i in z.infolist()) > LIMITE_DESCOMPRIMIDO:
                raise HTTPException(422, "Planilha grande demais depois de descompactada (máximo 20 MB)")
        wb = load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
        ws = wb.worksheets[0]
        linhas = [["" if v is None else str(v).strip() for v in row] for row in ws.iter_rows(values_only=True, max_row=LIMITE_LINHAS + 1)]
        return linhas, len(wb.worksheets)
    texto = conteudo.decode("utf-8-sig", errors="replace")
    try:
        dialeto = csv.Sniffer().sniff(texto[:2000], delimiters=";,\t")
    except csv.Error:
        dialeto = csv.excel
    return [[c.strip() for c in row] for row in csv.reader(io.StringIO(texto), dialeto)][: LIMITE_LINHAS + 1], 1


@router.post("/planilha")
def importar_planilha(arquivo: UploadFile, user: CurrentUser = Depends(get_current_user)) -> dict:
    """.xlsx ou .csv: uma linha por processo. Com cabecalho (numero/processo/cnj, tipo, descricao/partes) as
    colunas sao achadas pelo nome; sem cabecalho vale numero, tipo, descricao nessa ordem. Nao grava nada."""
    nome = arquivo.filename or ""
    if not nome.lower().endswith((".xlsx", ".xlsm", ".csv")):
        raise HTTPException(422, "Envie uma planilha .xlsx ou .csv")
    conteudo = arquivo.file.read(LIMITE_BYTES + 1)
    if len(conteudo) > LIMITE_BYTES:
        raise HTTPException(422, "Planilha grande demais (máximo 2 MB)")
    try:
        linhas, abas = _linhas(nome, conteudo)
        linhas = [l for l in linhas if any(l)]
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Planilha de processos ilegivel: %s", e)
        raise HTTPException(422, "Não consegui ler a planilha. Confira se o arquivo é .xlsx ou .csv válido.")
    if not linhas:
        raise HTTPException(422, "A planilha está vazia")
    mapa = _cabecalho(linhas[0])
    inicio = 1 if mapa else 0
    mapa = mapa or {"numero": 0, "tipo": 1, "descricao": 2}
    if len(linhas) - inicio > LIMITE_LINHAS:
        raise HTTPException(422, f"Planilha com mais de {LIMITE_LINHAS} processos")

    def celula(linha: list[str], chave: str) -> str:
        i = mapa.get(chave)
        return linha[i] if i is not None and i < len(linha) else ""

    saida, vistos = [], set()
    for n, linha in enumerate(linhas[inicio:], start=inicio + 1):
        item = _dados(celula(linha, "numero"))
        if item["valido"] and item["numero"] in vistos:
            item = {"valido": False, "numero": item["numero"], "erro": "Número repetido na planilha"}
        vistos.add(item["numero"])
        saida.append({
            "linha": n, **item,
            # tipo so' vai se for texto curto de verdade; vazio deixa o padrao "Processo"
            "tipo": celula(linha, "tipo")[:80], "descricao": celula(linha, "descricao")[:500],
        })
    aviso = f"A planilha tem {abas} abas; só a primeira foi lida." if abas > 1 else ""
    return {"aviso": aviso, "processos": saida, "validos": sum(1 for p in saida if p["valido"]), "invalidos": sum(1 for p in saida if not p["valido"])}
