# This file uses the following encoding: utf-8
"""自动阵容数据层。

数据文件（默认 config/auto_lineup.json）结构：

{
  "version": 1,
  "lineups": {
    "御魂-八岐大蛇": {
      "preset_group": 3,
      "preset_team": 1,
      "soul_group": "御魂A",
      "soul_team": "一队",
      "tags": ["御魂", "八岐大蛇"],
      "enemy": [],
      "priority": 10,
      "note": "13秒速刷"
    }
  },
  "task_map": {
    "Orochi": "御魂-八岐大蛇",
    "Dokan": {"lineup": "道馆-常规", "enemy": []}
  }
}
"""
import io
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from module.logger import logger

DEFAULT_DATA_FILE = 'config/auto_lineup.json'


@dataclass
class LineupEntry:
    name: str
    preset_group: int | None = None
    preset_team: int | None = None
    soul_group: str = ''
    soul_team: str = ''
    tags: list[str] = field(default_factory=list)
    enemy: list[str] = field(default_factory=list)
    priority: int = 0
    quick_loadout: dict[str, Any] = field(default_factory=dict)
    note: str = ''

    @classmethod
    def from_dict(cls, name: str, raw: dict) -> 'LineupEntry':
        return cls(
            name=name,
            preset_group=raw.get('preset_group'),
            preset_team=raw.get('preset_team'),
            soul_group=raw.get('soul_group', ''),
            soul_team=raw.get('soul_team', ''),
            tags=list(raw.get('tags') or []),
            enemy=list(raw.get('enemy') or []),
            priority=int(raw.get('priority', 0) or 0),
            quick_loadout=dict(raw.get('quick_loadout') or {}),
            note=raw.get('note', ''),
        )


def data_path(configured: str | None = None) -> Path:
    rel = (configured or DEFAULT_DATA_FILE).strip() or DEFAULT_DATA_FILE
    path = Path(rel)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def load_raw(configured: str | None = None) -> dict:
    path = data_path(configured)
    if not path.exists():
        logger.info(f'[AutoLineup] data file not found: {path}')
        return {'version': 1, 'lineups': {}, 'task_map': {}}
    try:
        with io.open(path, encoding='utf-8') as f:
            raw = json.load(f)
    except (OSError, ValueError) as e:
        logger.warning(f'[AutoLineup] failed to read {path}: {e}')
        return {'version': 1, 'lineups': {}, 'task_map': {}}
    raw.setdefault('lineups', {})
    raw.setdefault('task_map', {})
    return raw


def save_raw(raw: dict, configured: str | None = None) -> Path:
    path = data_path(configured)
    path.parent.mkdir(parents=True, exist_ok=True)
    with io.open(path, 'w', encoding='utf-8') as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
    return path


def load_entries(configured: str | None = None) -> tuple[dict[str, LineupEntry], dict]:
    raw = load_raw(configured)
    entries = {name: LineupEntry.from_dict(name, value)
               for name, value in raw.get('lineups', {}).items()}
    return entries, raw.get('task_map', {})


def fetch_remote(url: str, configured: str | None = None,
                 cache_hours: int = 24) -> dict | None:
    """从远端拉取 JSON 到本地数据文件（带缓存）。"""
    if not url:
        return None
    path = data_path(configured)
    if path.exists() and cache_hours > 0:
        age_hours = (time.time() - path.stat().st_mtime) / 3600
        if age_hours < cache_hours:
            logger.info(f'[AutoLineup] remote cache still fresh ({age_hours:.1f}h)')
            return load_raw(configured)
    try:
        import requests
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        raw = resp.json()
    except Exception as e:
        logger.warning(f'[AutoLineup] fetch {url} failed: {e}')
        return load_raw(configured)
    raw.setdefault('lineups', {})
    raw.setdefault('task_map', {})
    raw.setdefault('version', 1)
    save_raw(raw, configured)
    logger.info(f'[AutoLineup] fetched {len(raw["lineups"])} lineups from {url}')
    return raw


def ensure_default_file(configured: str | None = None) -> Path:
    """首次启用时生成一个带示例的数据文件。"""
    path = data_path(configured)
    if path.exists():
        return path
    template = {
        'version': 1,
        '_help': 'lineups 里定义阵容，task_map 把任务名映射到阵容；enemy 用于按敌方名称匹配',
        'lineups': {
            '示例-御魂': {
                'preset_group': 3,
                'preset_team': 1,
                'soul_group': '',
                'soul_team': '',
                'tags': ['御魂'],
                'enemy': [],
                'priority': 0,
                'note': '把这里的组/队改成你游戏里的预设队伍',
            },
        },
        'task_map': {
            'Orochi': '示例-御魂',
        },
    }
    save_raw(template, configured)
    return path
