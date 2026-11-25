"""Model providers: Gemini (text and speech), Cloudflare Workers AI (images), and offline mocks.

Each public function makes one logical model call through `core.model_call`, so retries and the
run log live in one place. With `ctx.mock` set, the same calls are answered locally with no
network, so the whole pipeline can be tested offline. Mock calls are logged to
outputs_mock/runs.mock.jsonl and never to runs.jsonl.

Request shapes follow the provider docs as read on 25 Nov 2026 (see ARCHITECTURE.md, "Providers").
Response parsing is deliberately tolerant, because these APIs change.
"""
from __future__ import annotations

import base64
import io
import json
import math
import os
import re
import struct
import uuid
import wave
from array import array
from typing import Any

from .core import Ctx, PipelineError, ProviderError, ff, model_call, sha

GEMINI = "https://generativelanguage.googleapis.com/v1beta"
CLOUDFLARE = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise PipelineError(f"{name} is not set. Copy .env.example to .env and fill it in.")
    return value


def _retry_after(resp: Any) -> float | None:
    header = resp.headers.get("Retry-After", "")
    if header.replace(".", "", 1).isdigit():
        return float(header)
    m = re.search(r'"retryDelay":\s*"(\d+(?:\.\d+)?)s"', resp.text)
    return float(m.group(1)) if m else None


def _post(url: str, headers: dict, json_body: dict | None = None, files: list | None = None, timeout: int = 300) -> Any:
    """POST and turn every failure into a ProviderError that says whether a retry can help."""
    import requests

    try:
        resp = requests.post(url, headers=headers, json=json_body, files=files, timeout=timeout)
    except requests.RequestException as e:
        raise ProviderError(f"network error ({type(e).__name__}).", retryable=True) from None
    if resp.status_code == 200:
        return resp
    body = " ".join(resp.text.split())[:1200]  # long enough to keep which quota was hit and its limit
    if resp.status_code == 429:
        raise ProviderError(f"HTTP 429, rate limit or quota reached. {body}", 429, True, _retry_after(resp))
    if resp.status_code >= 500:
        raise ProviderError(f"HTTP {resp.status_code}, the provider had an error. {body}", resp.status_code, True)
    hint = {400: "The request was rejected: check the model id and the parameters.",
            401: "The API key or token was rejected.",
            403: "This key has no access to the model, or the model is not offered in this region.",
            404: "Model or endpoint not found. The model id may have changed."}.get(resp.status_code, "")
    raise ProviderError(f"HTTP {resp.status_code}. {hint} {body}", resp.status_code, False)


def _json(resp: Any) -> Any:
    try:
        return resp.json()
    except ValueError:
        raise ProviderError("the provider did not answer with JSON: " + " ".join(resp.text.split())[:200]) from None


# ----------------------------------------------------------------------------- audio helpers


def pcm_to_wav(pcm: bytes, rate: int = 24000, note: str | None = None) -> bytes:
    """Wrap 16-bit mono PCM in a WAV container. `note` is stored in a private chunk (used by the mock)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    data = bytearray(buf.getvalue())
    if note is not None:
        payload = note.encode("utf-8")
        data += b"mock" + struct.pack("<I", len(payload)) + payload + (b"\x00" if len(payload) % 2 else b"")
        data[4:8] = struct.pack("<I", len(data) - 8)
    return bytes(data)


def wav_note(data: bytes) -> str | None:
    """Read back the private chunk written by `pcm_to_wav`."""
    pos = 12
    while pos + 8 <= len(data):
        tag, size = data[pos:pos + 4], struct.unpack("<I", data[pos + 4:pos + 8])[0]
        if tag == b"mock":
            return data[pos + 8:pos + 8 + size].decode("utf-8")
        pos += 8 + size + (size % 2)
    return None


def image_ext(raw: bytes) -> str:
    if raw.startswith(b"\x89PNG"):
        return "png"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp"
    return "jpg"


def audio_seconds(data: bytes) -> float | None:
    """Length of WAV audio held in memory. Speech is priced by the second, so this goes into the run log."""
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            return round(w.getnframes() / float(w.getframerate()), 3)
    except (wave.Error, EOFError):
        return None


def _usage(data: Any) -> dict:
    """Token counts of a speech response, when the API reports them. The key names are read tolerantly."""
    usage = data.get("usage") or data.get("usageMetadata") if isinstance(data, dict) else None
    if not isinstance(usage, dict):
        return {}
    def first(*names: str) -> Any:
        return next((usage[n] for n in names if isinstance(usage.get(n), (int, float))), None)
    return {"usage": {"input_tokens": first("total_input_tokens", "input_tokens", "promptTokenCount"),
                      "output_tokens": first("total_output_tokens", "output_tokens", "candidatesTokenCount")}}


def _find_audios(node: Any) -> list[tuple[str, str]]:
    """Every audio payload in a response, in order, whatever nesting the API uses this month."""
    found: list[tuple[str, str]] = []
    if isinstance(node, dict):
        if node.get("type") == "audio" and isinstance(node.get("data"), str):
            found.append((node["data"], node.get("mime_type") or node.get("mimeType") or "audio/wav"))
        inline = node.get("inlineData") or node.get("inline_data")
        if isinstance(inline, dict) and str(inline.get("mimeType") or inline.get("mime_type", "")).startswith("audio/"):
            found.append((inline["data"], inline.get("mimeType") or inline.get("mime_type")))
        for value in node.values():
            found += _find_audios(value)
    elif isinstance(node, list):
        for value in node:
            found += _find_audios(value)
    return found


def _find_audio(node: Any) -> tuple[str, str] | None:
    """The last audio payload in a response."""
    found = _find_audios(node)
    return found[-1] if found else None


def _as_wav(data: str, mime: str | None) -> bytes:
    raw = base64.b64decode(data)
    if not raw.startswith(b"RIFF"):  # headerless PCM: wrap it
        rate = re.search(r"rate=(\d+)", mime or "")
        raw = pcm_to_wav(raw, int(rate.group(1)) if rate else 24000)
    return raw


# ----------------------------------------------------------------------------- speech


def _mock_speech(text: str) -> bytes:
    """A beep pattern about as long as the line would take to say. Deterministic."""
    letters = sum(1 for ch in text if ch.isalnum())
    seconds = max(1.0, letters / (14.0 if text.isascii() else 6.0))  # Ethiopic letters are syllables
    rate, burst, gap = 24000, int(0.17 * 24000), int(0.06 * 24000)
    out, k = array("h"), 0
    while len(out) < seconds * rate:
        freq = 180 + (ord(text[k % len(text)]) % 12) * 14
        step = 2 * math.pi * freq / rate
        out.extend(int(9000 * min(1.0, j / 400, (burst - j) / 400) * math.sin(step * j)) for j in range(burst))
        out.extend([0] * gap)
        k += 1
    return out[:int(seconds * rate)].tobytes()


def tts(ctx: Ctx, stage: str, unit: str, text: str, *, voice: str, style: str, model: str | None = None) -> tuple[bytes, dict]:
    """Text to speech. Returns WAV bytes (24 kHz mono 16-bit)."""
    model = model or ctx.sb["models"]["tts"]
    params = {"voice": voice, "style": style, "chars": len(text), "text_sha": sha(text)[:12]}

    def real() -> tuple[bytes, dict]:
        body = {
            "model": model,
            "input": [{"type": "user_input", "content": [{"type": "text", "text": text,
                                                         "annotations": [{"type": "speech_metadata", "style": style}]}]}],
            "response_format": {"type": "audio"},
            "generation_config": {"speech_config": [{"voice": voice}]},
        }
        resp = _post(f"{GEMINI}/interactions", {"x-goog-api-key": _env("GEMINI_API_KEY")}, json_body=body)
        data = _json(resp)
        found = _find_audio(data)
        if not found:
            raise ProviderError("the response held no audio: " + " ".join(resp.text.split())[:200])
        raw = _as_wav(*found)
        return raw, {"audio_bytes": len(raw), "audio_seconds": audio_seconds(raw), **_usage(data)}

    def mock() -> tuple[bytes, dict]:
        raw = pcm_to_wav(_mock_speech(text), note=text)
        return raw, {"audio_bytes": len(raw), "audio_seconds": audio_seconds(raw)}

    return model_call(ctx, stage=stage, unit=unit, provider="mock" if ctx.mock else "gemini", model=model,
                      params=params, seed=None, fn=mock if ctx.mock else real)


PAUSE = "<long pause>"  # an inline tag from the speech docs: "Insert <short pause> or <long pause> at exact points in the script."
MOCK_PAUSE_S = 1.5


def tts_take(ctx: Ctx, stage: str, unit: str, texts: list[str], *, voice: str, style: str, model: str | None = None) -> tuple[list[bytes], dict]:
    """Several lines in ONE speech request. Returns the audio the model sent back as WAV, in order.

    The free tier counts requests (10 a day when this was written), not lines, so a take of the
    whole narration costs one request where a request per line costs eight. Each line is its own
    content item and ends with a long pause. The response holds either one audio per line or one
    audio for everything: the caller cuts a single audio at the pauses.
    """
    model = model or ctx.sb["models"]["tts"]
    params = {"voice": voice, "style": style, "lines": len(texts), "chars": sum(len(t) for t in texts), "text_sha": sha(texts)[:12]}

    def real() -> tuple[list[bytes], dict]:
        content = [{"type": "text", "text": text if n == len(texts) else f"{text} {PAUSE}",
                    "annotations": [{"type": "speech_metadata", "style": style}]} for n, text in enumerate(texts, start=1)]
        body = {"model": model, "input": [{"type": "user_input", "content": content}], "response_format": {"type": "audio"},
                "generation_config": {"speech_config": [{"voice": voice}]}}
        resp = _post(f"{GEMINI}/interactions", {"x-goog-api-key": _env("GEMINI_API_KEY")}, json_body=body)
        data = _json(resp)
        found = _find_audios(data)
        if not found:
            raise ProviderError("the response held no audio: " + " ".join(resp.text.split())[:200])
        wavs = [_as_wav(*item) for item in found]
        seconds = [audio_seconds(w) for w in wavs]
        return wavs, {"audio_blocks": len(wavs), "audio_bytes": sum(len(w) for w in wavs),
                      "audio_seconds": round(sum(x or 0 for x in seconds), 3), **_usage(data)}

    def mock() -> tuple[list[bytes], dict]:
        gap = b"\x00\x00" * int(MOCK_PAUSE_S * 24000)
        raw = pcm_to_wav(gap.join(_mock_speech(text) for text in texts))  # one audio for everything, pauses between the lines
        return [raw], {"audio_blocks": 1, "audio_bytes": len(raw), "audio_seconds": audio_seconds(raw)}

    return model_call(ctx, stage=stage, unit=unit, provider="mock" if ctx.mock else "gemini", model=model,
                      params=params, seed=None, fn=mock if ctx.mock else real)


# ----------------------------------------------------------------------------- text, vision, listening


def _claude(model: str, prompt: str, parts: list[tuple[str, bytes]], system: str | None, schema: dict | None) -> tuple[str, dict]:
    """One answer from the Claude API, through the official SDK. Images go in before the question.

    The SDK's own retries are switched off, so every attempt is one line in the run log, like any other call.
    A refusal can be answered by a fallback model on Anthropic's side: `served_by` in the log says which model answered.
    """
    try:
        import anthropic
    except ImportError:
        raise PipelineError("this model needs the anthropic package. Run: pip install anthropic") from None
    _env("ANTHROPIC_API_KEY")
    if any(not mime.startswith("image/") for mime, _ in parts):
        raise PipelineError(f"{model} takes pictures and text, not audio. Use a Gemini model for the listening check.")
    content: list[dict] = [{"type": "image", "source": {"type": "base64", "media_type": mime, "data": base64.b64encode(data).decode("ascii")}}
                           for mime, data in parts]
    content.append({"type": "text", "text": prompt})
    request: dict[str, Any] = {"model": model, "max_tokens": 16000, "messages": [{"role": "user", "content": content}]}
    if system:
        request["system"] = system
    if schema:
        request["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
    workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID", "").strip()  # needed with a key that is not scoped to one workspace
    client = anthropic.Anthropic(max_retries=0, default_headers={"anthropic-workspace-id": workspace} if workspace else None)
    try:
        response = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **request)
    except anthropic.RateLimitError as e:
        after = e.response.headers.get("retry-after", "")
        raise ProviderError(f"HTTP 429, rate limit reached. {e.message}", 429, True, float(after) if after.replace(".", "", 1).isdigit() else None) from None
    except (anthropic.BadRequestError, anthropic.AuthenticationError, anthropic.PermissionDeniedError, anthropic.NotFoundError) as e:
        raise ProviderError(f"HTTP {e.status_code}. {e.message}", e.status_code, False) from None
    except anthropic.APIStatusError as e:
        raise ProviderError(f"HTTP {e.status_code}. {e.message}", e.status_code, e.status_code >= 500) from None
    except anthropic.APIConnectionError as e:
        raise ProviderError(f"network error ({type(e).__name__}).", retryable=True) from None
    if response.stop_reason == "refusal":
        raise ProviderError("the model declined to answer this request.", retryable=False)
    answer = next((block.text for block in response.content if block.type == "text"), "")
    if not answer:
        raise ProviderError(f"the response held no text (stop reason: {response.stop_reason}).")
    return answer.strip(), {"usage": {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens,
                                      "thoughts_tokens": 0},  # thinking is already inside output_tokens on this API
                            "served_by": response.model}


def text(ctx: Ctx, stage: str, unit: str, prompt: str, *, kind: str, parts: list[tuple[str, bytes]] | None = None,
         system: str | None = None, json_mode: bool = False, schema: dict | None = None, temperature: float = 0.2,
         model: str | None = None) -> tuple[str, dict]:
    """One text answer. `parts` are images or audio the model should look at or listen to. A `text/plain` part is a label between them.

    `kind` names the job (translate, judge, transcribe). It is logged, and tells the mock what to answer.
    A model id that starts with `claude-` goes to the Claude API, where `schema` makes the answer valid JSON of
    that shape. Any other id goes to the Gemini API, where `json_mode` asks for JSON and the answer is parsed tolerantly.
    """
    model = model or ctx.sb["models"]["text"]
    parts = parts or []
    on_claude = model.startswith("claude-")
    params = {"kind": kind, "json_mode": json_mode or bool(schema), "prompt_sha": sha(prompt)[:12],
              "inputs": [mime for mime, _ in parts if mime != "text/plain"]}
    if not on_claude:
        params["temperature"] = temperature  # this Claude model sets its own sampling, so there is none to log

    def claude() -> tuple[str, dict]:
        return _claude(model, prompt, parts, system, schema)

    def real() -> tuple[str, dict]:
        content = [{"text": data.decode("utf-8")} if mime == "text/plain"  # a label between two clips or pictures
                   else {"inlineData": {"mimeType": mime, "data": base64.b64encode(data).decode("ascii")}} for mime, data in parts]
        body: dict[str, Any] = {"contents": [{"role": "user", "parts": [*content, {"text": prompt}]}],
                                "generationConfig": {"temperature": temperature}}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        resp = _post(f"{GEMINI}/models/{model}:generateContent", {"x-goog-api-key": _env("GEMINI_API_KEY")}, json_body=body)
        data = _json(resp)
        try:
            out = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError, TypeError):
            raise ProviderError("the response held no text: " + " ".join(resp.text.split())[:200]) from None
        usage = data.get("usageMetadata", {})
        return out.strip(), {"usage": {"input_tokens": usage.get("promptTokenCount"), "output_tokens": usage.get("candidatesTokenCount"),
                                       "thoughts_tokens": usage.get("thoughtsTokenCount")}}  # thinking is billed as output

    def mock() -> tuple[str, dict]:
        if kind == "transcribe":
            note = wav_note(parts[-1][1]) if parts else None
            return note or "mock transcript", {"usage": {}}
        if kind == "judge":
            h = int(sha([prompt, [sha(d.hex())[:8] for _, d in parts]])[:8], 16)
            scores = {"elements": [], "border": False, "text_in_image": False, "wrong_setting": "", "anatomy": "",
                      "character_match": 3 + h % 3, "prompt_adherence": 3 + (h >> 3) % 3, "artifacts": 3 + (h >> 6) % 3, "notes": "mock judge"}
            return json.dumps(scores), {"usage": {}}
        if kind == "describe_music":
            return json.dumps({"vocals": False, "instruments": ["mock instrument"], "tempo": "slow", "mood": "mock, calm, plain",
                               "busy_moments": [], "notes": "mock listener"}), {"usage": {}}
        if kind == "subtitle_check":
            return json.dumps({"literal": "mock literal translation", "faithful": True, "differences": []}), {"usage": {}}
        return "[mock translation] " + prompt.splitlines()[-1][:60], {"usage": {}}

    return model_call(ctx, stage=stage, unit=unit, provider="mock" if ctx.mock else "anthropic" if on_claude else "gemini", model=model,
                      params=params, seed=None, fn=mock if ctx.mock else claude if on_claude else real)


# ----------------------------------------------------------------------------- images


def _mock_image(ctx: Ctx, prompt: str, width: int, height: int, seed: int | None, label: str) -> bytes:
    """A flat colour card with a lighter box in the centre and the unit name on it. Made with ffmpeg."""
    h = sha([prompt, seed])
    bg, box = h[:6], h[6:12]
    tmp = ctx.out / "tmp" / f"mock-{uuid.uuid4().hex[:8]}.jpg"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    base = f"drawbox=x=iw/4:y=ih/4:w=iw/2:h=ih/2:color=0x{box}@0.9:t=fill"
    words = re.sub(r"[^A-Za-z0-9 _-]", "", label)[:24]
    labelled = base + f",drawtext=text='{words}':fontsize=h/14:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2"
    src = ["-f", "lavfi", "-i", f"color=c=0x{bg}:s={width}x{height}:d=1"]
    try:
        ff([*src, "-vf", labelled, "-frames:v", "1", "-q:v", "3", str(tmp)])
    except PipelineError:  # no usable font on this machine: leave the label off
        ff([*src, "-vf", base, "-frames:v", "1", "-q:v", "3", str(tmp)])
    raw = tmp.read_bytes()
    tmp.unlink()
    return raw


def image(ctx: Ctx, stage: str, unit: str, prompt: str, *, width: int, height: int, seed: int | None,
          refs: list[bytes] | None = None, model: str | None = None) -> tuple[bytes, dict]:
    """Text to image, optionally steered by reference images. Returns image bytes (JPEG or PNG)."""
    model = model or ctx.sb["models"]["image"]
    refs = refs or []
    multipart = "flux-2" in model  # FLUX.2 on Workers AI takes multipart forms and reference images
    params = {"width": width, "height": height, "refs": len(refs) if multipart else 0, "prompt_sha": sha(prompt)[:12],
              "megapixels": round(width * height / 1e6, 3)}

    def real() -> tuple[bytes, dict]:
        url = CLOUDFLARE.format(account=_env("CLOUDFLARE_ACCOUNT_ID"), model=model)
        headers = {"Authorization": "Bearer " + _env("CLOUDFLARE_API_TOKEN")}

        def send(with_seed: bool) -> Any:
            if multipart:
                form: list = [("prompt", (None, prompt)), ("width", (None, str(width))), ("height", (None, str(height)))]
                if with_seed and seed is not None:
                    form.append(("seed", (None, str(seed))))
                form += [(f"input_image_{i}", (f"ref{i}.jpg", data, "image/jpeg")) for i, data in enumerate(refs[:4])]
                return _post(url, headers, files=form)
            body = {"prompt": prompt[:2048], "steps": 4}
            if with_seed and seed is not None:
                body["seed"] = seed
            return _post(url, headers, json_body=body)

        seed_applied = seed is not None
        try:
            resp = send(True)
        except ProviderError as e:
            if e.status == 400 and seed is not None:
                resp, seed_applied = send(False), False  # rejected with a seed, accepted without: say so in the log
            else:
                raise
        if resp.headers.get("content-type", "").startswith("image/"):
            raw = resp.content
        else:
            data = _json(resp)
            result = data.get("result", data) if isinstance(data, dict) else {}
            b64 = result.get("image") if isinstance(result, dict) else None
            if not b64:
                raise ProviderError("the response held no image: " + " ".join(resp.text.split())[:200])
            raw = base64.b64decode(b64)
        return raw, {"image_bytes": len(raw), "format": image_ext(raw), "seed_applied": seed_applied}

    def mock() -> tuple[bytes, dict]:
        raw = _mock_image(ctx, prompt, width, height, seed, unit)
        return raw, {"image_bytes": len(raw), "format": image_ext(raw), "seed_applied": True}

    return model_call(ctx, stage=stage, unit=unit, provider="mock" if ctx.mock else "cloudflare", model=model,
                      params=params, seed=seed, fn=mock if ctx.mock else real)
