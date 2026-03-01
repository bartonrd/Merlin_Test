"""
Root-level launcher – lets users start Merlin with:

    python main.py                    # from the project root
    python main.py --host 0.0.0.0 --port 8000

Equivalent to:
    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
import argparse
import sys
from pathlib import Path

# Ensure the project root is on sys.path regardless of the working directory.
_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import uvicorn  # noqa: E402 – must come after sys.path setup


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the Merlin document assistant server.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev mode)")
    args = parser.parse_args()

    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
