"""Lazy, bounded The Pitch portrait discovery with a workspace-local cache.

Profile reads never access the network. The browser's separate image request does
that work in FastAPI's sync worker, and failures leave the initials fallback intact.
"""
from __future__ import annotations

from hashlib import sha256
from html.parser import HTMLParser
from http.client import HTTPException
import json
from pathlib import Path
import re
from threading import BoundedSemaphore, Lock
from tempfile import NamedTemporaryFile
from time import monotonic, time
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .investor_presentation import INVESTOR_PRESENTATION

DIRECTORY = "https://www.thepitch.show/investors"
NEGATIVE_TTL = 3600
MAX_BYTES = 4 * 1024 * 1024
_FETCH_SLOTS = BoundedSemaphore(4)


def _trusted(url: str, *, image: bool = False) -> bool:
    parsed = urlparse(url)
    hosts = {"cdn.sanity.io"} if image else {"www.thepitch.show", "thepitch.show"}
    return (parsed.scheme == "https" and parsed.hostname in hosts
            and parsed.port in (None, 443) and not parsed.username and not parsed.password
            and (parsed.path.startswith("/images/dlpvy1r0/production/") if image
                 else parsed.path == "/investors" or parsed.path.startswith("/investors/")))


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Reject before following: validating only the final host is too late.
        raise ValueError("portrait redirect refused")


def retrieve(url: str, *, image: bool = False) -> tuple[bytes, str]:
    if not _trusted(url, image=image):
        raise ValueError("untrusted portrait source")
    deadline = monotonic() + 8
    request = Request(url, headers={"User-Agent": "VCLogic-portrait-cache/1.0"})
    with build_opener(_NoRedirect()).open(request, timeout=4) as response:
        chunks, size = [], 0
        while True:
            chunk = response.read1(64 * 1024)
            size += len(chunk)
            if size > MAX_BYTES or monotonic() > deadline:
                raise ValueError("portrait source exceeds limits")
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks), response.headers.get_content_type()


class _Page(HTMLParser):
    def __init__(self, content: bytes):
        super().__init__()
        self.links: list[str] = []
        self.images: list[dict[str, str]] = []
        self.feed(content.decode("utf-8", errors="replace"))

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "a" and values.get("href"):
            self.links.append(urljoin(DIRECTORY, values["href"]))
        if tag == "img":
            self.images.append(values)


def _name(value: str) -> str:
    return "-".join(re.findall(r"[a-z0-9]+", value.casefold()))


class PortraitCache:
    def __init__(self, workspace: Path):
        self.root = Path(workspace) / "outputs/web-investors/portraits"
        self._guard = Lock()
        self._locks: dict[str, Lock] = {}

    def _key(self, profile) -> str:
        return sha256(f"{profile.vc_slug}\0{profile.display_name}\0{profile.firm}".encode()).hexdigest()

    def _metadata(self, profile) -> dict:
        try:
            data = json.loads((self.root / f"{self._key(profile)}.json").read_text())
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def fields(self, profile) -> dict:
        fixed = INVESTOR_PRESENTATION.get(profile.vc_slug)
        if fixed:
            return {key: str(getattr(fixed, key)) for key in
                    ("portrait_path", "portrait_alt", "source_profile_url", "photo_attribution")}
        cached = self._metadata(profile)
        return dict(portrait_path=f"/api/investors/{profile.vc_slug}/portrait",
                    portrait_alt=f"{profile.display_name} portrait",
                    source_profile_url=cached.get("source_profile_url", DIRECTORY),
                    photo_attribution="Photo: The Pitch")

    def _discover(self, profile) -> tuple[str, str]:
        identity = _name(profile.display_name)
        # Registry metadata may already contain the original public source URL.
        candidates = []
        try:
            with profile.registry_path.open() as stream:
                metadata = stream.read(256 * 1024)
            candidates = [url for url in re.findall(r'https://[^\s"<>\x27]+', metadata)
                          if _trusted(url) and urlparse(url).path.startswith("/investors/")]
        except OSError:
            pass
        candidates = [url for url in candidates
                      if urlparse(url).path.rstrip("/").rsplit("/", 1)[-1] == identity
                      or urlparse(url).path.rstrip("/").rsplit("/", 1)[-1].startswith(identity + "-")]
        if not candidates:
            content, kind = retrieve(DIRECTORY)
            if kind != "text/html":
                raise ValueError("invalid investor directory")
            candidates = [url for url in _Page(content).links if _trusted(url)
                          and (urlparse(url).path.rstrip("/").rsplit("/", 1)[-1] == identity
                               or urlparse(url).path.rstrip("/").rsplit("/", 1)[-1].startswith(identity + "-"))]
        candidates = sorted(set(candidates))
        if len(candidates) != 1:
            raise ValueError("no unambiguous investor portrait source")
        source = candidates[0]
        content, kind = retrieve(source)
        if kind != "text/html":
            raise ValueError("invalid investor page")
        for image in _Page(content).images:
            alt = _name(image.get("alt", ""))
            if alt != identity and not alt.startswith(identity + "-"):
                continue
            url = urljoin(source, image.get("src", ""))
            if urlparse(url).path == "/_next/image":
                url = parse_qs(urlparse(url).query).get("url", [""])[0]
            if _trusted(url, image=True):
                return source, url
        raise ValueError("no identity-matched portrait")

    def _cached_image(self, key: str) -> Path | None:
        for suffix in ("jpg", "png", "webp"):
            path = self.root / f"{key}.{suffix}"
            if path.is_file():
                return path
        return None

    def _write(self, destination: Path, payload: bytes) -> None:
        with NamedTemporaryFile(dir=self.root, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
        try:
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

    def resolve(self, profile) -> Path | None:
        key = self._key(profile)
        cached = self._cached_image(key)
        if cached is not None:
            return cached
        with self._guard:
            lock = self._locks.setdefault(key, Lock())
        # Same-person image requests share a download; independent images use up
        # to four workers. Waiting is isolated to image requests, never profiles.
        if not lock.acquire(timeout=30):
            return None
        acquired_slot = False
        try:
            cached = self._cached_image(key)
            if cached is not None:
                return cached
            metadata = self._metadata(profile)
            if metadata.get("retry_after", 0) > time():
                return None
            acquired_slot = _FETCH_SLOTS.acquire(timeout=30)
            if not acquired_slot:
                return None
            self.root.mkdir(parents=True, exist_ok=True)
            try:
                source, image = self._discover(profile)
                payload, kind = retrieve(image, image=True)
                suffix = None
                if kind == "image/jpeg" and payload.startswith(b"\xff\xd8\xff"):
                    suffix = "jpg"
                elif kind == "image/png" and payload.startswith(b"\x89PNG\r\n\x1a\n"):
                    suffix = "png"
                elif kind == "image/webp" and payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
                    suffix = "webp"
                if suffix is None:
                    raise ValueError("portrait is not a supported raster image")
                self._write(self.root / f"{key}.{suffix}", payload)
                metadata = dict(source_profile_url=source, source_image_url=image,
                                photo_attribution="Photo: The Pitch", retrieved_at=time(),
                                sha256=sha256(payload).hexdigest(), content_type=kind)
            except (OSError, ValueError, HTTPException):
                metadata = {"retry_after": time() + NEGATIVE_TTL}
            self._write(self.root / f"{key}.json", json.dumps(metadata).encode())
            return self._cached_image(key)
        except OSError:
            return None
        finally:
            if acquired_slot:
                _FETCH_SLOTS.release()
            lock.release()
