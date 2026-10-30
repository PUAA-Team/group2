"""按显式空间和操作人添加已授权的教学预置，不修改用户权限或旧版本。"""
import argparse
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend/src"))
from model_platform.config import Settings
from model_platform.database import make_engine, make_session_factory
from model_platform.models import User
from model_platform.services.presets import seed_presets


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--actor-id", required=True)
    parser.add_argument("--connect-local", action="store_true")
    args = parser.parse_args(); settings = Settings(); engine = make_engine(settings.db_url)
    try:
        with make_session_factory(engine)() as db:
            actor = db.get(User, args.actor_id)
            if not actor or not actor.active:
                raise ValueError("操作人必须存在且启用")
            result = asyncio.run(seed_presets(db, settings, actor, args.workspace_id, ["text_classification", "image_classification", "llm_sft"]))
            print(json.dumps({"presets": len(result), "workspace_id": args.workspace_id}, ensure_ascii=False))
            if args.connect_local:
                from model_platform.compute_schemas import LocalWorkerInput
                from model_platform.services.local_worker import start_local_worker
                receipt = start_local_worker(db, settings, actor, LocalWorkerInput(workspace_id=args.workspace_id, name="本机 RTX 4060", runtime_id="llm"))
                print(json.dumps(receipt, ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
