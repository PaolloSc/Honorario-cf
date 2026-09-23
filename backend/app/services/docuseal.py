from __future__ import annotations
 
import base64
import logging
import re
from pathlib import Path
 
import httpx
 
from app.config import settings
 
logger = logging.getLogger(__name__)
 
 
class DocuSealService:
    """Integration with DocuSeal API for digital signatures."""
 
    def __init__(self) -> None:
        self.base_url = settings.docuseal_base_url.rstrip("/")
        self.api_key = settings.docuseal_api_key
 
    def _headers(self) -> dict[str, str]:
        return {
            "X-Auth-Token": self.api_key,
            "Content-Type": "application/json",
        }
 
    async def create_template_from_docx(self, filepath: str, name: str) -> dict:
        """Upload a DOCX file and create a DocuSeal template."""
        file_path = Path(filepath)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
 
        with open(file_path, "rb") as f:
            file_content = base64.b64encode(f.read()).decode("utf-8")
 
        payload = {
            "name": name,
            "documents": [
                {
                    "name": file_path.stem,
                    "file": f"data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,{file_content}",
                }
            ],
        }
 
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/templates/docx",
                json=payload,
                headers=self._headers(),
                timeout=60.0,
            )
 
        if response.status_code in (200, 201):
            template_data = response.json()
            logger.info("DocuSeal template created: %s", template_data.get("id"))
            return template_data
 
        logger.error("Failed to create template: %s %s", response.status_code, response.text)
        raise RuntimeError(f"DocuSeal template creation failed: {response.status_code} - {response.text}")
 
    async def send_for_signature(
        self,
        template_id: int,
        signatarios: list[dict[str, str]],
        send_email: bool = True,
    ) -> dict:
        """Create a submission (send for signing) from a template.
 
        signatarios: list of {"email": "...", "name": "...", "role": "..."}
        """
        submitters = [_submitter(sig, send_email) for sig in signatarios]
 
        payload = {
            "template_id": template_id,
            "send_email": send_email,
            "order": "preserved",
            "submitters": submitters,
        }
 
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/submissions",
                json=payload,
                headers=self._headers(),
                timeout=30.0,
            )
 
        if response.status_code in (200, 201):
            submission_data = response.json()
            logger.info("DocuSeal submission created: %s", submission_data)

            # DocuSeal returns a list of submitters or a single object
            if isinstance(submission_data, list):
                # Extract submission_id from first submitter
                first = submission_data[0] if submission_data else {}
                submission_obj = {
                    "id": first.get("submission_id") or first.get("id"),
                    "submitters": submission_data,
                }
            else:
                submission_obj = submission_data

            return {
                "success": True,
                "submission": submission_obj,
                "message": "Documento enviado para assinatura com sucesso",
            }
 
        logger.error("Failed to create submission: %s %s", response.status_code, response.text)
        return {
            "success": False,
            "message": f"Erro ao enviar para assinatura: {response.status_code} - {response.text}",
        }
 
    async def get_submission_status(self, submission_id: int | str) -> dict:
        """Check the status of a submission."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/submissions/{submission_id}",
                headers=self._headers(),
                timeout=15.0,
            )
 
        if response.status_code == 200:
            return response.json()
 
        raise RuntimeError(f"Failed to get submission: {response.status_code}")


def link_assinatura(base_url: str, slug: str) -> str:
    """Link da tela de assinatura de um signatario.

    O GET /submissions/{id} traz so' o `slug` (o `embed_src` vem apenas na
    criacao). A tela fica no mesmo servidor da API, sem o "api." do DocuSeal
    em nuvem (api.docuseal.com -> docuseal.com) ou sem o "/api" do auto-hospedado.
    """
    if not slug:
        return ""
    base = base_url.rstrip("/")
    if base.endswith("/api"):
        base = base[: -len("/api")]
    base = base.replace("://api.", "://", 1)
    return f"{base}/s/{slug}"


def telefone_e164(numero: str | None) -> str | None:
    """Celular/telefone brasileiro no formato do DocuSeal e do wa.me (+55DDDNUMERO).

    Aceita com ou sem mascara e com ou sem o 55. Numero incompleto vira None
    em vez de ir errado para o DocuSeal.
    """
    digitos = re.sub(r"\D", "", numero or "")
    if len(digitos) in (10, 11):
        digitos = "55" + digitos
    if len(digitos) not in (12, 13) or not digitos.startswith("55"):
        return None
    return "+" + digitos


def _submitter(sig: dict, send_email: bool) -> dict:
    """Um signatario da submissao. O WhatsApp vai como `phone` (o DocuSeal so
    manda SMS quando pedido) e volta na consulta, para a tela montar o envio."""
    submitter = {
        "email": sig["email"],
        "name": sig.get("name", ""),
        "role": sig.get("role", "Contratante"),
        "send_email": send_email,
        "order": sig.get("order", 1),
    }
    telefone = telefone_e164(sig.get("phone"))
    if telefone:
        submitter["phone"] = telefone
    return submitter
