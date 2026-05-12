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
        self._msal_app: msal.ConfidentialClientApplication | None = None

    def _get_msal_app(self) -> msal.ConfidentialClientApplication:
        if self._msal_app is None:
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
                    "Credenciais Azure ausentes: "
                    + ", ".join(missing)
                )
            self._msal_app = msal.ConfidentialClientApplication(
                settings.azure_client_id,
                authority=f"https://login.microsoftonline.com/{settings.azure_tenant_id}",
                client_credential=settings.azure_client_secret,
            )
        return self._msal_app

    async def _get_access_token(self) -> str:
        """Get OAuth2 token using client credentials flow with MSAL cache."""
        app = self._get_msal_app()

        # MSAL handles token caching and refresh automatically
        result = app.acquire_token_silent(scopes=self.SCOPES, account=None)
        if not result:
            result = app.acquire_token_for_client(scopes=self.SCOPES)

        if "access_token" not in result:
            error = result.get("error_description", "Unknown error")
            raise RuntimeError(f"Failed to acquire Azure token: {error}")

        return result["access_token"]

    def _build_recipients(self, to_email: str, to_name: str) -> list[dict]:
        """Build recipient list supporting comma-separated emails."""
        emails = [e.strip() for e in to_email.split(",") if e.strip()]
        return [
            {"emailAddress": {"address": email, "name": to_name}}
            for email in emails
        ]

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
                        '<div style="font-family: Segoe UI, Tahoma, sans-serif; max-width: 600px;">'
                        '<div style="background-color: #1A3C34; padding: 24px 32px; border-radius: 8px 8px 0 0;">'
                        '<span style="font-family: Lexend Zetta, sans-serif; color: #FFFFFF; font-size: 18px; '
                        'font-weight: 500; letter-spacing: 2px;">Carvalho &amp; Furtado</span>'
                        '<br><span style="font-family: Lexend Zetta, sans-serif; color: rgba(255,255,255,0.8); '
                        'font-size: 10px; letter-spacing: 6px;">ADVOGADOS</span>'
                        "</div>"
                        '<div style="padding: 32px; border: 1px solid #D7D1CA; border-top: none; border-radius: 0 0 8px 8px;">'
                        f"<p>Prezado(a) {to_name},</p>"
                        "<p>Segue em anexo o Contrato de Honorários para sua conferência.</p>"
                        "<p>Após a conferência, o documento será encaminhado para assinatura "
                        "digital via DocuSeal.</p>"
                        '<p style="margin-top: 24px;">Atenciosamente,<br>'
                        '<strong style="color: #1A3C34;">Carvalho &amp; Furtado Advogados</strong></p>'
                        "</div>"
                        '<div style="text-align: center; padding: 16px; color: #7A6755; font-size: 11px;">'
                        "Este e-mail e seu conteúdo são confidenciais."
                        "</div>"
                        "</div>"
                    ),
                },
                "toRecipients": self._build_recipients(to_email, to_name),
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

    async def send_html_email(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        html_content: str,
    ) -> dict:
        """Send a plain HTML email without attachments."""
        token = await self._get_access_token()

        email_body = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": html_content},
                "toRecipients": self._build_recipients(to_email, to_name),
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
            logger.info("HTML email sent to %s", to_email)
            return {"success": True}

        logger.error("Failed to send HTML email: %s %s", response.status_code, response.text)
        return {"success": False, "error": f"{response.status_code} - {response.text}"}

    async def send_html_email_with_attachment(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        html_content: str,
        attachment_path: str,
        attachment_name: str | None = None,
    ) -> dict:
        """Send an HTML email with a file attachment."""
        token = await self._get_access_token()

        file_path = Path(attachment_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Attachment file not found: {attachment_path}")

        display_name = attachment_name or file_path.name

        with open(file_path, "rb") as f:
            file_content = base64.b64encode(f.read()).decode("utf-8")

        email_body = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": html_content},
                "toRecipients": self._build_recipients(to_email, to_name),
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
            logger.info("HTML email with attachment sent to %s", to_email)
            return {"success": True}

        logger.error("Failed to send HTML email with attachment: %s %s", response.status_code, response.text)
        return {"success": False, "error": f"{response.status_code} - {response.text}"}
