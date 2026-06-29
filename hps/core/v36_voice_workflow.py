from __future__ import annotations

import csv
import html
import json
import os
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from hps.core.block_state import approved_voice_path
from hps.core.voice_pipeline import generate_voice_for_block
from hps.pipeline.build import BuildPipeline

AUDIO_EXTS = {'.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg', '.txt'}


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
    p = Path(p)
    try:
        return str(p.relative_to(root)).replace('\\', '/')
    except Exception:
        return str(p).replace('\\', '/')


def _read_env(root: Path) -> dict[str, str]:
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


def provider_chain_from_env(root: Path, explicit: str | None = None) -> list[str]:
    env = _read_env(root)
    if explicit:
        raw = explicit
    else:
        primary = env.get('V36_PRIMARY_VOICE_PROVIDER') or env.get('PRIMARY_VOICE_PROVIDER') or env.get('VOICE_PROVIDER') or 'qwen'
        backups = env.get('V36_BACKUP_VOICE_PROVIDERS') or env.get('VOICE_PROVIDER_BACKUPS') or 'mock'
        raw = primary + ',' + backups
    chain: list[str] = []
    for part in raw.replace(';', ',').split(','):
        p = part.strip().lower()
        if p and p not in chain:
            chain.append(p)
    return chain or ['qwen', 'mock']


def _ollama_status(root: Path) -> dict[str, Any]:
    env = _read_env(root)
    host = env.get('OLLAMA_HOST') or 'http://127.0.0.1:11434'
    model = env.get('OLLAMA_MODEL') or env.get('QWEN_MODEL') or 'qwen2.5:7b'
    status = {'host': host, 'model': model, 'available': False, 'models': [], 'error': ''}
    try:
        req = urllib.request.Request(host.rstrip('/') + '/api/tags')
        with urllib.request.urlopen(req, timeout=2) as res:
            payload = json.loads(res.read().decode('utf-8', errors='ignore'))
        models = [m.get('name', '') for m in payload.get('models', []) if isinstance(m, dict)]
        status['models'] = models
        status['available'] = bool(models)
        status['model_found'] = model in models or any(str(x).startswith(model) for x in models)
    except Exception as exc:
        status['error'] = str(exc)
    return status


def _audio_versions(db, block_id: str) -> list[dict[str, Any]]:
    try:
        return [dict(v) for v in db.audio_versions(block_id)]
    except Exception:
        return []


def _block_voice_row(db, root: Path, block) -> dict[str, Any]:
    bid = _get(block, 'id', '')
    text = (_get(block, 'text', '') or '').strip()
    approved = approved_voice_path(db, bid)
    versions = _audio_versions(db, bid)
    latest = versions[-1] if versions else {}
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
        'latest_version': str(latest.get('rel_path') or latest.get('path') or ''),
        'version_count': len(versions),
        'status': 'approved' if approved else ('needs_generation' if not versions else 'needs_review'),
        'next_task': 'done' if approved else ('generate voice' if not versions else 'review/approve latest voice'),
    }


def build_v36_voiceover_plan(db, provider_chain: list[str] | None = None) -> dict[str, Any]:
    root = Path(db.root_dir)
    production = root / 'production'
    out_dir = root / 'exports' / 'v36_voiceover'
    out_dir.mkdir(parents=True, exist_ok=True)

    chain = provider_chain or provider_chain_from_env(root)
    blocks = list(db.blocks())
    rows = [_block_voice_row(db, root, b) for b in blocks]
    total = len(rows)
    approved = sum(1 for r in rows if r['voice_ok'])
    generated_waiting_review = sum(1 for r in rows if r['status'] == 'needs_review')
    missing = sum(1 for r in rows if r['status'] == 'needs_generation')
    chars_pending = sum(r['chars'] for r in rows if not r['voice_ok'])

    ollama = _ollama_status(root)
    qwen_note = 'Qwen/Ollama is metadata/planning unless your qwen provider can synthesize audio. Mock fallback remains enabled.'
    if 'qwen' in chain and not ollama.get('available'):
        qwen_note = 'Qwen selected, but Ollama is not reachable. Fallback provider will be used if generation is attempted.'

    report = {
        'version': 'v36_voiceover_workflow',
        'built_at': datetime.now().isoformat(timespec='seconds'),
        'root': str(root),
        'provider_chain': chain,
        'primary_provider': chain[0] if chain else '',
        'backup_providers': chain[1:],
        'ollama': ollama,
        'summary': {
            'blocks_total': total,
            'voices_approved': approved,
            'generated_waiting_review': generated_waiting_review,
            'missing_generation': missing,
            'chars_pending': chars_pending,
            'next_action': 'Generate missing voices, then review/approve them block by block.' if approved < total else 'All voices approved.',
            'qwen_note': qwen_note,
        },
        'blocks': rows,
    }

    _write_json(production / 'v36_voiceover_plan_latest.json', report)
    _write_json(out_dir / 'voiceover_plan.json', report)

    csv_path = out_dir / 'voiceover_queue.csv'
    with csv_path.open('w', newline='', encoding='utf-8') as f:
        fields = ['block_id', 'scene_title', 'character', 'voice_state', 'status', 'next_task', 'word_count', 'chars', 'version_count', 'approved_voice', 'latest_version']
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, '') for k in fields})

    html_path = out_dir / 'voiceover_dashboard.html'
    html_path.write_text(_voiceover_html(report), encoding='utf-8')

    review_path = out_dir / 'voice_review_queue.html'
    review_path.write_text(_review_html(report), encoding='utf-8')

    report['report_path'] = str(production / 'v36_voiceover_plan_latest.json')
    report['html_path'] = str(html_path)
    report['review_html_path'] = str(review_path)
    report['csv_path'] = str(csv_path)
    return report


def _try_provider(db, block_id: str, provider: str, progress=None) -> dict[str, Any]:
    start = time.time()
    result: dict[str, Any] = {'provider': provider, 'ok': False, 'error': '', 'audio_rel_path': ''}
    try:
        if provider == 'mock':
            out = generate_voice_for_block(db, block_id, provider='mock')
            result['audio_rel_path'] = str(out.get('audio_rel_path') or out.get('rel_path') or '') if isinstance(out, dict) else ''
            result['ok'] = True
        else:
            # Uses existing provider system. If qwen is implemented in the project it will run;
            # if not, exception is captured and fallback providers continue.
            out = BuildPipeline(db, provider_name=provider, progress=progress).provider.synthesize(db=db, block_id=block_id)
            if isinstance(out, dict):
                result['audio_rel_path'] = str(out.get('audio_rel_path') or out.get('rel_path') or out.get('path') or '')
            result['ok'] = True
    except Exception as exc:
        result['error'] = str(exc)
    result['seconds'] = round(time.time() - start, 2)
    return result


def generate_v36_voice_queue(db, limit: int | None = 5, provider_chain: list[str] | None = None, progress=None) -> dict[str, Any]:
    root = Path(db.root_dir)
    out_dir = root / 'exports' / 'v36_voiceover'
    out_dir.mkdir(parents=True, exist_ok=True)
    chain = provider_chain or provider_chain_from_env(root)

    plan = build_v36_voiceover_plan(db, chain)
    pending = [r for r in plan['blocks'] if not r['voice_ok'] and r['has_story']]
    if limit is not None and limit > 0:
        pending = pending[:limit]

    attempts: list[dict[str, Any]] = []
    generated = 0
    failed = 0
    total = len(pending)
    for idx, row in enumerate(pending, 1):
        bid = row['block_id']
        if progress:
            progress('voice', bid, idx, total)
        block_attempt = {'block_id': bid, 'scene_title': row.get('scene_title', ''), 'character': row.get('character', ''), 'providers': [], 'ok': False, 'chosen_provider': '', 'audio_rel_path': ''}
        for provider in chain:
            res = _try_provider(db, bid, provider, progress=None)
            block_attempt['providers'].append(res)
            if res.get('ok'):
                block_attempt['ok'] = True
                block_attempt['chosen_provider'] = provider
                block_attempt['audio_rel_path'] = res.get('audio_rel_path', '')
                generated += 1
                break
        if not block_attempt['ok']:
            failed += 1
        attempts.append(block_attempt)

    refreshed = build_v36_voiceover_plan(db, chain)
    report = {
        'version': 'v36_voice_generation_report',
        'built_at': datetime.now().isoformat(timespec='seconds'),
        'provider_chain': chain,
        'requested_blocks': total,
        'generated_blocks': generated,
        'failed_blocks': failed,
        'attempts': attempts,
        'post_generation_summary': refreshed.get('summary', {}),
    }
    report_path = out_dir / 'voice_generation_report_latest.json'
    _write_json(report_path, report)
    report['report_path'] = str(report_path)
    report['dashboard_path'] = refreshed.get('html_path', '')
    report['review_html_path'] = refreshed.get('review_html_path', '')
    return report


def _pct(done: int, total: int) -> int:
    return int(round((done / total) * 100)) if total else 0


def _bar(done: int, total: int, width: int = 24) -> str:
    if not total:
        return '░' * width
    filled = int(round(done / total * width))
    return '█' * filled + '░' * max(0, width - filled)


def _voiceover_html(report: dict[str, Any]) -> str:
    s = report['summary']
    rows = '\n'.join(
        f"<tr class='{html.escape(r['status'])}'><td>{html.escape(r['block_id'])}</td><td>{html.escape(r['scene_title'])}</td><td>{html.escape(r['character'])}</td><td>{html.escape(r['voice_state'])}</td><td>{html.escape(r['status'])}</td><td>{r['word_count']}</td><td>{html.escape(r['latest_version'])}</td></tr>"
        for r in report.get('blocks', [])[:500]
    )
    chain = ' → '.join(report.get('provider_chain', []))
    ollama = report.get('ollama', {})
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>Histora V36 Voiceover Dashboard</title>
<style>body{{font-family:Segoe UI,Arial;background:#111;color:#eee;margin:22px}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}} .card{{background:#1d1d1d;border:1px solid #333;border-radius:8px;padding:14px}} .num{{font-size:28px;font-weight:700}} .num span{{font-size:15px;color:#8bdcff}} pre{{color:#4cc2ff;font-size:18px}} .next{{background:#202a20;border:1px solid #375f37;padding:14px;border-radius:8px;margin:16px 0}} .warn{{background:#2a2414;border:1px solid #665c23;padding:14px;border-radius:8px;margin:16px 0}} table{{width:100%;border-collapse:collapse;margin-top:18px}} th,td{{border:1px solid #333;padding:7px;text-align:left}} th{{background:#222;color:#8bdcff}} tr.needs_generation td{{background:#201914}} tr.needs_review td{{background:#222015}} tr.approved td{{background:#142414}}</style>
</head><body><h1>Histora V36 Voiceover Dashboard</h1>
<div class=next><b>Provider chain:</b> {html.escape(chain)}<br><b>Next:</b> {html.escape(s.get('next_action',''))}</div>
<div class=warn><b>Qwen note:</b> {html.escape(s.get('qwen_note',''))}<br>Ollama: {'AVAILABLE' if ollama.get('available') else 'NOT AVAILABLE'} | Host: {html.escape(str(ollama.get('host','')))} | Model: {html.escape(str(ollama.get('model','')))}</div>
<div class=grid>
<div class=card><h3>Approved voices</h3><div class=num>{s['voices_approved']}/{s['blocks_total']} <span>{_pct(s['voices_approved'],s['blocks_total'])}%</span></div><pre>{_bar(s['voices_approved'],s['blocks_total'])}</pre></div>
<div class=card><h3>Waiting review</h3><div class=num>{s['generated_waiting_review']}/{s['blocks_total']} <span>{_pct(s['generated_waiting_review'],s['blocks_total'])}%</span></div><pre>{_bar(s['generated_waiting_review'],s['blocks_total'])}</pre></div>
<div class=card><h3>Missing generation</h3><div class=num>{s['missing_generation']}/{s['blocks_total']} <span>{_pct(s['missing_generation'],s['blocks_total'])}%</span></div><pre>{_bar(s['missing_generation'],s['blocks_total'])}</pre></div>
<div class=card><h3>Pending chars</h3><div class=num>{s['chars_pending']}</div><p>Characters still needing approved narration.</p></div>
</div>
<h2>Voice Blocks</h2><table><tr><th>Block</th><th>Scene</th><th>Character</th><th>Voice State</th><th>Status</th><th>Words</th><th>Latest Version</th></tr>{rows}</table>
</body></html>"""


def _review_html(report: dict[str, Any]) -> str:
    queue = [r for r in report.get('blocks', []) if r.get('status') != 'approved']
    rows = '\n'.join(
        f"<tr><td>{i}</td><td>{html.escape(r['block_id'])}</td><td>{html.escape(r['scene_title'])}</td><td>{html.escape(r['character'])}</td><td>{html.escape(r['status'])}</td><td>{html.escape(r['next_task'])}</td><td>{html.escape(r['latest_version'])}</td></tr>"
        for i, r in enumerate(queue[:500], 1)
    )
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>Histora V36 Voice Review Queue</title>
<style>body{{font-family:Segoe UI,Arial;background:#111;color:#eee;margin:22px}} table{{width:100%;border-collapse:collapse}} th,td{{border:1px solid #333;padding:7px;text-align:left}} th{{background:#222;color:#8bdcff}} .next{{background:#241d14;border:1px solid #654;padding:12px;margin:12px 0;border-radius:8px}}</style></head>
<body><h1>Histora V36 Voice Review Queue</h1><div class=next><b>Queue items:</b> {len(queue)} | Review generated voices, approve good ones, redo bad ones.</div>
<table><tr><th>#</th><th>Block</th><th>Scene</th><th>Character</th><th>Status</th><th>Next task</th><th>Latest version</th></tr>{rows}</table></body></html>"""
