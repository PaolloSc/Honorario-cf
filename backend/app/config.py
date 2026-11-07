import logging
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
    # Medido em 05/11/2026 (texto de ~15 campos, 7 erros plantados): v4-pro com thinking
    # levou ~125s e estourou max_tokens sem devolver nada (0 achados); v4-flash sem thinking
    # levou ~6,6s e achou os 7. Thinking so' se DEEPSEEK_THINKING=true.
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_thinking: bool = False

    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    # Quem pode usar o contrato de Acao de Consumo (aerea). Lista de e-mails
    # separados por virgula; admin sempre pode. Vazio = so' admin.
    consumidor_emails: str = ""

    # Dados do escritorio: sem valor padrao no codigo (nada de dado pessoal aqui).
    # Em producao sao obrigatorios (ver ESSENCIAIS_PRODUCAO).
    financeiro_email: str = ""        # lista separada por virgula
    cf_signer_email: str = ""
    # Testemunha 1 fixa (financeiro) injetada em toda submissao p/ assinatura.
    # Email unico (financeiro_email pode ser lista, nao serve p/ submitter DocuSeal).
    # O nome vem do cadastro de colaboradores; este e' so' a reserva.
    testemunha1_nome: str = ""
    testemunha1_email: str = ""
    bank_account_info: str = ""       # conta/Pix que aparece na clausula de pagamento

    # Segredo do aviso (webhook) do DocuSeal. Sem ele todo aviso da' 403.
    docuseal_webhook_secret: str = ""

    # Banco: vazio = SQLite local (honorarios.db), so' para desenvolvimento.
    database_url: str = ""

    # Legal One (so' leitura). Sem credenciais, a busca de partes fica desligada.
    legalone_api_client_id: str = ""
    legalone_api_client_secret: str = ""
    legalone_api_token_url: str = "https://api.thomsonreuters.com/legalone/oauth?grant_type=client_credentials"
    legalone_api_base: str = "https://api.thomsonreuters.com/legalone/v1/api/rest"

    # A Vercel define VERCEL_ENV=production no deploy de producao (e no homolog,
    # que tambem roda como producao). E' o que liga a checagem estrita.
    vercel_env: str = ""

    template_path: str = "templates/timbrado_peticao_1.dotx"
    output_dir: str = "generated_contracts"

    # Modo dev: aceita header X-Dev-User-Email/Role no lugar do JWT Azure AD.
    # NUNCA habilitar em produção.
    dev_mode: bool = False

    # Link de convidado sem login: /convite/<token> no frontend. Mesmo valor nos
    # dois projetos Vercel. Vazio = desligado; trocar o valor revoga o link.
    convite_token: str = ""
    # Perfil de quem entra pelo link (admin | advogado | financeiro | leitor).
    convite_role: str = "admin"

    # NFS-e BH (financeiro)
    nfse_enabled: bool = False
    nfse_kek: str = ""                       # base64 32 bytes (AES-GCM)
    nfse_worker_token: str = ""              # bearer p/ worker GH Actions
    nfse_backfill_days: int = 90
    # Trava da emissao: so 'homologacao' (producao restrita) ate alguem ligar de proposito.
    nfse_emissao_producao_permitida: bool = False
    nfse_gh_actions_cidrs: str = ""          # CSV, opcional (allowlist)

    model_config = {"env_file": str(ENV_FILE), "env_file_encoding": "utf-8"}

    def faltando(self) -> list[str]:
        """Nomes das variaveis essenciais sem valor."""
        missing = [nome for nome, campo in ESSENCIAIS if not getattr(self, campo)]
        if self.vercel_env == "production":
            missing += [nome for nome, campo in ESSENCIAIS_PRODUCAO if not getattr(self, campo)]
        if self.nfse_enabled:
            missing += [n for n, c in (("NFSE_KEK", "nfse_kek"), ("NFSE_WORKER_TOKEN", "nfse_worker_token"))
                        if not getattr(self, c)]
        return missing

    def validate_critical(self) -> None:
        """Em producao, nao sobe sem o essencial; fora dela, so' avisa."""
        missing = self.faltando()
        if not missing:
            return
        if self.vercel_env == "production":
            raise RuntimeError("Configuração essencial ausente em produção: " + ", ".join(missing))
        _config_logger.warning(
            "Variáveis de configuração críticas não definidas: %s",
            ", ".join(missing),
        )


ESSENCIAIS = (
    ("AZURE_TENANT_ID", "azure_tenant_id"),
    ("AZURE_CLIENT_ID", "azure_client_id"),
    ("AZURE_CLIENT_SECRET", "azure_client_secret"),
)
# So' cobradas em producao: em dev/teste o SQLite e o DocuSeal desligado bastam.
ESSENCIAIS_PRODUCAO = (
    ("DATABASE_URL", "database_url"),
    ("DOCUSEAL_API_KEY", "docuseal_api_key"),
    ("DOCUSEAL_WEBHOOK_SECRET", "docuseal_webhook_secret"),
    ("FINANCEIRO_EMAIL", "financeiro_email"),
    ("CF_SIGNER_EMAIL", "cf_signer_email"),
    ("TESTEMUNHA1_NOME", "testemunha1_nome"),
    ("TESTEMUNHA1_EMAIL", "testemunha1_email"),
    ("BANK_ACCOUNT_INFO", "bank_account_info"),
)


settings = Settings()
settings.validate_critical()
