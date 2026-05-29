import pytest

from apps.common.services.timetable_update.version_core import file_data
from apps.common.services.timetable_update.version_core.file_data import (
    FileData,
    FileTooLargeError,
)


class FakeResponse:
    status_code = 200

    def __init__(self, chunks: list[bytes], headers: dict[str, str] | None = None) -> None:
        self._chunks = chunks
        self.headers = headers or {}

    def iter_content(self, chunk_size: int):
        yield from self._chunks


def test_download_file_uses_timeout_and_stream(monkeypatch, tmp_path):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse([b"abc"], {"Content-Length": "3"})

    monkeypatch.setattr(file_data.requests, "get", fake_get)

    downloaded_path = FileData(
        "Schedule/file.xlsx",
        "https://example.test/file.xlsx",
        "2026-05-29 10:00:00",
    ).download_file(tmp_path)

    assert downloaded_path.read_bytes() == b"abc"
    assert calls == [
        (
            "https://example.test/file.xlsx",
            {"stream": True, "timeout": file_data.DOWNLOAD_TIMEOUT_SECONDS},
        )
    ]


def test_download_file_rejects_large_content_length(monkeypatch, tmp_path):
    def fake_get(url, **kwargs):
        return FakeResponse([], {"Content-Length": str(file_data.MAX_DOWNLOAD_BYTES + 1)})

    monkeypatch.setattr(file_data.requests, "get", fake_get)

    with pytest.raises(FileTooLargeError):
        FileData(
            "Schedule/file.xlsx",
            "https://example.test/file.xlsx",
            "2026-05-29 10:00:00",
        ).download_file(tmp_path)

    assert not list(tmp_path.iterdir())


def test_download_file_deletes_partial_file_when_stream_exceeds_limit(monkeypatch, tmp_path):
    def fake_get(url, **kwargs):
        return FakeResponse(
            [b"a" * file_data.MAX_DOWNLOAD_BYTES, b"b"],
            {"Content-Length": str(file_data.MAX_DOWNLOAD_BYTES)},
        )

    monkeypatch.setattr(file_data.requests, "get", fake_get)

    with pytest.raises(FileTooLargeError):
        FileData(
            "Schedule/file.xlsx",
            "https://example.test/file.xlsx",
            "2026-05-29 10:00:00",
        ).download_file(tmp_path)

    assert not list(tmp_path.iterdir())
