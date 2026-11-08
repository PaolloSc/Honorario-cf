"""Ciclo de vida do contrato: criar, nova versao, reverter e auditoria, num lugar so.

Modulo de servico, sem HTTP. As rotas decidem permissao e traduzem erros; aqui ficam as
regras que antes estavam copiadas em contract.py, contracts.py e substabelecimento_vinculado.py:

- numeracao e nome do arquivo: cada versao tem `contrato_<id>_v<N>.docx`; o gerador grava
  sempre no nome generico, entao antes de gerar a proxima versao o arquivo da atual e'
  preso ao nome proprio (`preparar_versao`);
- nada de .docx sem registro: se o banco nao grava, os arquivos criados saem (`confirmar`),
  e o arquivo da versao anterior volta como estava;
- "travado": enviado ou assinado agora; nao se grava por cima;
- auditoria: `registrar_auditoria`.

Fluxo de uma nova versao: `preparar_versao` (gera) -> `gravar_versao` (linhas) -> `confirmar`.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.database import AuditLogDB, ContractDB, ContractVersionDB, serialize_cliente_docs, utcnow


STATUS_TRAVADOS = ("enviado", "assinado")


def travado(contract: ContractDB) -> bool:
    """Enviado para assinatura ou assinado AGORA: nao se grava por cima.

    So o estado atual conta: "Cancelar envio" arquiva a submissao e volta a rascunho.
    """
    return contract.status in STATUS_TRAVADOS


def registrar_auditoria(
    db: Session,
    contract_id: str,
    action: str,
    detail: str = "",
    versao: int | None = None,
    user_email: str = "",
) -> None:
    db.add(AuditLogDB(
        contract_id=contract_id,
        action=action,
        detail=detail,
        version_number=versao,
        user_email=user_email,
        created_at=utcnow(),
    ))


@dataclass
class Arquivos:
    """O que uma operacao criou ou preservou no disco, para desfazer se o banco nao gravar."""

    novos: list[str] = field(default_factory=list)
    congelados: list[tuple[Path, Path]] = field(default_factory=list)  # (original, copia)

    def desfazer(self) -> None:
        for f in self.novos:
            Path(f).unlink(missing_ok=True)
        for original, copia in self.congelados:
            # o gerador sobrescreve o original no lugar: devolve a ele o conteudo da versao anterior
            if copia.exists():
                shutil.copyfile(copia, original)
                copia.unlink(missing_ok=True)
        self.novos.clear()
        self.congelados.clear()


def confirmar(db: Session, arquivos: Arquivos) -> None:
    """Commit; se falhar, desfaz o banco e o disco e repete o erro."""
    try:
        db.commit()
    except Exception:
        db.rollback()
        arquivos.desfazer()
        raise


def _arquivo_da_versao(filepath: str | Path, contract_id: str, versao: int) -> str:
    """Copia o DOCX para um nome proprio da versao (o gerador reaproveita sempre o mesmo nome)."""
    origem = Path(filepath)
    destino = origem.with_name(f"contrato_{contract_id}_v{versao}.docx")
    if origem != destino:
        shutil.copyfile(origem, destino)
    return str(destino)


def _congelar_versao_atual(db: Session, contract: ContractDB, arquivos: Arquivos) -> None:
    ver = (
        db.query(ContractVersionDB)
        .filter(
            ContractVersionDB.contract_id == contract.contract_id,
            ContractVersionDB.version_number == contract.current_version,
        )
        .first()
    )
    if ver and ver.file_path and Path(ver.file_path).exists():
        original = Path(ver.file_path)
        ver.file_path = _arquivo_da_versao(original, contract.contract_id, ver.version_number)
        if Path(ver.file_path) != original:
            arquivos.congelados.append((original, Path(ver.file_path)))


@dataclass
class VersaoPreparada:
    numero: int
    arquivo: str  # ja no nome proprio da versao


def preparar_versao(
    db: Session, contract: ContractDB, gerador: Any, request: Any, arquivos: Arquivos
) -> VersaoPreparada:
    """Prende o arquivo da versao atual, gera o DOCX da proxima e o poe no nome dela.

    Se a geracao falhar, desfaz o que fez (inclusive o arquivo preso) e repete o erro.
    """
    _congelar_versao_atual(db, contract, arquivos)
    try:
        _, caminho = gerador.generate(request, contract_id=contract.contract_id)
    except Exception:
        db.rollback()  # o file_path alterado em memoria nao pode ir ao banco
        arquivos.desfazer()
        raise
    numero = contract.current_version + 1
    arquivo = _arquivo_da_versao(caminho, contract.contract_id, numero)
    arquivos.novos.append(arquivo)
    return VersaoPreparada(numero=numero, arquivo=arquivo)


def gravar_versao(
    db: Session,
    contract: ContractDB,
    prep: VersaoPreparada,
    *,
    form_data_json: str,
    client_name: str,
    client_email: str,
    user_email: str,
    acao: str,
    detalhe: str,
) -> None:
    """Linhas da nova versao: versao, contrato (volta a rascunho) e auditoria. Sem commit."""
    db.add(ContractVersionDB(
        contract_id=contract.contract_id,
        version_number=prep.numero,
        form_data_json=form_data_json,
        file_path=prep.arquivo,
        created_by=user_email,
        created_at=utcnow(),
    ))
    contract.current_version = prep.numero
    contract.client_name = client_name
    contract.client_email = client_email
    contract.status = "rascunho"
    contract.updated_by = user_email
    contract.updated_at = utcnow()
    registrar_auditoria(db, contract.contract_id, acao, detalhe, prep.numero, user_email)


def criar(
    db: Session,
    arquivos: Arquivos,
    *,
    gerador: Any,
    request: Any,
    tipo: str,
    form_dict: dict,
    client_name: str,
    client_email: str,
    user_email: str,
    detalhe: str,
    contrato_origem_id: str | None = None,
    cliente_docs: str | None = None,
) -> tuple[str, str]:
    """Gera o DOCX e grava contrato, versao 1 e auditoria "criacao" (sem commit).

    Devolve (contract_id, arquivo). O arquivo fica em `arquivos` para sair se o banco falhar.
    """
    contract_id, arquivo = gerador.generate(request)
    arquivos.novos.append(arquivo)
    db.add(ContractDB(
        contract_id=contract_id,
        status="rascunho",
        client_name=client_name,
        client_email=client_email,
        tipo_contrato=tipo,
        contrato_origem_id=contrato_origem_id,
        current_version=1,
        created_by=user_email,
        updated_by=user_email,
        created_at=utcnow(),
        updated_at=utcnow(),
        cliente_docs=cliente_docs if cliente_docs is not None else serialize_cliente_docs(form_dict),
    ))
    db.flush()
    db.add(ContractVersionDB(
        contract_id=contract_id,
        version_number=1,
        form_data_json=json.dumps(form_dict, ensure_ascii=False),
        file_path=arquivo,
        created_by=user_email,
        created_at=utcnow(),
    ))
    registrar_auditoria(db, contract_id, "criacao", detalhe, 1, user_email)
    return contract_id, arquivo
