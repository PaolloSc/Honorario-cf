from __future__ import annotations

import base64
import logging
from pathlib import Path

import httpx
import msal

from app.config import settings

logger = logging.getLogger(__name__)


class AzureEmailService:
    """Send emails via Microsoft Graph API (Outlook)."""

    GRAPH_API_URL = "https://graph.microsoft.com/v1.0"
    SCOPES = ["https://graph.microsoft.com/.default"]

    def __init__(self) -> None:
        self._token: str | None = None

    async def _get_access_token(self) -> str:
        """Get OAuth2 token using client credentials flow."""
        if self._token:
            return self._token

        missing = [
            name
            for name, value in (
                ("AZURE_TENANT_ID", settings.azure_tenant_id),
                ("AZURE_CLIENT_ID", settings.azure_client_id),
                ("AZURE_CLIENT_SECRET", settings.azure_client_secret),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Credenciais Azure ausentes em backend/.env: "
                + ", ".join(missing)
                + ". Verifique se o uvicorn esta carregando o .env correto."
            )

        app = msal.ConfidentialClientApplication(
            settings.azure_client_id,
            authority=f"https://login.microsoftonline.com/{settings.azure_tenant_id}",
            client_credential=settings.azure_client_secret,
        )

        result = app.acquire_token_for_client(scopes=self.SCOPES)

        if "access_token" not in result:
            error = result.get("error_description", "Unknown error")
            raise RuntimeError(f"Failed to acquire Azure token: {error}")

        self._token = result["access_token"]
        return self._token

    async def send_email_with_attachment(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        attachment_path: str,
        attachment_name: str | None = None,
    ) -> dict:
        """Send a contract as attachment via Outlook/Graph API."""
        token = await self._get_access_token()

        file_path = Path(attachment_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Contract file not found: {attachment_path}")

        display_name = attachment_name or file_path.name

        with open(file_path, "rb") as f:
            file_content = base64.b64encode(f.read()).decode("utf-8")

        email_body = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": (
                        f"<p>Prezado(a) {to_name},</p>"
                        "<p>Segue em anexo o Contrato de Honorarios para sua conferencia.</p>"
                        "<p>Apos a conferencia, o documento sera encaminhado para assinatura "
                        "digital via DocuSeal.</p>"
                        "<p>Atenciosamente,<br>"
                        "Carvalho & Furtado Advogados</p>"
                    ),
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": to_email,
                            "name": to_name,
                        }
                    }
                ],
                "attachments": [
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": display_name,
                        "contentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "contentBytes": file_content,
                    }
                ],
            },
            "saveToSentItems": "true",
        }

        url = f"{self.GRAPH_API_URL}/users/{settings.sender_email}/sendMail"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=email_body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

        if response.status_code == 202:
            logger.info("Email sent successfully to %s", to_email)
            return {"success": True, "message": "Email enviado com sucesso"}

        logger.error("Failed to send email: %s %s", response.status_code, response.text)
        return {
            "success": False,
            "error": f"Erro ao enviar email: {response.status_code} - {response.text}",
        }
