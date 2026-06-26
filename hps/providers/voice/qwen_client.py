import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

def qwen_config() -> Dict[str, Any]:
    region = os.getenv("QWEN_REGION", "singapore").lower().strip()
    workspace = os.getenv("QWEN_WORKSPACE_ID", "").strip()
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()

    if region in ("beijing", "china", "cn"):
        base = f"https://{workspace}.cn-beijing.maas.aliyuncs.com/api/v1"
    else:
        base = f"https://{workspace}.ap-southeast-1.maas.aliyuncs.com/api/v1"

    return {
        "region": region,
        "workspace": workspace,
        "api_key": api_key,
        "base_url": base,
        "tts_model": os.getenv("QWEN_TTS_MODEL", "qwen3-tts-flash"),
        "tts_instruct_model": os.getenv("QWEN_TTS_INSTRUCT_MODEL", "qwen3-tts-instruct-flash"),
        "voice_design_model": os.getenv("QWEN_VOICE_DESIGN_MODEL", "qwen-voice-design"),
        "voice_design_target_model": os.getenv("QWEN_VOICE_DESIGN_TARGET_MODEL", "qwen3-tts-vd-2026-01-26"),
        "default_voice": os.getenv("QWEN_DEFAULT_VOICE", "Cherry"),
    }

def check_config() -> Dict[str, Any]:
    cfg = qwen_config()
    missing = []
    if not cfg["api_key"]:
        missing.append("DASHSCOPE_API_KEY")
    if not cfg["workspace"]:
        missing.append("QWEN_WORKSPACE_ID")
    return {
        "ok": len(missing) == 0,
        "missing": missing,
        "config": {k: ("***" if k == "api_key" and cfg[k] else v) for k, v in cfg.items()},
    }

def _safe_json_dump(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        path.write_text(str(obj), encoding="utf-8")

def _download_url(url: str, output_path: Path, api_key: str = "") -> bool:
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    response = requests.get(url, headers=headers, timeout=180)
    if response.status_code == 200 and response.content:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        return True
    return False

def _walk_json(obj: Any, path: str = ""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_json(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_json(v, f"{path}[{i}]")
    else:
        yield path, obj

def _get_nested(data: Any, *keys):
    cur = data
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur

def extract_audio_from_qwen_response(data: Any, output_path: Path, api_key: str = "") -> Dict[str, Any]:
    result = {"saved": False, "path": "", "method": "", "candidate": ""}

    known_url = _get_nested(data, "output", "audio", "url")
    if isinstance(known_url, str) and known_url.startswith("http"):
        result["candidate"] = known_url
        if _download_url(known_url, output_path, api_key=api_key):
            result.update({"saved": True, "path": str(output_path), "method": "download:output.audio.url"})
            return result

    known_data = _get_nested(data, "output", "audio", "data")
    if isinstance(known_data, str) and len(known_data) > 100:
        try:
            output_path.write_bytes(base64.b64decode(known_data))
            result.update({"saved": True, "path": str(output_path), "method": "base64:output.audio.data"})
            return result
        except Exception:
            pass

    audios = _get_nested(data, "output", "audios")
    if isinstance(audios, list):
        for i, audio in enumerate(audios):
            if not isinstance(audio, dict):
                continue
            url = audio.get("url")
            if isinstance(url, str) and url.startswith("http"):
                result["candidate"] = url
                if _download_url(url, output_path, api_key=api_key):
                    result.update({"saved": True, "path": str(output_path), "method": f"download:output.audios[{i}].url"})
                    return result
            b64 = audio.get("data")
            if isinstance(b64, str) and len(b64) > 100:
                try:
                    output_path.write_bytes(base64.b64decode(b64))
                    result.update({"saved": True, "path": str(output_path), "method": f"base64:output.audios[{i}].data"})
                    return result
                except Exception:
                    pass

    for key_path, value in _walk_json(data):
        if not isinstance(value, str):
            continue
        low_key = key_path.lower()
        if value.startswith("http") and any(token in low_key for token in ["audio", "url", "file"]):
            result["candidate"] = value
            if _download_url(value, output_path, api_key=api_key):
                result.update({"saved": True, "path": str(output_path), "method": f"download:{key_path}"})
                return result

    for key_path, value in _walk_json(data):
        if not isinstance(value, str):
            continue
        low_key = key_path.lower()
        if any(token in low_key for token in ["audio", "data", "base64"]) and len(value) > 100:
            try:
                output_path.write_bytes(base64.b64decode(value))
                result.update({"saved": True, "path": str(output_path), "method": f"base64:{key_path}"})
                return result
            except Exception:
                pass

    return result

def build_tts_payload(text: str, voice: str, instructions: Optional[str]) -> Dict[str, Any]:
    cfg = qwen_config()
    model = cfg["tts_instruct_model"] if instructions else cfg["tts_model"]
    payload = {
        "model": model,
        "input": {
            "text": text,
            "voice": voice,
        },
        "parameters": {
            "sample_rate": 24000,
            "response_format": "wav",
        },
    }
    if instructions:
        payload["input"]["instructions"] = instructions
        payload["input"]["optimize_instructions"] = True
    return payload

def synthesize_qwen_tts(text: str, voice: str, output_path: Path, instructions: Optional[str] = None, dry_run: bool = True) -> Dict[str, Any]:
    cfg = qwen_config()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_tts_payload(text=text, voice=voice, instructions=instructions)

    if dry_run:
        sidecar = output_path.with_suffix(".dryrun.json")
        _safe_json_dump({"endpoint": "not called - dry run", "payload": payload}, sidecar)
        return {
            "ok": True,
            "dry_run": True,
            "message": "Dry run only. No Qwen request was sent.",
            "model": payload["model"],
            "voice": voice,
            "chars": len(text),
            "output_path": str(output_path),
            "payload_sidecar": str(sidecar),
            "status": "dry_run",
        }

    check = check_config()
    if not check["ok"]:
        raise RuntimeError("Missing Qwen configuration: " + ", ".join(check["missing"]))

    url = cfg["base_url"] + "/services/aigc/multimodal-generation/generation"
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers, timeout=180)

    sidecar = output_path.with_suffix(".response.json")
    try:
        body = response.json()
    except Exception:
        body = {"raw_text": response.text[:10000]}

    wrapped = {
        "request_url": url,
        "request_payload": payload,
        "status_code": response.status_code,
        "response_headers": dict(response.headers),
        "response_body": body,
    }
    _safe_json_dump(wrapped, sidecar)

    if response.status_code != 200:
        return {
            "ok": False,
            "dry_run": False,
            "message": f"Qwen TTS HTTP status {response.status_code}. Response saved for inspection.",
            "response_sidecar": str(sidecar),
            "status": "error",
        }

    extracted = extract_audio_from_qwen_response(body, output_path, api_key=cfg["api_key"])
    return {
        "ok": extracted["saved"],
        "dry_run": False,
        "message": "Audio saved." if extracted["saved"] else "Response received but audio was not auto-extracted. Inspect sidecar.",
        "audio_path": extracted["path"],
        "audio_extraction": extracted,
        "response_sidecar": str(sidecar),
        "status": "generated" if extracted["saved"] else "needs_inspection",
    }

def create_voice_design(voice_prompt: str, preferred_name: str, preview_text: str, output_dir: Path, dry_run: bool = True) -> Dict[str, Any]:
    cfg = qwen_config()
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": cfg["voice_design_model"],
        "input": {
            "action": "create_voice",
            "target_model": cfg["voice_design_target_model"],
            "preferred_name": preferred_name,
            "voice_prompt": voice_prompt,
            "preview_text": preview_text,
        },
        "parameters": {
            "sample_rate": 24000,
            "response_format": "wav",
        },
    }

    if dry_run:
        sidecar = output_dir / f"{preferred_name}_voice_design_dryrun.json"
        _safe_json_dump({"endpoint": "not called - dry run", "payload": payload}, sidecar)
        return {"ok": True, "dry_run": True, "message": "Dry run only. No Qwen request was sent.", "payload_sidecar": str(sidecar)}

    check = check_config()
    if not check["ok"]:
        raise RuntimeError("Missing Qwen configuration: " + ", ".join(check["missing"]))

    url = cfg["base_url"] + "/services/audio/tts/customization"
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers, timeout=180)

    try:
        body = response.json()
    except Exception:
        body = {"raw_text": response.text[:10000]}

    sidecar = output_dir / f"{preferred_name}_voice_design_response.json"
    _safe_json_dump({"request_url": url, "request_payload": payload, "status_code": response.status_code, "response_body": body}, sidecar)

    if response.status_code != 200:
        return {"ok": False, "dry_run": False, "message": f"Voice design HTTP {response.status_code}. Inspect sidecar.", "response_sidecar": str(sidecar)}

    preview_path = output_dir / f"{preferred_name}_preview.wav"
    extracted = extract_audio_from_qwen_response(body, preview_path, api_key=cfg["api_key"])
    voice = None
    for key_path, value in _walk_json(body):
        if key_path.lower().endswith(("voice", "voice_id", "voiceid", "voice_name")) and isinstance(value, str):
            voice = value
            break

    return {
        "ok": True,
        "dry_run": False,
        "voice": voice,
        "preview_path": extracted["path"],
        "audio_extraction": extracted,
        "response_sidecar": str(sidecar),
    }
