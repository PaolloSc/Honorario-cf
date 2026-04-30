from pathlib import Path

from pydantic_settings import BaseSettings

BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    azure_sender_email: str = ""
    graph_user_email: str = ""

    @property
    def sender_email(self) -> str:
        return self.graph_user_email or self.azure_sender_email
    azure_email_connection_string: str = ""

    docuseal_api_key: str = ""
    docuseal_base_url: str = "https://api.docuseal.com"

    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    template_path: str = "templates/timbrado_peticao_1.dotx"
    output_dir: str = "generated_contracts"

    model_config = {"env_file": str(ENV_FILE), "env_file_encoding": "utf-8"}


settings = Settings()
