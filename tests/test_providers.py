"""Provider clients against mocked HTTP / SDK: request shape and error classification."""

import base64
import types

import httpx
import pytest

from pipeline.common import PermanentError, TransientError
from pipeline.providers import cloudflare, gemini

PNG = b"\x89PNG\r\n\x1a\nfake"


@pytest.fixture(autouse=True)
def creds(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    monkeypatch.setenv("GEMINI_API_KEY", "key")


def _resp(status: int, body: dict) -> httpx.Response:
    return httpx.Response(status, json=body, request=httpx.Request("POST", "https://x"))


def test_schnell_sends_json_and_decodes_image(monkeypatch):
    seen = {}

    def fake_post(url, headers, timeout, **kw):  # noqa: ARG001
        seen.update(url=url, headers=headers, **kw)
        return _resp(200, {"result": {"image": base64.b64encode(PNG).decode()}})

    monkeypatch.setattr(httpx, "post", fake_post)
    out = cloudflare.flux_schnell("a pot", model="@cf/black-forest-labs/flux-1-schnell", seed=3)
    assert out == PNG
    assert seen["url"].endswith("/accounts/acct/ai/run/@cf/black-forest-labs/flux-1-schnell")
    assert seen["headers"]["Authorization"] == "Bearer tok"
    assert seen["json"] == {"prompt": "a pot", "steps": 4, "seed": 3}


def test_flux2_sends_multipart_with_references(monkeypatch):
    seen = {}

    def fake_post(url, headers, timeout, **kw):  # noqa: ARG001
        seen.update(kw)
        return _resp(200, {"result": {"image": base64.b64encode(PNG).decode()}})

    monkeypatch.setattr(httpx, "post", fake_post)
    cloudflare.flux2("p", model="m", width=512, height=256, seed=1, references=[b"a", b"b"])
    names = [name for name, _ in seen["files"]]
    assert names[:3] == ["prompt", "width", "height"]
    assert "input_image_0" in names and "input_image_1" in names
    assert "json" not in seen  # multipart, not JSON


@pytest.mark.parametrize("status,exc", [(429, TransientError), (503, TransientError),
                                        (400, PermanentError), (401, PermanentError)])
def test_cloudflare_error_classification(monkeypatch, status, exc):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _resp(status, {"errors": ["x"]}))
    with pytest.raises(exc):
        cloudflare.flux_schnell("p", model="m")


def test_cloudflare_missing_image_is_transient(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _resp(200, {"result": {}}))
    with pytest.raises(TransientError):
        cloudflare.flux_schnell("p", model="m")


def test_cloudflare_network_error_is_transient(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectTimeout("slow")

    monkeypatch.setattr(httpx, "post", boom)
    with pytest.raises(TransientError):
        cloudflare.flux_schnell("p", model="m")


class _FakeClient:
    def __init__(self, interaction=None, error=None, text="hi"):
        self._interaction, self._error, self.calls = interaction, error, []
        self.interactions = types.SimpleNamespace(create=self._create)
        self.models = types.SimpleNamespace(
            generate_content=lambda **kw: self.calls.append(kw) or types.SimpleNamespace(text=text))

    def _create(self, **kw):
        self.calls.append(kw)
        if self._error:
            raise self._error
        return self._interaction


def _use_client(monkeypatch, client):
    monkeypatch.setattr(gemini, "_client", lambda: client)


def test_tts_request_shape_and_wav_output(monkeypatch):
    wav = gemini.ensure_wav(b"\x00\x00" * 100)
    client = _FakeClient(types.SimpleNamespace(
        output_audio=types.SimpleNamespace(data=base64.b64encode(wav).decode())))
    _use_client(monkeypatch, client)
    out = gemini.tts("ሰላም", model="gemini-3.8-flash-tts", voice="Sulafat", style="warm")
    assert out == wav
    call = client.calls[0]
    assert call["model"] == "gemini-3.8-flash-tts"
    assert call["generation_config"] == {"speech_config": [{"voice": "Sulafat"}]}
    content = call["input"][0]["content"][0]
    assert content["text"] == "ሰላም"
    assert content["annotations"] == [{"type": "speech_metadata", "style": "warm"}]


def test_tts_maps_quota_error_to_transient(monkeypatch):
    err = Exception("quota")
    err.code = 429
    _use_client(monkeypatch, _FakeClient(error=err))
    with pytest.raises(TransientError):
        gemini.tts("x", model="m", voice="v")


def test_tts_maps_bad_request_to_permanent(monkeypatch):
    err = Exception("bad")
    err.code = 400
    _use_client(monkeypatch, _FakeClient(error=err))
    with pytest.raises(PermanentError):
        gemini.tts("x", model="m", voice="v")


def test_tts_without_audio_is_transient(monkeypatch):
    _use_client(monkeypatch, _FakeClient(types.SimpleNamespace(output_audio=None)))
    with pytest.raises(TransientError):
        gemini.tts("x", model="m", voice="v")


def test_generate_text_json_mode(monkeypatch):
    client = _FakeClient(text='{"a": 1}')
    _use_client(monkeypatch, client)
    assert gemini.generate_text("p", model="m", json_mode=True) == '{"a": 1}'
    assert client.calls[0]["config"]["response_mime_type"] == "application/json"
