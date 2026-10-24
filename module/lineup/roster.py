# This file uses the following encoding: utf-8
"""玩家式神/御魂池（roster）数据。

config/roster.json 结构：
{
  "shikigami": [
    {"name": "须佐之男", "level": 40, "skills": [5,5,5], "speed": 180,
     "souls": ["破势4", "狂骨2"]},
    {"name": "因幡辉夜姬", "level": 40, "skills": [5,5,5], "speed": 165, "souls": ["招财猫4"]}
  ],
  "updated_at": "2026-10-24"
}

skills 可写成 555 或 [5,5,5]；speed 是面板速度（可省略，省略时速度要求按通过处理）。
"""
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

from module.logger import logger

DEFAULT_ROSTER_FILE = 'config/roster.json'
META_FILE = 'assets/lineup/meta_zh-CN.json'


@dataclass
class Shikigami:
    name: str
    level: int = 40
    skills: tuple = (5, 5, 5)
    speed: int | None = None
    souls: list[str] = field(default_factory=list)

    @property
    def skill_total(self) -> int:
        return sum(self.skills) if self.skills else 0

    @property
    def skill_text(self) -> str:
        return ''.join(str(s) for s in self.skills)

    @classmethod
    def from_dict(cls, raw: dict) -> 'Shikigami':
        skills = raw.get('skills', 555)
        if isinstance(skills, int):
            skills = tuple(int(c) for c in str(skills).ljust(3, '0')[:3])
        elif isinstance(skills, str):
            skills = tuple(int(c) for c in skills.ljust(3, '0')[:3])
        else:
            skills = tuple(int(x) for x in skills)
        return cls(
            name=str(raw.get('name', '')).strip(),
            level=int(raw.get('level', 40) or 40),
            skills=skills,
            speed=raw.get('speed'),
            souls=list(raw.get('souls') or []),
        )


def roster_path(configured: str | None = None) -> Path:
    rel = (configured or DEFAULT_ROSTER_FILE).strip() or DEFAULT_ROSTER_FILE
    path = Path(rel)
    return path if path.is_absolute() else Path.cwd() / path


def load_meta() -> dict:
    path = Path.cwd() / META_FILE
    if not path.exists():
        return {'shikigami': {}, 'souls': {}}
    try:
        with io.open(path, encoding='utf-8') as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return {'shikigami': {}, 'souls': {}}
    raw.setdefault('shikigami', {})
    raw.setdefault('souls', {})
    return raw


def alias_map(meta: dict | None = None) -> dict[str, str]:
    """别名 -> 正式名。"""
    meta = meta or load_meta()
    result = {}
    for name, info in meta.get('shikigami', {}).items():
        result[name] = name
        for alias in info.get('aliases') or []:
            result[alias] = name
    return result


def load_roster(configured: str | None = None) -> dict[str, Shikigami]:
    path = roster_path(configured)
    if not path.exists():
        logger.info(f'[AutoLineup] roster not found: {path}')
        return {}
    try:
        with io.open(path, encoding='utf-8') as f:
            raw = json.load(f)
    except (OSError, ValueError) as e:
        logger.warning(f'[AutoLineup] roster broken: {e}')
        return {}
    result = {}
    for item in raw.get('shikigami', []) or []:
        shiki = Shikigami.from_dict(item)
        if shiki.name:
            result[shiki.name] = shiki
    return result


def find_shikigami(roster: dict[str, Shikigami], candidate: str,
                   aliases: dict[str, str] | None = None) -> Shikigami | None:
    """按正式名或别名在 roster 里找人。"""
    if candidate in roster:
        return roster[candidate]
    aliases = aliases or alias_map()
    canonical = aliases.get(candidate, candidate)
    if canonical in roster:
        return roster[canonical]
    for alias, target in aliases.items():
        if target == canonical and alias in roster:
            return roster[alias]
    return None


def ensure_default_roster(configured: str | None = None) -> Path:
    path = roster_path(configured)
    if path.exists():
        return path
    template = {
        '_help': ('把你拥有的式神填进来：level 等级、skills 技能等级、speed 面板速度（可省）、'
                  'souls 御魂套装。自动阵容的「强度适配」会按这个文件打分。'),
        'shikigami': [
            {'name': '须佐之男', 'level': 40, 'skills': [5, 5, 5], 'speed': 180, 'souls': ['破势4', '狂骨2']},
            {'name': '因幡辉夜姬', 'level': 40, 'skills': [5, 5, 5], 'speed': 165, 'souls': ['招财猫4']},
        ],
        'updated_at': '',
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with io.open(path, 'w', encoding='utf-8') as f:
        json.dump(template, f, ensure_ascii=False, indent=2)
    return path
