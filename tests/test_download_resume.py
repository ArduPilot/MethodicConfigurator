"""Unit tests for download resume and retry behavior."""

from collections.abc import Iterator

from requests.exceptions import RequestException

from ardupilot_methodic_configurator.backend_internet import download_file_from_url


class DummyResponse:
    def __init__(self, chunks: Iterator[bytes], headers: dict[str, str], status_code: int = 200) -> None:
        self._chunks = list(chunks)
        self.headers = headers
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int = 8192) -> Iterator[bytes]:
        yield from self._chunks


def test_download_success(tmp_path, monkeypatch) -> None:
    data = b"hello world"
    file_path = tmp_path / "out.bin"

    def _get(*_args: object, **_kwargs: object) -> DummyResponse:
        return DummyResponse([data], {"content-length": str(len(data))}, 200)

    monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.requests_get", _get)

    ok = download_file_from_url("https://example.com/file", str(file_path))
    assert ok is True
    assert file_path.read_bytes() == data


def test_download_resume_with_existing_file(tmp_path, monkeypatch) -> None:
    full = b"abcdefghijklmnopqrstuvwxyz"
    existing = full[:10]
    remaining = full[10:]

    file_path = tmp_path / "resume.bin"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(existing)

    # Response must indicate total size via Content-Range or content-length
    headers = {"Content-Range": f"bytes {len(existing)}-{len(full) - 1}/{len(full)}"}

    def _get(*_args: object, **_kwargs: object) -> DummyResponse:
        # Ensure the caller set a Range header when resuming
        headers_arg = _kwargs.get("headers", {})
        assert "Range" in headers_arg
        return DummyResponse([remaining], headers, 206)

    monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.requests_get", _get)

    ok = download_file_from_url("https://example.com/large", str(file_path), allow_resume=True)
    assert ok is True
    assert file_path.read_bytes() == full


def test_download_retries_on_transient_errors(tmp_path, monkeypatch) -> None:
    data = b"finaldata"
    file_path = tmp_path / "retry.bin"

    calls = {"n": 0}

    def _get(*_args: object, **_kwargs: object) -> DummyResponse:
        calls["n"] += 1
        # First two attempts raise, third returns data
        if calls["n"] < 3:
            err_msg = "transient"
            err = RequestException(err_msg)
            raise err
        return DummyResponse([data], {"content-length": str(len(data))}, 200)

    monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.requests_get", _get)

    ok = download_file_from_url("https://example.com/retry", str(file_path), retries=3, backoff_factor=0.01)
    assert ok is True
    assert file_path.read_bytes() == data
    assert calls["n"] >= 3
