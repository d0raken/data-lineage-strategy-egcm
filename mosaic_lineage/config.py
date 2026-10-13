"""Configuration management for Mosaic Lineage Extractor."""

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Optional


def load_dotenv(filepath: Optional[str] = None) -> None:
    """Carrega variáveis de um arquivo .env se existir."""
    target_path = Path(filepath) if filepath else Path.cwd() / ".env"
    if not target_path.is_file():
        return
    with open(target_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            k, v = stripped.split("=", 1)
            k = k.strip()
            v = v.strip().strip("\"'")
            if k and k not in os.environ:
                os.environ[k] = v


# Carrega automaticamente ao importar config
load_dotenv()


@dataclass
class Config:
    """Configurações de conexão e execução."""
    base_url: str = field(default_factory=lambda: os.getenv("MSTR_BASE_URL", ""))
    username: str = field(default_factory=lambda: os.getenv("MSTR_USERNAME", ""))
    password: str = field(default_factory=lambda: os.getenv("MSTR_PASSWORD", ""))
    project_id: Optional[str] = field(default_factory=lambda: os.getenv("MSTR_PROJECT_ID"))
    project_name: Optional[str] = field(default_factory=lambda: os.getenv("MSTR_PROJECT_NAME"))
    data_model_id: Optional[str] = field(default_factory=lambda: os.getenv("MSTR_DATA_MODEL_ID"))
    export_format: str = field(default_factory=lambda: os.getenv("MSTR_EXPORT_FORMAT", "json"))
    output_dir: str = field(default_factory=lambda: os.getenv("MSTR_OUTPUT_DIR", "./output"))
    ssl_verify: bool = field(
        default_factory=lambda: os.getenv("MSTR_SSL_VERIFY", "true").lower() in ("1", "true", "yes")
    )

    def validate(self, require_model_id: bool = False) -> None:
        """Valida se campos essenciais estão preenchidos."""
        if not self.base_url:
            raise ValueError("MSTR_BASE_URL é obrigatório.")
        if not self.username:
            raise ValueError("MSTR_USERNAME é obrigatório.")
        if not self.password:
            raise ValueError("MSTR_PASSWORD é obrigatório.")
        if not self.project_id and not self.project_name:
            raise ValueError("MSTR_PROJECT_ID é obrigatório.")
        if require_model_id and not self.data_model_id:
            raise ValueError("data_model_id é obrigatório para extração de modelo específico.")
