from __future__ import annotations
 
import base64
import logging
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
                f"{self.base_url}/templates",
                json=payload,
                headers=self._headers(),
                timeout=60.0,
            )
 
        if response.status_code in (200, 201):
            template_data = response.json()
            logger.info("DocuSeal template created: %s", template_data.get("id"))
            return template_data
 
        logger.error("Failed to create template: %s %s", response.status_code, response.text)
        raise RuntimeError(f"DocuSeal template creation failed: {response.status_code}")
 
    async def send_for_signature(
        self,
        template_id: int,
        signatarios: list[dict[str, str]],
        send_email: bool = True,
    ) -> dict:
        """Create a submission (send for signing) from a template.
 
        signatarios: list of {"email": "...", "name": "...", "role": "..."}
        """
        submitters = []
        for sig in signatarios:
            submitters.append(
                {
                    "email": sig["email"],
                    "name": sig.get("name", ""),
                    "role": sig.get("role", "Contratante"),
                    "send_email": send_email,
                }
            )
 
        payload = {
            "template_id": template_id,
            "send_email": send_email,
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
            return {
                "success": True,
                "submission": submission_data,
                "message": "Documento enviado para assinatura com sucesso",
            }
 
        logger.error("Failed to create submission: %s %s", response.status_code, response.text)
        return {
            "success": False,
            "message": f"Erro ao enviar para assinatura: {response.status_code} - {response.text}",
        }
 
    async def get_submission_status(self, submission_id: int) -> dict:
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