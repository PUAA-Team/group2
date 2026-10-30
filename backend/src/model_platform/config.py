import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    runtime_dir: Path = field(default_factory=lambda: Path(os.environ.get(
        "MT_RUNTIME_DIR") or "D:/model-training-demo/backend-runtime"))
    database_url: str | None = field(default_factory=lambda: os.environ.get("MT_DATABASE_URL"))
    allowed_origins: tuple[str, ...] = field(default_factory=lambda: tuple(
        value.strip() for value in os.environ.get(
            "MT_ALLOWED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:8765,http://localhost:8765").split(",") if value.strip()))
    secure_cookie: bool = field(default_factory=lambda: os.environ.get("MT_SECURE_COOKIE") == "1")
    allow_browser_setup: bool = field(default_factory=lambda: os.environ.get("MT_ALLOW_BROWSER_SETUP") == "1")
    session_hours: int = 8
    login_failures: int = 5
    login_lock_seconds: int = 300
    max_upload_bytes: int = 10 * 1024 * 1024
    max_samples: int = 10000
    node_timeout_seconds: int = 20
    heartbeat_seconds: int = 3
    enrollment_seconds: int = 600
    enable_local_worker: bool = field(default_factory=lambda: os.environ.get("MT_ENABLE_LOCAL_WORKER") == "1")
    local_controller_url: str = field(default_factory=lambda: os.environ.get("MT_LOCAL_CONTROLLER_URL") or "http://127.0.0.1:8000")
    torch_python: str = field(default_factory=lambda: os.environ.get("MT_TORCH_PYTHON") or "D:/Anaconda/anzhuang/envs/torch_env/python.exe")
    llm_python: str = field(default_factory=lambda: os.environ.get("MT_LLM_PYTHON") or "D:/model-training-demo/worker-llm-runtime/.venv/Scripts/python.exe")
    local_model_cache: str = field(default_factory=lambda: os.environ.get("MT_MODEL_CACHE") or "D:/model-training-demo/worker-llm-runtime/cache/huggingface")

    def __post_init__(self):
        if not self.runtime_dir.is_absolute():
            raise ValueError("MT_RUNTIME_DIR 必须是绝对路径")
        if "*" in self.allowed_origins:
            raise ValueError("不允许通配符来源")

    @property
    def db_url(self) -> str:
        return self.database_url or f"sqlite:///{(self.runtime_dir / 'platform.sqlite3').as_posix()}"

    @property
    def storage_dir(self) -> Path:
        return self.runtime_dir / "storage"
