"""应用升级前使用 SQLite 在线备份并核对，保留已有账号与资产。"""
from datetime import datetime
import json
from pathlib import Path
import sqlite3


def main():
    root = Path("D:/model-training-demo/backend-runtime")
    destination = root / "backups" / ("pre-compute-jobs-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    destination.mkdir(parents=True, exist_ok=False)
    with sqlite3.connect(f"file:{(root / 'platform.sqlite3').as_posix()}?mode=ro", uri=True) as source:
        before = {table: source.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0] for table in ["users", "user_groups", "workspaces", "models", "model_versions", "datasets", "dataset_versions"]}
        with sqlite3.connect(destination / "platform.sqlite3") as target:
            source.backup(target)
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("数据库备份完整性检查失败")
        version = source.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    record = {"backup": str(destination / "platform.sqlite3"), "schema": version, "counts": before}
    (destination / "backup.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "latest-pre-upgrade-backup.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
