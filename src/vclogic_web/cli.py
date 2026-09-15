"""One-command launcher for the local founder-rehearsal application."""

from __future__ import annotations

import argparse
import ipaddress
from pathlib import Path
from typing import Sequence

import uvicorn

from .app import create_app


def validate_host(host: str, *, allow_remote: bool) -> str:
    try:
        address = ipaddress.ip_address(host)
        local = address.is_loopback
    except ValueError:
        local = host.casefold() == "localhost"
    if not local and not allow_remote:
        raise ValueError(
            "non-loopback binding requires explicit --allow-remote authorization"
        )
    return host


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vc-clone-web")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/rehearsal-charles-v41-grounded.toml"),
    )
    parser.add_argument("--pipeline-workspace", type=Path, required=True,
                        help="Pipeline checkout containing configs, inputs, and runtime outputs")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument("--static-root", type=Path, default=Path("web/frontend/dist"))
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    host = validate_host(args.host, allow_remote=args.allow_remote)
    workspace = Path.cwd().resolve()
    static_root = (workspace / args.static_root).resolve()
    if not (static_root / "index.html").is_file():
        raise SystemExit(
            f"compiled frontend not found at {static_root}; run `cd web/frontend && npm run build`"
        )
    app = create_app(
        pipeline_workspace=args.pipeline_workspace.resolve(),
        rehearsal_config=args.config,
        static_root=static_root,
    )
    uvicorn.run(app, host=host, port=args.port)


if __name__ == "__main__":  # pragma: no cover
    main()
