#!/usr/bin/env python3
"""Download the fixed, attributed The Pitch portrait allowlist."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
from typing import Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from vclogic_web.investor_presentation import INVESTOR_PRESENTATION


Retriever = Callable[[str], tuple[bytes, str, str]]


def retrieve_url(url: str) -> tuple[bytes, str, str]:
    request = Request(url, headers={"User-Agent": "vc-clone-portrait-sync/1.0"})
    with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed allowlist
        return response.read(), response.headers.get_content_type(), response.geturl()


def download_portraits(
    output_root: Path, *, retrieve: Retriever = retrieve_url
) -> dict[str, object]:
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    assets: dict[str, object] = {}
    for slug, metadata in INVESTOR_PRESENTATION.items():
        payload, content_type, final_url = retrieve(str(metadata.source_image_url))
        if urlparse(final_url).hostname != "cdn.sanity.io":
            raise ValueError(f"portrait redirect left approved host: {slug}")
        if content_type.split(";", 1)[0] != "image/jpeg" or not payload.startswith(
            b"\xff\xd8\xff"
        ):
            raise ValueError(f"portrait is not a JPEG: {slug}")
        destination = output_root / f"{slug}.jpg"
        with tempfile.NamedTemporaryFile(dir=output_root, delete=False) as stream:
            stream.write(payload)
            temporary = Path(stream.name)
        temporary.replace(destination)
        assets[slug] = {
            "asset_path": metadata.portrait_path,
            "source_profile_url": str(metadata.source_profile_url),
            "source_image_url": str(metadata.source_image_url),
            "photo_attribution": metadata.photo_attribution,
            "sha256": sha256(payload).hexdigest(),
            "bytes": len(payload),
        }
    return {
        "schema": "investor-portrait-manifest-v1",
        "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "assets": assets,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = download_portraits(args.output)
    destination = args.output / "portrait-manifest.json"
    destination.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
