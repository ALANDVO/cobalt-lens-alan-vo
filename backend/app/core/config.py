from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "cobalt-lens"
    environment: str = "development"
    debug: bool = True

    # Database
    database_url: str = "sqlite:///./cobalt_lens.db"

    # API
    api_prefix: str = "/api/v1"
    host: str = "127.0.0.1"
    port: int = 8000

    # Parser
    max_file_size_mb: int = 10
    parse_timeout_seconds: int = 30

    # LLM (optional, opt-in)
    llm_api_key: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None

    # Auth (future)
    oidc_issuer_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None

    @property
    def database_path(self) -> Path:
        if self.database_url.startswith("sqlite:///"):
            return Path(self.database_url.replace("sqlite:///", ""))
        return Path("./cobalt_lens.db")


settings = Settings()