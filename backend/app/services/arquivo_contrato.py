"""Arquivo (DOCX) de uma versao do contrato: onde esta e, se o disco efemero o perdeu, como refazer.

Modulo de servico: nao conhece HTTP. Quem chama traduz ArquivoNaoEncontrado em 404.
Download, envio para assinatura e e-mail usam este resolvedor, sempre com a versao.

Regras de nome: cada versao tem `contrato_<id>_v<N>.docx`. O nome generico `contrato_<id>.docx`
e' o que o gerador grava para a versao mais nova (e contratos antigos apontam varias versoes
para ele); so serve para a versao atual. Refazer um arquivo nunca grava por cima do nome
generico, e o DOCX provisorio ("em processamento") nunca e' gravado como arquivo da versao.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, settings
from app.database import ContractDB, ContractVersionDB
from app.models.contrato_consumidor import TIPO_CONSUMIDOR_AEREO
from app.models.documentos_complementares import ROTULO_DOCUMENTO
from app.services.contrato_carregado import TIPO_HONORARIOS, carregar_versao

logger = logging.getLogger(__name__)


class ArquivoNaoEncontrado(Exception):
    """Nenhuma estrategia achou nem conseguiu refazer o arquivo do contrato."""

    def __init__(self, contract_id: str):
        super().__init__(f"Contract file not found: {contract_id}")
        self.contract_id = contract_id


class VersaoNaoEncontrada(ArquivoNaoEncontrado):
    """A versao pedida nao existe."""

    def __init__(self, contract_id: str, versao: int):
        super().__init__(contract_id)
        self.versao = versao


def resolve_backend_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return BACKEND_DIR / path


def _provisorio(output_dir: Path, contract_id: str) -> Path:
    """DOCX de aviso, com nome proprio e sem registro no banco: so para o download."""
    from docx import Document

    doc = Document()
    doc.add_paragraph("Contrato em processamento - documento sera regenerado.")
    caminho = output_dir / f"contrato_{contract_id}_provisorio.docx"
    doc.save(str(caminho))
    return caminho


def resolver_arquivo(
    contract_id: str,
    db: Session,
    versao: int | None = None,
    *,
    provisorio: bool = False,
) -> Path:
    """Acha o DOCX da versao (a mais nova, se `versao` nao vier); refaz do banco se o disco o perdeu.

    `provisorio=True` (so o download) devolve um aviso "em processamento" quando nem o modelo
    esta disponivel; sem isso, ArquivoNaoEncontrado.
    """
    output_dir = resolve_backend_path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    consulta = db.query(ContractVersionDB).filter(ContractVersionDB.contract_id == contract_id)
    if versao is not None:
        ver = consulta.filter(ContractVersionDB.version_number == versao).first()
        if ver is None:
            raise VersaoNaoEncontrada(contract_id, versao)
    else:
        ver = consulta.order_by(ContractVersionDB.version_number.desc()).first()

    contract = db.query(ContractDB).filter(ContractDB.contract_id == contract_id).first()
    atual = contract.current_version if contract else (ver.version_number if ver else None)
    eh_atual = ver is None or ver.version_number == atual

    generico = output_dir / f"contrato_{contract_id}.docx"
    proprio = output_dir / f"contrato_{contract_id}_v{ver.version_number}.docx" if ver else None

    candidatos: list[Path] = []
    if ver and ver.file_path:
        guardado = Path(ver.file_path)
        # Contratos antigos: varias versoes apontam para o generico, que so tem o texto da mais nova.
        if guardado.name != generico.name or eh_atual:
            candidatos += [guardado, output_dir / guardado.name]
    if proprio:
        candidatos.append(proprio)
    if eh_atual:
        candidatos.append(generico)
    for c in candidatos:
        if c.exists():
            return c

    if ver and ver.form_data_json:
        logger.warning("Arquivo do contrato %s v%s fora do disco; refazendo do banco.", contract_id, ver.version_number)
        try:
            carregado = carregar_versao(ver)
            _, novo = carregado.gerador.generate(carregado.request, contract_id=contract_id, nome_arquivo=proprio.name)
            ver.file_path = str(novo)
            db.commit()
            return Path(novo)
        except FileNotFoundError as sem_modelo:  # disco efemero sem o modelo .docx
            logger.warning("Modelo do contrato indisponivel: %s", sem_modelo)
            if provisorio:
                return _provisorio(output_dir, contract_id)
        except Exception as e:
            logger.error("Falha ao refazer o contrato %s: %s", contract_id, e)

    logger.error("Arquivo do contrato %s nao encontrado (guardado=%s)", contract_id, ver.file_path if ver else "N/A")
    raise ArquivoNaoEncontrado(contract_id)


_FILENAME_BAD = re.compile(r'[\r\n\t/\\:*?"<>|]+')


def _parte_do_nome(name: str) -> str:
    """Sanitiza um trecho vindo do usuário para uso em nome de arquivo/anexo."""
    cleaned = " ".join(_FILENAME_BAD.sub(" ", name).split())
    return cleaned[:120].strip()


def nome_do_anexo(
    client_name: str | None, contract_id: str, tipo: str = TIPO_HONORARIOS
) -> str:
    """Nome do anexo: o cliente precisa reconhecer o contrato pelo arquivo."""
    consumidor = tipo == TIPO_CONSUMIDOR_AEREO
    rotulo = ROTULO_DOCUMENTO.get(
        tipo, "Contrato de Prestação de Serviços" if consumidor else "Contrato Honorários"
    )
    generico = f"contrato_{'servicos' if consumidor else 'honorarios'}_{contract_id}.docx"

    nome = _parte_do_nome(client_name) if client_name else ""
    return f"{rotulo} — {nome}.docx" if nome else generico
