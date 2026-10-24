# This file uses the following encoding: utf-8
"""阵容知识库版本管理。

知识库（式神元数据 / 阵容模板）都带 game_version 与 updated_at，
随仓库更新；也可以指向一个远端 JSON 做版本检查。
"""
import io
import json
from pathlib import Path

META_FILE = 'assets/lineup/meta_zh-CN.json'
TEMPLATES_FILE = 'assets/lineup/templates_zh-CN.json'


def _load(path: str) -> dict:
    p = Path.cwd() / path
    if not p.exists():
        return {}
    try:
        with io.open(p, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def version_info() -> dict:
    meta = _load(META_FILE)
    templates = _load(TEMPLATES_FILE)
    return {
        'game_version': meta.get('game_version') or templates.get('game_version'),
        'meta_updated_at': meta.get('updated_at'),
        'templates_updated_at': templates.get('updated_at'),
        'shikigami_count': len(meta.get('shikigami', {})),
        'soul_count': len(meta.get('souls', {})),
        'template_count': len(templates.get('templates', [])),
        'source': meta.get('source', ''),
    }


def check_remote(url: str) -> dict | None:
    """拉取远端版本信息并与本地比较。远端 JSON 至少包含 game_version/updated_at。"""
    if not url:
        return None
    try:
        import requests
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        remote = resp.json()
    except Exception as e:
        return {'error': str(e)}
    local = version_info()
    newer = (remote.get('updated_at') or '') > (local.get('meta_updated_at') or '')
    return {'local': local, 'remote': remote, 'has_update': newer}
