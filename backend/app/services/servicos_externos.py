"""Unico lugar que cria os clientes de e-mail e de assinatura (um por processo)."""
from __future__ import annotations

from app.services.azure_email import AzureEmailService
from app.services.docuseal import DocuSealService

_email_service: AzureEmailService | None = None
_docuseal_service: DocuSealService | None = None


def get_email_service() -> AzureEmailService:
    global _email_service
    if _email_service is None:
        _email_service = AzureEmailService()
    return _email_service


def get_docuseal_service() -> DocuSealService:
    global _docuseal_service
    if _docuseal_service is None:
        _docuseal_service = DocuSealService()
    return _docuseal_service
