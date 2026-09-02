import logging
import os
from pathlib import Path

from pydantic_settings import BaseSettings

_config_logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    # App registration do LOGIN (audience dos tokens do frontend).
    # azure_client_id/secret ficam pro e-mail via Graph; sem esse split,
    # trocar as credenciais de e-mail derruba a validacao de JWT (401).
    azure_auth_client_id: str = ""
    azure_sender_email: str = ""
    graph_user_email: str = ""

    @property
    def sender_email(self) -> str:
        return self.graph_user_email or self.azure_sender_email
    azure_email_connection_string: str = ""

    docuseal_api_key: str = ""
    docuseal_base_url: str = "https://api.docuseal.com"

    # Varredura de portugues/padrao do contrato antes da geracao (Step7).
    # DeepSeek expoe endpoint compativel com a API da Anthropic.
    deepseek_api_key: str = ""
    deepseek_api_base: str = "https://api.deepseek.com/anthropic"
    # deepseek-v4-pro (thinking mode) pega erros de portugues que o deepseek-chat
    # (sem thinking) deixa passar em testes reais — ver contract_reviewer.py.
    deepseek_model: str = "deepseek-v4-pro"

    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    # Quem pode usar o contrato de Acao de Consumo (aerea). Lista de e-mails
    # separados por virgula; admin sempre pode. Vazio = so' admin.
    consumidor_emails: str = os.getenv("CONSUMIDOR_EMAILS", "")

    financeiro_email: str = os.getenv("FINANCEIRO_EMAIL", "financeiro@carvalhofurtadoadv.com.br,gabriel@carvalhofurtadoadv.com.br")

    cf_signer_email: str = os.getenv("CF_SIGNER_EMAIL", "contrato@carvalhofurtadoadv.com.br")

    # Testemunha 1 fixa (financeiro) injetada em toda submissao p/ assinatura.
    # Email unico (financeiro_email pode ser lista, nao serve p/ submitter DocuSeal).
    testemunha1_nome: str = os.getenv("TESTEMUNHA1_NOME", "Lilian Siqueira")
    testemunha1_email: str = os.getenv("TESTEMUNHA1_EMAIL", "financeiro@carvalhofurtadoadv.com.br")

    bank_account_info: str = os.getenv(
        "BANK_ACCOUNT_INFO",
        "Banco Inter, agência 0001, conta corrente 17841983-4, ou chave Pix (CNPJ) 25463159000173",
    )

    template_path: str = "templates/timbrado_peticao_1.dotx"
    output_dir: str = "generated_contracts"

    # Modo dev: aceita header X-Dev-User-Email/Role no lugar do JWT Azure AD.
    # NUNCA habilitar em produção.
    dev_mode: bool = False

    # NFS-e BH (financeiro)
    nfse_enabled: bool = False
    nfse_kek: str = ""                       # base64 32 bytes (AES-GCM)
    nfse_worker_token: str = ""              # bearer p/ worker GH Actions
    nfse_backfill_days: int = 90
    nfse_gh_actions_cidrs: str = ""          # CSV, opcional (allowlist)

    model_config = {"env_file": str(ENV_FILE), "env_file_encoding": "utf-8"}

    def validate_critical(self) -> None:
        missing = []
        if not self.azure_tenant_id:
            missing.append("AZURE_TENANT_ID")
        if not self.azure_client_id:
            missing.append("AZURE_CLIENT_ID")
        if not self.azure_client_secret:
            missing.append("AZURE_CLIENT_SECRET")
        if self.nfse_enabled:
            if not self.nfse_kek:
                missing.append("NFSE_KEK")
            if not self.nfse_worker_token:
                missing.append("NFSE_WORKER_TOKEN")
        if missing:
            _config_logger.warning(
                "Variáveis de configuração críticas não definidas: %s",
                ", ".join(missing),
            )


settings = Settings()
settings.validate_critical()
