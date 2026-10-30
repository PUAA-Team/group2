import argparse
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description="模型训练平台 Worker")
    commands = parser.add_subparsers(dest="command", required=True)
    agent = commands.add_parser("agent")
    agent.add_argument("--controller", required=True)
    agent.add_argument("--state-dir", required=True)
    agent.add_argument("--trainer-python", default=sys.executable)
    agent.add_argument("--slots", type=int, choices=range(1, 5), default=2)
    agent.add_argument("--join-code-stdin", action="store_true")
    agent.add_argument("--allow-http", action="store_true")
    agent.add_argument("--model-cache", default=None)
    run = commands.add_parser("run")
    run.add_argument("--spec", required=True)
    args = parser.parse_args()
    args.bundle = Path(sys.argv[0]).resolve()
    try:
        if args.command == "agent":
            from .agent import Agent
            Agent(args).run()
        elif args.command == "run":
            from .runner import run_job
            run_job(Path(args.spec))
    except Exception as error:
        # 错误只输出受控说明；不打印参数、输入的接入码或凭据。
        from .client import WorkerError
        message = str(error) if isinstance(error, (WorkerError, ValueError, RuntimeError)) else type(error).__name__
        parser.exit(1, "Worker 未完成：" + message + "\n")


if __name__ == "__main__":
    main()
