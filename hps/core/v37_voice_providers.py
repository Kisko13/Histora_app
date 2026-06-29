from __future__ import annotations

import csv
import html
import json
import os
import shutil
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from hps.core.block_state import approved_voice_path
from hps.core.voice_pipeline import generate_voice_for_block

AUDIO_EXTS = {'.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg'}


def _get(row: Any, key: str, default=None):
    try:
        return row[key]
    except Exception:
        return default


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def _rel(root: Path, p: Path | str | None) -> str:
    if not p:
        return ''
    pp = Path(p)
    try:
        return str(pp.relative_to(root)).replace('\\', '/')
    except Exception:
        return str(pp).replace('\\', '/')


def read_env(root: Path | str) -> dict[str, str]:
    root = Path(root)
    data: dict[str, str] = {}
    for env_path in [root / '.env', Path.cwd() / '.env']:
        try:
            if env_path.exists():
                for raw in env_path.read_text(encoding='utf-8', errors='ignore').splitlines():
                    line = raw.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    k, v = line.split('=', 1)
                    data[k.strip()] = v.strip().strip('"').strip("'")
        except Exception:
            pass
    for k, v in os.environ.items():
        data.setdefault(k, v)
    return data


def provider_chain_from_env_v37(root: Path | str, explicit: str | None = None) -> list[str]:
    env = read_env(root)
    raw = explicit or env.get('V37_VOICE_PROVIDER_CHAIN') or env.get('V36_PRIMARY_VOICE_PROVIDER', 'qwen') + ',' + env.get('V36_BACKUP_VOICE_PROVIDERS', 'mock')
    chain: list[str] = []
    for part in raw.replace(';', ',').split(','):
        p = part.strip().lower()
        if p and p not in chain:
            chain.append(p)
    return chain or ['qwen', 'mock']


def _ollama_status(root: Path | str) -> dict[str, Any]:
    env = read_env(root)
    host = env.get('OLLAMA_HOST') or 'http://127.0.0.1:11434'
    model = env.get('OLLAMA_MODEL') or env.get('QWEN_MODEL') or 'qwen2.5:7b'
    timeout = float(env.get('OLLAMA_TIMEOUT_SECONDS') or '3')
    status: dict[str, Any] = {'host': host, 'model': model, 'available': False, 'model_found': False, 'models': [], 'error': ''}
    try:
        req = urllib.request.Request(host.rstrip('/') + '/api/tags')
        with urllib.request.urlopen(req, timeout=timeout) as res:
            payload = json.loads(res.read().decode('utf-8', errors='ignore'))
        models = [m.get('name', '') for m in payload.get('models', []) if isinstance(m, dict)]
        status['models'] = models
        status['available'] = True
        status['model_found'] = model in models or any(str(x).startswith(model) for x in models)
        if not status['model_found']:
            status['error'] = f'Ollama is running, but model {model} was not found.'
    except Exception as exc:
        status['error'] = str(exc)
    return status


def _tool_status(root: Path | str) -> dict[str, Any]:
    env = read_env(root)
    ffmpeg = env.get('FFMPEG_EXE') or shutil.which('ffmpeg') or ''
    piper = env.get('PIPER_EXE') or shutil.which('piper') or ''
    piper_voice = env.get('PIPER_VOICE') or env.get('PIPER_MODEL') or ''
    ollama_exe = env.get('OLLAMA_EXE') or shutil.which('ollama') or ''
    return {
        'ffmpeg': {'path': ffmpeg, 'available': bool(ffmpeg and Path(ffmpeg).exists()) or bool(shutil.which('ffmpeg'))},
        'ollama_exe': {'path': ollama_exe, 'available': bool(ollama_exe)},
        'piper': {'path': piper, 'voice': piper_voice, 'available': bool(piper and piper_voice and Path(piper).exists() and Path(piper_voice).exists())},
        'mock': {'available': True, 'note': 'Always available. Produces test audio only, not production narration.'},
        'qwen': {'available_for_planning': _ollama_status(root).get('available', False), 'audio_synthesis': False, 'note': 'Qwen/Ollama is an LLM. It can create voice direction/prompts, but it does not synthesize WAV by itself.'},
    }


def _audio_versions(db, block_id: str) -> list[dict[str, Any]]:
    try:
        return [dict(v) for v in db.audio_versions(block_id)]
    except Exception:
        return []


def _block_text(block: Any) -> str:
    return (_get(block, 'text', '') or '').strip()


def _block_voice_row(db, root: Path, block: Any) -> dict[str, Any]:
    bid = _get(block, 'id', '')
    text = _block_text(block)
    approved = approved_voice_path(db, bid)
    versions = _audio_versions(db, bid)
    # Prefer latest real audio over txt prompt artifacts.
    audio_versions = [v for v in versions if Path(str(v.get('rel_path') or v.get('path') or '')).suffix.lower() in AUDIO_EXTS]
    latest = audio_versions[-1] if audio_versions else (versions[-1] if versions else {})
    latest_rel = str(latest.get('rel_path') or latest.get('path') or '')
    return {
        'block_id': bid,
        'scene_id': _get(block, 'scene_id', ''),
        'scene_title': _get(block, 'scene_title', ''),
        'character': _get(block, 'character_id', ''),
        'voice_state': _get(block, 'voice_state_id', ''),
        'title': _get(block, 'title', '') or _get(block, 'scene_title', '') or bid,
        'word_count': len(text.split()),
        'chars': len(text),
        'has_story': bool(text),
        'voice_ok': bool(approved),
        'approved_voice': _rel(root, approved) if approved else '',
        'latest_version': latest_rel,
        'version_count': len(audio_versions),
        'status': 'approved' if approved else ('needs_generation' if not audio_versions else 'needs_review'),
        'next_task': 'done' if approved else ('generate voice' if not audio_versions else 'review/approve latest voice'),
    }


def build_v37_voice_provider_health(db) -> dict[str, Any]:
    root = Path(db.root_dir)
    out_dir = root / 'exports' / 'v37_voice'
    production = root / 'production'
    out_dir.mkdir(parents=True, exist_ok=True)
    chain = provider_chain_from_env_v37(root)
    ollama = _ollama_status(root)
    tools = _tool_status(root)
    blocks = list(db.blocks())
    rows = [_block_voice_row(db, root, b) for b in blocks]
    summary = {
        'blocks_total': len(rows),
        'approved': sum(1 for r in rows if r['voice_ok']),
        'waiting_review': sum(1 for r in rows if r['status'] == 'needs_review'),
        'needs_generation': sum(1 for r in rows if r['status'] == 'needs_generation'),
        'pending_chars': sum(r['chars'] for r in rows if not r['voice_ok']),
    }
    report = {
        'version': 'v37_voice_provider_manager',
        'built_at': datetime.now().isoformat(timespec='seconds'),
        'root': str(root),
        'provider_chain': chain,
        'ollama': ollama,
        'tools': tools,
        'summary': summary,
        'important_note': 'Qwen is kept as primary planning provider. For real audio you need a TTS backend such as Piper/Kokoro/XTTS/ElevenLabs/OpenAI. Mock is only a safety fallback.',
        'blocks': rows,
    }
    _write_json(production / 'v37_voice_provider_health_latest.json', report)
    _write_json(out_dir / 'voice_provider_health.json', report)
    html_path = out_dir / 'voice_provider_health.html'
    html_path.write_text(_health_html(report), encoding='utf-8')
    report['html_path'] = str(html_path)
    report['report_path'] = str(production / 'v37_voice_provider_health_latest.json')
    return report


def _ollama_generate(root: Path, prompt: str) -> dict[str, Any]:
    env = read_env(root)
    host = env.get('OLLAMA_HOST') or 'http://127.0.0.1:11434'
    model = env.get('OLLAMA_MODEL') or env.get('QWEN_MODEL') or 'qwen2.5:7b'
    timeout = float(env.get('OLLAMA_TIMEOUT_SECONDS') or '60')
    payload = json.dumps({'model': model, 'prompt': prompt, 'stream': False}).encode('utf-8')
    req = urllib.request.Request(host.rstrip('/') + '/api/generate', data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        data = json.loads(res.read().decode('utf-8', errors='ignore'))
    return data


def _register_audio_version(db, block_id: str, rel_path: str, provider: str, cost: float = 0.0) -> None:
    try:
        db.add_audio_version(block_id, rel_path=rel_path, provider=provider, cost_usd=cost)
        return
    except Exception:
        pass
    try:
        db.add_audio_version(block_id, rel_path, provider, cost)
        return
    except Exception:
        pass
    # Last-resort: generation will still create a file; UI refresh may pick it up from folder in later code.


def _write_qwen_direction(db, root: Path, block_id: str, text: str, voice_state: str, character: str) -> dict[str, Any]:
    prompt = f"""You are preparing voice direction for historical first-person narration.
Do not rewrite the story. Return concise voice direction only.
Character: {character}
Voice state: {voice_state}
Style: deep restrained male narrator, slow immersive delivery, tired human realism.
Text:
{text}

Return:
- delivery notes
- pacing notes
- emotional pressure
- pronunciation warnings if any
"""
    out_dir = root / 'assets' / 'voice_prompts'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f'{block_id}_qwen_voice_direction.txt'
    try:
        data = _ollama_generate(root, prompt)
        direction = str(data.get('response') or '').strip()
        out_path.write_text(direction or prompt, encoding='utf-8')
        return {'ok': True, 'path': out_path, 'text': direction, 'error': ''}
    except Exception as exc:
        out_path.write_text(prompt, encoding='utf-8')
        return {'ok': False, 'path': out_path, 'text': prompt, 'error': str(exc)}


def _piper_synthesize(db, root: Path, block_id: str, text: str) -> dict[str, Any]:
    env = read_env(root)
    piper = env.get('PIPER_EXE') or shutil.which('piper') or ''
    voice = env.get('PIPER_VOICE') or env.get('PIPER_MODEL') or ''
    if not piper or not Path(piper).exists():
        raise RuntimeError('Piper executable not found. Set PIPER_EXE in .env.')
    if not voice or not Path(voice).exists():
        raise RuntimeError('Piper voice/model not found. Set PIPER_VOICE in .env.')
    raw_dir = root / 'assets' / 'audio_raw'
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_path = raw_dir / f'{block_id}_piper_v{int(time.time())}.wav'
    cmd = [piper, '--model', voice, '--output_file', str(out_path)]
    proc = subprocess.run(cmd, input=text, text=True, capture_output=True, timeout=float(env.get('PIPER_TIMEOUT_SECONDS') or '180'))
    if proc.returncode != 0 or not out_path.exists():
        raise RuntimeError((proc.stderr or proc.stdout or 'Piper failed').strip())
    rel = _rel(root, out_path)
    _register_audio_version(db, block_id, rel, 'piper')
    return {'audio_rel_path': rel, 'path': str(out_path)}


def _mock_synthesize(db, root: Path, block_id: str) -> dict[str, Any]:
    out = generate_voice_for_block(db, block_id, provider='mock')
    rel = str(out.get('audio_rel_path') or out.get('rel_path') or '') if isinstance(out, dict) else ''
    return {'audio_rel_path': rel}


def _try_provider_v37(db, block: Any, provider: str) -> dict[str, Any]:
    root = Path(db.root_dir)
    block_id = _get(block, 'id', '')
    text = _block_text(block)
    voice_state = _get(block, 'voice_state_id', '')
    character = _get(block, 'character_id', '')
    start = time.time()
    res = {'provider': provider, 'ok': False, 'audio_rel_path': '', 'artifact_rel_path': '', 'error': '', 'seconds': 0.0}
    try:
        if provider == 'qwen':
            q = _write_qwen_direction(db, root, block_id, text, voice_state, character)
            res['artifact_rel_path'] = _rel(root, q.get('path'))
            if not q.get('ok'):
                raise RuntimeError('Qwen/Ollama not reachable: ' + q.get('error', ''))
            raise RuntimeError('Qwen produced voice direction only. It is not a TTS audio provider; continuing to backup TTS provider.')
        if provider == 'piper':
            out = _piper_synthesize(db, root, block_id, text)
            res['audio_rel_path'] = out.get('audio_rel_path', '')
            res['ok'] = True
            return res
        if provider == 'mock':
            out = _mock_synthesize(db, root, block_id)
            res['audio_rel_path'] = out.get('audio_rel_path', '')
            res['ok'] = True
            return res
        raise RuntimeError(f'Provider {provider} is not implemented in V37. Add piper or mock as backup.')
    except Exception as exc:
        res['error'] = str(exc)
        return res
    finally:
        res['seconds'] = round(time.time() - start, 2)


def generate_v37_voice_queue(db, limit: int | None = 5, provider_chain: list[str] | None = None, progress=None) -> dict[str, Any]:
    root = Path(db.root_dir)
    out_dir = root / 'exports' / 'v37_voice'
    out_dir.mkdir(parents=True, exist_ok=True)
    chain = provider_chain or provider_chain_from_env_v37(root)
    blocks = list(db.blocks())
    rows = [_block_voice_row(db, root, b) for b in blocks]
    by_id = {_get(b, 'id', ''): b for b in blocks}
    pending_rows = [r for r in rows if not r['voice_ok'] and r['has_story']]
    if limit is not None and limit > 0:
        pending_rows = pending_rows[:limit]
    attempts: list[dict[str, Any]] = []
    generated = 0
    failed = 0
    total = len(pending_rows)
    for idx, row in enumerate(pending_rows, 1):
        bid = row['block_id']
        if progress:
            progress('voice', bid, idx, total)
        block = by_id.get(bid)
        item = {'block_id': bid, 'scene_title': row.get('scene_title', ''), 'character': row.get('character', ''), 'providers': [], 'ok': False, 'chosen_provider': '', 'audio_rel_path': ''}
        for provider in chain:
            p = provider.strip().lower()
            if not p:
                continue
            res = _try_provider_v37(db, block, p)
            item['providers'].append(res)
            if res.get('ok'):
                item['ok'] = True
                item['chosen_provider'] = p
                item['audio_rel_path'] = res.get('audio_rel_path', '')
                generated += 1
                break
        if not item['ok']:
            failed += 1
        attempts.append(item)
    refreshed = build_v37_voice_provider_health(db)
    report = {
        'version': 'v37_voice_generation_report',
        'built_at': datetime.now().isoformat(timespec='seconds'),
        'provider_chain': chain,
        'requested_blocks': total,
        'generated_blocks': generated,
        'failed_blocks': failed,
        'attempts': attempts,
        'post_generation_summary': refreshed.get('summary', {}),
        'note': 'Qwen is treated as voice-direction provider. Real WAV comes from Piper or another TTS backend, then mock if configured.',
    }
    report_path = out_dir / 'voice_generation_report_latest.json'
    _write_json(report_path, report)
    report['report_path'] = str(report_path)
    report['dashboard_path'] = refreshed.get('html_path', '')
    return report


def test_v37_voice_provider(db, text: str, provider_chain: list[str] | None = None) -> dict[str, Any]:
    root = Path(db.root_dir)
    out_dir = root / 'exports' / 'v37_voice' / 'provider_tests'
    out_dir.mkdir(parents=True, exist_ok=True)
    # Use a fake minimal block-like dict so tests don't mutate a production block unless mock pipeline requires DB block id.
    # For mock we use the first real block because existing mock generation is DB-driven.
    blocks = list(db.blocks())
    first = blocks[0] if blocks else {'id': 'test', 'text': text, 'character_id': 'test', 'voice_state_id': 'narrator_slow', 'scene_title': 'Provider Test'}
    test_block = dict(first) if not isinstance(first, dict) else dict(first)
    test_block['text'] = text
    chain = provider_chain or provider_chain_from_env_v37(root)
    attempts: list[dict[str, Any]] = []
    chosen = ''
    audio_rel = ''
    for p in chain:
        if p == 'qwen':
            q = _write_qwen_direction(db, root, 'provider_test', text, 'narrator_slow', 'test')
            attempts.append({'provider': p, 'ok': False, 'artifact_rel_path': _rel(root, q.get('path')), 'error': 'Qwen created direction only; not audio.' if q.get('ok') else q.get('error', '')})
            continue
        if p == 'piper':
            try:
                out = _piper_synthesize(db, root, 'provider_test', text)
                chosen = 'piper'; audio_rel = out.get('audio_rel_path', '')
                attempts.append({'provider': p, 'ok': True, 'audio_rel_path': audio_rel, 'error': ''})
                break
            except Exception as exc:
                attempts.append({'provider': p, 'ok': False, 'error': str(exc)})
                continue
        if p == 'mock':
            try:
                # Create an isolated simple WAV without touching DB.
                wav = out_dir / f'provider_test_mock_{int(time.time())}.wav'
                _write_silence_wav(wav, seconds=2.0)
                chosen = 'mock'; audio_rel = _rel(root, wav)
                attempts.append({'provider': p, 'ok': True, 'audio_rel_path': audio_rel, 'error': ''})
                break
            except Exception as exc:
                attempts.append({'provider': p, 'ok': False, 'error': str(exc)})
                continue
        attempts.append({'provider': p, 'ok': False, 'error': f'Provider {p} is not implemented in V37.'})
    report = {
        'version': 'v37_voice_provider_test',
        'built_at': datetime.now().isoformat(timespec='seconds'),
        'text': text,
        'provider_chain': chain,
        'chosen_provider': chosen,
        'audio_rel_path': audio_rel,
        'audio_path': str(root / audio_rel) if audio_rel else '',
        'attempts': attempts,
    }
    path = out_dir / 'provider_test_latest.json'
    _write_json(path, report)
    report['report_path'] = str(path)
    return report


def _write_silence_wav(path: Path, seconds: float = 2.0) -> None:
    import wave
    sample_rate = 48000
    frames = int(sample_rate * seconds)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(b'\x00\x00' * frames)


def _pct(done: int, total: int) -> int:
    return int(round((done / total) * 100)) if total else 0


def _bar(done: int, total: int, width: int = 24) -> str:
    if not total:
        return '░' * width
    filled = int(round(done / total * width))
    return '█' * filled + '░' * max(0, width - filled)


def _health_html(report: dict[str, Any]) -> str:
    s = report['summary']
    tools = report.get('tools', {})
    ollama = report.get('ollama', {})
    rows = ''.join(
        f"<tr><td>{html.escape(k)}</td><td>{'YES' if v.get('available') or v.get('available_for_planning') else 'NO'}</td><td>{html.escape(json.dumps(v, ensure_ascii=False))}</td></tr>"
        for k, v in tools.items()
    )
    chain = ' → '.join(report.get('provider_chain', []))
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>Histora V37 Voice Provider Health</title>
<style>body{{font-family:Segoe UI,Arial;background:#111;color:#eee;margin:22px}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}} .card{{background:#1d1d1d;border:1px solid #333;border-radius:8px;padding:14px}} .num{{font-size:28px;font-weight:700}} .num span{{font-size:15px;color:#8bdcff}} pre{{color:#4cc2ff;font-size:18px}} .next{{background:#202a20;border:1px solid #375f37;padding:14px;border-radius:8px;margin:16px 0}} .warn{{background:#2a2414;border:1px solid #665c23;padding:14px;border-radius:8px;margin:16px 0}} table{{width:100%;border-collapse:collapse;margin-top:18px}} th,td{{border:1px solid #333;padding:7px;text-align:left}} th{{background:#222;color:#8bdcff}}</style></head><body>
<h1>Histora V37 Voice Provider Health</h1>
<div class=next><b>Provider chain:</b> {html.escape(chain)}<br><b>Recommended:</b> qwen,piper,mock if you want Qwen voice direction plus local TTS fallback.</div>
<div class=warn><b>Reality check:</b> Qwen/Ollama is not a voice synthesizer. It can prepare direction/prompts. Real audio must come from Piper/Kokoro/XTTS/paid TTS. Mock is testing only.<br>Ollama: {'AVAILABLE' if ollama.get('available') else 'NOT AVAILABLE'} | model found: {'YES' if ollama.get('model_found') else 'NO'} | host: {html.escape(str(ollama.get('host','')))} | model: {html.escape(str(ollama.get('model','')))} | error: {html.escape(str(ollama.get('error','')))}</div>
<div class=grid>
<div class=card><h3>Approved voices</h3><div class=num>{s['approved']}/{s['blocks_total']} <span>{_pct(s['approved'],s['blocks_total'])}%</span></div><pre>{_bar(s['approved'],s['blocks_total'])}</pre></div>
<div class=card><h3>Waiting review</h3><div class=num>{s['waiting_review']}/{s['blocks_total']} <span>{_pct(s['waiting_review'],s['blocks_total'])}%</span></div><pre>{_bar(s['waiting_review'],s['blocks_total'])}</pre></div>
<div class=card><h3>Needs generation</h3><div class=num>{s['needs_generation']}/{s['blocks_total']} <span>{_pct(s['needs_generation'],s['blocks_total'])}%</span></div><pre>{_bar(s['needs_generation'],s['blocks_total'])}</pre></div>
<div class=card><h3>Pending chars</h3><div class=num>{s['pending_chars']}</div><p>Characters still needing approved narration.</p></div>
</div>
<h2>Provider/tool status</h2><table><tr><th>Tool</th><th>Available</th><th>Details</th></tr>{rows}</table>
</body></html>"""
