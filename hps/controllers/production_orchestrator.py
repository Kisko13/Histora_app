"""
V24 Production Orchestrator.
Free-first policy: orchestration, images, music, reports and assembly are local/free.
Only voice generation may call the configured voice provider, and existing cost_guard still blocks paid use unless allowed in .env.
"""
from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import Callable, Optional

from hps.core.block_state import compute_project_state, compute_block_state
from hps.core.cost_control import cost_guard
from hps.core.local_assets import create_image_placeholder, create_music_placeholder, write_recovery_snapshot, write_budget_forecast
from hps.core.production_director import ProductionDirector
from hps.core.assembly_engine import AssemblyEngine
from hps.pipeline.build import BuildPipeline


Progress = Optional[Callable[[int, int, str, str], None]]


class ProductionOrchestrator:
    def __init__(self, db, voice_provider: str = "mock", allow_voice_generation: bool = False, progress: Progress = None):
        self.db = db
        self.voice_provider = voice_provider
        self.allow_voice_generation = allow_voice_generation
        self.progress = progress
        self.log = []

    def _emit(self, i, total, block_id, message):
        self.log.append(message)
        if self.progress:
            self.progress(i, total, block_id, message)

    def rebuild_plan(self) -> list[dict]:
        self.db.clear_production_jobs()
        project = compute_project_state(self.db)
        jobs = []
        for s in project["states"]:
            bid = s["block_id"]
            if not s["story_ok"]:
                jid = self.db.add_production_job("story", bid, status="blocked", message="Script text is missing; manual writing required.")
                jobs.append(dict(id=jid, task_type="story", block_id=bid, status="blocked"))
                continue
            if not s["voice_ok"]:
                est = cost_guard(self.db, "all", self.voice_provider)["estimated_cost"] / max(1, project["total"])
                jid = self.db.add_production_job("voice", bid, status="pending", estimated_cost_usd=est, message="Voice controls timing. Paid provider allowed only for this task type.")
                jobs.append(dict(id=jid, task_type="voice", block_id=bid, status="pending"))
            if not s["image_ok"]:
                dep = f"voice:{bid}" if not s["voice_ok"] else ""
                status = "waiting" if dep else "pending"
                jid = self.db.add_production_job("image", bid, status=status, dependency_key=dep, message="Local placeholder/prompt pack. No paid image API.")
                jobs.append(dict(id=jid, task_type="image", block_id=bid, status=status))
            if not s["music_ok"]:
                dep = f"voice:{bid}" if not s["voice_ok"] else ""
                status = "waiting" if dep else "pending"
                jid = self.db.add_production_job("music", bid, status=status, dependency_key=dep, message="Local cue/silent bed. No paid music API.")
                jobs.append(dict(id=jid, task_type="music", block_id=bid, status=status))
        if project["total"] and project["assembly_ready"] == project["total"]:
            jid = self.db.add_production_job("assembly", "", status="pending", message="Build local timeline/package/FFmpeg script.")
            jobs.append(dict(id=jid, task_type="assembly", block_id="", status="pending"))
        write_recovery_snapshot(self.db, "v24_plan")
        write_budget_forecast(self.db, self.voice_provider)
        ProductionDirector(self.db).export_report()
        return jobs

    def _unlock_waiting_jobs(self):
        for job in self.db.production_jobs():
            if job["status"] != "waiting" or not job["dependency_key"]:
                continue
            key = job["dependency_key"]
            if key.startswith("voice:"):
                bid = key.split(":", 1)[1]
                if compute_block_state(self.db, bid)["voice_ok"]:
                    self.db.update_production_job(job["id"], status="pending", message="Dependency satisfied.")

    def run_pending(self, offline_assets: bool = True, build_assembly: bool = True) -> dict:
        # Always rebuild before run so recovery reflects current files.
        self.rebuild_plan()
        total = max(1, len(self.db.production_jobs()))
        i = 0
        changed = True
        while changed:
            changed = False
            self._unlock_waiting_jobs()
            for job in self.db.production_jobs():
                if job["status"] != "pending":
                    continue
                i += 1
                changed = True
                self._run_job(job, i, total, offline_assets=offline_assets, build_assembly=build_assembly)
                self._unlock_waiting_jobs()
        write_recovery_snapshot(self.db, "latest")
        return {"log": self.log, "jobs": [dict(j) for j in self.db.production_jobs()]}

    def _run_job(self, job, i, total, offline_assets: bool, build_assembly: bool):
        jid, typ, bid = job["id"], job["task_type"], job["block_id"]
        self.db.update_production_job(jid, status="running", attempt_count=job["attempt_count"] + 1)
        try:
            if typ == "voice":
                if not self.allow_voice_generation:
                    self.db.update_production_job(jid, status="waiting", message="Voice generation not run. Use Generate Voice or enable Run Voice in Orchestrator.")
                    self._emit(i, total, bid, f"WAIT voice {bid}: manual/paid voice step required")
                    return
                guard = cost_guard(self.db, "all", self.voice_provider)
                if self.voice_provider != "mock" and not guard["allowed"]:
                    self.db.update_production_job(jid, status="failed", message="Paid voice blocked by .env budget guard.")
                    self._emit(i, total, bid, f"BLOCKED paid voice {bid}: check .env budget guard")
                    return
                self._emit(i, total, bid, f"Generating voice for {bid}")
                pipe = BuildPipeline(self.db, provider_name=self.voice_provider)
                pipe.provider.synthesize(db=self.db, block_id=bid)
                rel = pipe.approve_latest(bid)
                self.db.update_production_job(jid, status="completed", result_path=rel, message="Voice generated and approved.")
            elif typ == "image":
                if not offline_assets:
                    self.db.update_production_job(jid, status="waiting", message="Offline image creation disabled.")
                    return
                path = create_image_placeholder(self.db, bid)
                rel = str(path.relative_to(self.db.root_dir)).replace("\\", "/")
                self.db.update_production_job(jid, status="completed", result_path=rel, message="Local approved placeholder + prompt created. No paid API.")
                self._emit(i, total, bid, f"Local image placeholder approved for {bid}")
            elif typ == "music":
                if not offline_assets:
                    self.db.update_production_job(jid, status="waiting", message="Offline music cue creation disabled.")
                    return
                path = create_music_placeholder(self.db, bid)
                rel = str(path.relative_to(self.db.root_dir)).replace("\\", "/")
                self.db.update_production_job(jid, status="completed", result_path=rel, message="Local silent bed + cue created. No paid API.")
                self._emit(i, total, bid, f"Local music cue approved for {bid}")
            elif typ == "assembly":
                if not build_assembly:
                    self.db.update_production_job(jid, status="waiting", message="Assembly build disabled.")
                    return
                result = AssemblyEngine(self.db).build_all()
                rel = str(result["summary"].relative_to(self.db.root_dir)).replace("\\", "/")
                self.db.update_production_job(jid, status="completed", result_path=rel, message="Assembly outputs created.")
                p = self.db.project()
                if p:
                    self.db.execute("UPDATE project SET assembly_status='approved' WHERE id=?", (p["id"],))
                self._emit(i, total, "assembly", "Assembly package rebuilt")
            elif typ == "story":
                self.db.update_production_job(jid, status="blocked", message="Manual script writing required.")
        except Exception as exc:
            msg = f"{exc}\n{traceback.format_exc()}"
            status = "retry" if job["attempt_count"] + 1 < job["max_attempts"] else "failed"
            self.db.update_production_job(jid, status=status, message=msg[:3000])
            self._emit(i, total, bid, f"FAILED {typ} {bid}: {exc}")
