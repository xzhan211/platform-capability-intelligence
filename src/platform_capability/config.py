from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PCI_", env_file=".env", extra="ignore")

    max_evidence_tokens: int = 60_000
    max_snippet_lines: int = 40
    max_archive_size_mb: int = 200
    max_file_count: int = 5000
    llm_provider: str = "mock"          # mock | bedrock
    llm_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    llm_max_retry: int = 2
    output_dir: str = "./output"
    log_level: str = "INFO"

    ignored_dirs: list[str] = [
        ".git", "__pycache__", ".venv", "venv", "env",
        "node_modules", "build", "dist", "target", ".idea", ".vscode",
        ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ]

    ignored_extensions: list[str] = [
        ".pyc", ".pyo", ".class", ".jar", ".war", ".so", ".dylib",
        ".png", ".jpg", ".gif", ".ico", ".pdf", ".zip", ".tar",
    ]


settings = Settings()
