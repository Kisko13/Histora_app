
from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Any


@dataclass
class AnalysisContext:
    project_title: str = "Historical POV Project"
    historical_period: str = ""
    main_pov_character: str = ""
    voice_style: str = ""
    target_runtime_minutes: int = 75
    known_characters: list[str] = field(default_factory=list)
    known_locations: list[str] = field(default_factory=list)
    known_equipment: list[str] = field(default_factory=list)
    style_bible: str = ""


@dataclass
class CharacterProfile:
    id: str
    name: str
    role: str = ""
    baseline: str = ""
    appears_in_scenes: list[str] = field(default_factory=list)


@dataclass
class ProductionBlock:
    id: str
    scene_id: str
    text: str
    character: str
    duration_seconds: int
    voice: dict[str, Any]
    image_prompt: str
    music_cue: str
    locations: list[str] = field(default_factory=list)
    equipment: list[str] = field(default_factory=list)
    sfx: list[str] = field(default_factory=list)
    ambience: list[str] = field(default_factory=list)


@dataclass
class ProductionScene:
    id: str
    title: str
    summary: str
    blocks: list[ProductionBlock] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    equipment: list[str] = field(default_factory=list)


@dataclass
class ProductionPlan:
    title: str
    source: str
    context: AnalysisContext
    characters: list[CharacterProfile]
    scenes: list[ProductionScene]
    style_bible: dict[str, str]
    production_policy: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
