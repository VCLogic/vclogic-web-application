from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from vclogic_web import portraits
from vclogic_web.app import create_app

SOURCE = portraits.DIRECTORY + "/mac-conwell-rarebreed-ventures"
IMAGE = "https://cdn.sanity.io/images/dlpvy1r0/production/mac-800x800.jpg"


def person(tmp_path):
    registry = tmp_path / "mac.toml"
    registry.write_text('name = "Mac Conwell"')
    return SimpleNamespace(vc_slug="mac-conwell", display_name="Mac Conwell",
                           firm="RareBreed Ventures", registry_path=registry)


def fixture_network(monkeypatch, *, payload=b"\xff\xd8\xffphoto", kind="image/jpeg"):
    calls = []
    def fetch(url, *, image=False):
        calls.append(url)
        if url == portraits.DIRECTORY:
            return f'<a href="{SOURCE}">Mac Conwell</a>'.encode(), "text/html"
        if url == SOURCE:
            return (f'<img alt="Other Investor" src="{IMAGE}?wrong">'
                    f'<img alt="Mac Conwell, venture capital investor on The Pitch" '
                    f'src="/_next/image?url={IMAGE}&amp;w=3840">').encode(), "text/html"
        assert url == IMAGE and image
        return payload, kind
    monkeypatch.setattr(portraits, "retrieve", fetch)
    return calls


def test_lazy_discovery_slug_difference_and_persistent_cache(tmp_path, monkeypatch):
    profile = person(tmp_path)
    calls = fixture_network(monkeypatch)
    cache = portraits.PortraitCache(tmp_path)
    assert cache.fields(profile)["portrait_path"] == "/api/investors/mac-conwell/portrait"
    assert calls == []
    image = cache.resolve(profile)
    assert image.read_bytes() == b"\xff\xd8\xffphoto"
    assert cache.fields(profile)["source_profile_url"] == SOURCE
    assert cache.fields(profile)["photo_attribution"] == "Photo: The Pitch"
    assert portraits.PortraitCache(tmp_path).resolve(profile) == image
    assert calls == [portraits.DIRECTORY, SOURCE, IMAGE]


def test_metadata_source_skips_directory(tmp_path, monkeypatch):
    profile = person(tmp_path)
    profile.registry_path.write_text(f'source_url = "{SOURCE}"')
    calls = fixture_network(monkeypatch)
    assert portraits.PortraitCache(tmp_path).resolve(profile)
    assert calls == [SOURCE, IMAGE]


def test_negative_cache_and_retry(tmp_path, monkeypatch):
    profile = person(tmp_path)
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise OSError("offline")
    monkeypatch.setattr(portraits, "retrieve", fail)
    cache = portraits.PortraitCache(tmp_path)
    assert cache.resolve(profile) is None
    assert portraits.PortraitCache(tmp_path).resolve(profile) is None
    assert len(calls) == 1
    now = portraits.time()
    monkeypatch.setattr(portraits, "time", lambda: now + portraits.NEGATIVE_TTL + 1)
    assert cache.resolve(profile) is None
    assert len(calls) == 2


@pytest.mark.parametrize("url", ["http://cdn.sanity.io/images/dlpvy1r0/production/x",
    "https://evil.test/a", "https://cdn.sanity.io@evil.test/a",
    "https://cdn.sanity.io:8080/images/dlpvy1r0/production/x"])
def test_untrusted_fetch_is_rejected_before_network(url):
    with pytest.raises(ValueError):
        portraits.retrieve(url, image=True)


def test_redirect_refused_before_following():
    with pytest.raises(ValueError, match="redirect"):
        portraits._NoRedirect().redirect_request(None, None, 302, "", {}, "https://127.0.0.1/")


@pytest.mark.parametrize(("payload", "kind", "suffix"), [
    (b"\xff\xd8\xffphoto", "image/jpeg", ".jpg"),
    (b"\x89PNG\r\n\x1a\nphoto", "image/png", ".png"),
    (b"RIFF0000WEBPphoto", "image/webp", ".webp"),
])
def test_raster_types_and_image_endpoint(tmp_path, monkeypatch, payload, kind, suffix):
    profile = person(tmp_path)
    fixture_network(monkeypatch, payload=payload, kind=kind)
    cache = portraits.PortraitCache(tmp_path)
    path = cache.resolve(profile)
    assert path.suffix == suffix
    backend = SimpleNamespace(portrait=lambda slug: cache.resolve(profile))
    client = TestClient(create_app(testing=True, profile_service=backend))
    response = client.get("/api/investors/mac-conwell/portrait")
    assert response.content == payload
    assert response.headers["content-type"] == kind


def test_wrong_content_and_missing_identity_fail_closed(tmp_path, monkeypatch):
    profile = person(tmp_path)
    fixture_network(monkeypatch, payload=b"<script>bad</script>", kind="image/jpeg")
    assert portraits.PortraitCache(tmp_path).resolve(profile) is None
    assert not list((tmp_path / "outputs").rglob("*.jpg"))


def test_concurrent_image_requests_share_download(tmp_path, monkeypatch):
    profile = person(tmp_path)
    calls = fixture_network(monkeypatch)
    cache = portraits.PortraitCache(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        paths = list(pool.map(lambda _: cache.resolve(profile), range(4)))
    assert paths[0] is not None and len(set(paths)) == 1
    assert calls == [portraits.DIRECTORY, SOURCE, IMAGE]


def test_stream_size_limit(tmp_path, monkeypatch):
    class Response:
        headers = SimpleNamespace(get_content_type=lambda: "image/jpeg")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read1(self, size):
            return b"12345"
    monkeypatch.setattr(portraits, "MAX_BYTES", 4)
    monkeypatch.setattr(portraits, "build_opener", lambda *args: SimpleNamespace(open=lambda *a, **k: Response()))
    with pytest.raises(ValueError, match="limits"):
        portraits.retrieve(IMAGE, image=True)


def test_stream_deadline_checked_after_each_single_read(monkeypatch):
    reads = []
    class Response:
        headers = SimpleNamespace(get_content_type=lambda: "image/jpeg")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read1(self, size):
            reads.append(size)
            return b"x"
    clock = iter((0, 3, 6, 9))
    monkeypatch.setattr(portraits, "monotonic", lambda: next(clock))
    monkeypatch.setattr(portraits, "build_opener", lambda *args: SimpleNamespace(open=lambda *a, **k: Response()))
    with pytest.raises(ValueError, match="limits"):
        portraits.retrieve(IMAGE, image=True)
    assert len(reads) == 3


def test_wrong_person_image_is_not_used(tmp_path, monkeypatch):
    profile = person(tmp_path)
    profile.registry_path.write_text(f'source_url = "{SOURCE}"')
    monkeypatch.setattr(portraits, "retrieve", lambda *args, **kwargs:
                        (f'<img alt="Someone Else" src="{IMAGE}">'.encode(), "text/html"))
    assert portraits.PortraitCache(tmp_path).resolve(profile) is None
