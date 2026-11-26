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
    csrf_secret: str = field(default_factory=lambda: os.environ.get("MT_CSRF_SECRET") or "")
    allow_browser_setup: bool = field(default_factory=lambda: os.environ.get("MT_ALLOW_BROWSER_SETUP") == "1")
    session_hours: int = 8
    login_failures: int = 5
    login_lock_seconds: int = 300
    # 账号维度全局滑动限流：阈值约为单 IP 的 3 倍，窗口与锁定时长 15 分钟。
    login_account_failures: int = 15
    login_account_lock_seconds: int = 900
    login_account_window_seconds: int = 900
    max_upload_bytes: int = 10 * 1024 * 1024
    max_samples: int = 10000
    node_timeout_seconds: int = 20
    heartbeat_seconds: int = 3
    enrollment_seconds: int = 600
    # Worker 凭据有效期（天），可通过 MT_WORKER_CREDENTIAL_DAYS 覆盖。
    worker_credential_days: int = field(default_factory=lambda: int(os.environ.get("MT_WORKER_CREDENTIAL_DAYS") or 90))
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

    @property
    def resolved_csrf_secret(self) -> str:
        if self.csrf_secret:
            return self.csrf_secret
        import secrets
        key_dir = self.runtime_dir / "private"
        key_file = key_dir / "csrf.key"
        if key_file.is_file():
            return key_file.read_text(encoding="ascii").strip()
        key_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        generated = secrets.token_hex(32)
        try:
            with os.fdopen(os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="ascii") as f:
                f.write(generated)
            return generated
        except FileExistsError:
            return key_file.read_text(encoding="ascii").strip()
