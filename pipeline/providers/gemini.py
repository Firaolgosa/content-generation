"""Gemini API: text (storyboard drafting, translation) and TTS (narration).

TTS uses the Interactions API documented at aistudio.google.com/docs/speech-generation
(google-genai >= 2.25). Unary TTS returns a WAV (24 kHz, mono, 16-bit); older preview
models returned headerless PCM, which `ensure_wav` wraps.
"""

from __future__ import annotations

import base64
import io
import wave
from functools import lru_cache
from typing import Any

from pipeline.common import PermanentError, TransientError, http_error_is_transient, require_env

TTS_SAMPLE_RATE = 24_000


@lru_cache(maxsize=1)
def _client() -> Any:
    from google import genai

    key = require_env("GEMINI_API_KEY")["GEMINI_API_KEY"]
    return genai.Client(api_key=key, http_options={"api_version": "v1beta"})


def _translate_error(exc: Exception) -> Exception:
    """Map google-genai errors onto our retry taxonomy."""
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(code, int):
        cls = TransientError if http_error_is_transient(code) else PermanentError
        return cls(f"gemini {code}: {getattr(exc, 'message', None) or exc}")
    name = type(exc).__name__.lower()
    if "timeout" in name or "connect" in name:
        return TransientError(f"gemini network: {exc}")
    return exc


def ensure_wav(audio: bytes, sample_rate: int = TTS_SAMPLE_RATE) -> bytes:
    """Return WAV bytes; wrap raw 16-bit mono PCM if there is no RIFF header."""
    if audio[:4] == b"RIFF":
        return audio
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(audio)
    return buf.getvalue()


def _decode_audio(data: Any) -> bytes:
    if isinstance(data, bytes | bytearray):
        raw = bytes(data)
        return raw if raw[:4] == b"RIFF" else base64.b64decode(raw)
    return base64.b64decode(data)


def tts(text: str, *, model: str, voice: str, style: str = "") -> bytes:
    """Synthesize one narration line. Returns WAV bytes."""
    content: dict[str, Any] = {"type": "text", "text": text}
    if style:
        content["annotations"] = [{"type": "speech_metadata", "style": style}]
    try:
        interaction = _client().interactions.create(
            model=model,
            input=[{"type": "user_input", "content": [content]}],
            response_format={"type": "audio"},
            generation_config={"speech_config": [{"voice": voice}]},
        )
    except Exception as exc:  # noqa: BLE001 - mapped to retry taxonomy
        raise _translate_error(exc) from exc
    audio = getattr(interaction, "output_audio", None)
    if audio is None or not getattr(audio, "data", None):
        raise TransientError("gemini tts returned no audio")
    return ensure_wav(_decode_audio(audio.data))


def generate_text(prompt: str, *, model: str, json_mode: bool = False,
                  temperature: float = 0.7) -> str:
    """Single-turn text generation. With json_mode the model is asked for application/json."""
    config: dict[str, Any] = {"temperature": temperature}
    if json_mode:
        config["response_mime_type"] = "application/json"
    try:
        resp = _client().models.generate_content(model=model, contents=prompt, config=config)
    except Exception as exc:  # noqa: BLE001
        raise _translate_error(exc) from exc
    text = getattr(resp, "text", None)
    if not text:
        raise TransientError("gemini returned an empty response")
    return text
