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


BUNDLED_FILE = 'assets/lineup/lineups_zh-CN.json'


def bundled_path() -> Path:
    return Path.cwd() / BUNDLED_FILE


def load_bundled() -> dict:
    """内置参考阵容库（随仓库分发，来自公开攻略整理）。"""
    path = bundled_path()
    if not path.exists():
        return {'version': 1, 'lineups': {}, 'task_map': {}}
    try:
        with io.open(path, encoding='utf-8') as f:
            raw = json.load(f)
    except (OSError, ValueError) as e:
        logger.warning(f'[AutoLineup] bundled file broken: {e}')
        return {'version': 1, 'lineups': {}, 'task_map': {}}
    raw.setdefault('lineups', {})
    raw.setdefault('task_map', {})
    return raw


def remote_path(configured: str | None = None) -> Path:
    path = data_path(configured)
    return path.with_name(path.stem + '_remote.json')


def load_remote(configured: str | None = None) -> dict:
    path = remote_path(configured)
    if not path.exists():
        return {'version': 1, 'lineups': {}, 'task_map': {}}
    try:
        with io.open(path, encoding='utf-8') as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return {'version': 1, 'lineups': {}, 'task_map': {}}
    raw.setdefault('lineups', {})
    raw.setdefault('task_map', {})
    return raw


def load_merged(configured: str | None = None, use_remote: bool = False):
    """合并优先级：内置库 < 联网缓存 < 本地文件（本地编辑优先）。"""
    layers = [load_bundled()]
    if use_remote:
        layers.append(load_remote(configured))
    layers.append(load_raw(configured))
    lineups, task_map = {}, {}
    for layer in layers:
        lineups.update(layer.get('lineups', {}))
        task_map.update(layer.get('task_map', {}))
    entries = {name: LineupEntry.from_dict(name, value)
               for name, value in lineups.items()}
    return entries, task_map


def fetch_remote(url: str, configured: str | None = None,
                 cache_hours: int = 24) -> dict | None:
    """从远端拉取 JSON 到「联网缓存」文件（不覆盖你自己的本地阵容表）。"""
    if not url:
        return None
    path = remote_path(configured)
    if path.exists() and cache_hours > 0:
        age_hours = (time.time() - path.stat().st_mtime) / 3600
        if age_hours < cache_hours:
            logger.info(f'[AutoLineup] remote cache still fresh ({age_hours:.1f}h)')
            return load_remote(configured)
    try:
        import requests
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        raw = resp.json()
    except Exception as e:
        logger.warning(f'[AutoLineup] fetch {url} failed: {e}')
        return load_remote(configured)
    raw.setdefault('lineups', {})
    raw.setdefault('task_map', {})
    raw.setdefault('version', 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    with io.open(path, 'w', encoding='utf-8') as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
    logger.info(f'[AutoLineup] fetched {len(raw["lineups"])} lineups from {url}')
    return raw


def ensure_default_file(configured: str | None = None) -> Path:
    """首次启用时生成一个空骨架；内置参考阵容在 assets/lineup/ 里，不覆盖。"""
    path = data_path(configured)
    if path.exists():
        return path
    template = {
        'version': 1,
        '_help': ('本文件只放你自己的覆盖项；不写就用 assets/lineup/lineups_zh-CN.json 的内置参考库。'
                  'lineups 定义阵容（preset_group/preset_team/soul_group/soul_team/enemy/priority/note），'
                  'task_map 把任务名映射到阵容名。'),
        'lineups': {},
        'task_map': {},
    }
    save_raw(template, configured)
    return path
