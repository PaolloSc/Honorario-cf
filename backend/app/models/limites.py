"""Limite de tamanho dos textos que chegam pela API (evita 500 por coluna VARCHAR estourada)."""
from pydantic import BaseModel, model_validator

LIMITE_TEXTO = 20_000  # qualquer campo de texto (cláusulas, descrições, etc.)
LIMITE_CURTO = 256  # nomes e e-mails: o banco guarda client_name/client_email em VARCHAR(256)


def _curto(chave: str) -> bool:
    return chave in ("nome", "razao_social") or chave.endswith("_nome") or chave.startswith("email") or chave.endswith("_email")


def _checar(valor, caminho: str, chave: str = "") -> None:
    if isinstance(valor, str):
        limite = LIMITE_CURTO if _curto(chave) else LIMITE_TEXTO
        if len(valor) > limite:
            raise ValueError(f"O campo {caminho} tem {len(valor)} caracteres; o máximo é {limite}.")
    elif isinstance(valor, dict):
        for k, v in valor.items():
            _checar(v, f"{caminho}.{k}" if caminho else str(k), str(k))
    elif isinstance(valor, (list, tuple)):
        for i, v in enumerate(valor):
            _checar(v, f"{caminho}.{i}", chave)


class LimiteTamanhos(BaseModel):
    """Mixin: recusa (422) texto acima do limite em qualquer campo do pedido."""

    @model_validator(mode="after")
    def _limite_de_tamanho(self):
        _checar(self.model_dump(mode="json"), "")
        return self
