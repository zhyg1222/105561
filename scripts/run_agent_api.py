import argparse
import asyncio
import sys


def main() -> None:
    if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=12400)
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args()

    from uvicorn import Config, Server

    from xiaojuju_core.windows_mutex import acquire_named_mutex, release_named_mutex

    class SelectorConfig(Config):
        def get_loop_factory(self):
            return asyncio.SelectorEventLoop

    config = SelectorConfig(
        "xiaojuju_agent.main:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level,
    )
    lock = acquire_named_mutex(r"Local\XiaoJuJuAgentAPI")
    if lock is None:
        print("agent API already running")
        return
    try:
        Server(config).run()
    finally:
        release_named_mutex(lock)


if __name__ == "__main__":
    main()
