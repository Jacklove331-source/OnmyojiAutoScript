# This file uses the following encoding: utf-8
"""阵容强度与适配度评分。

评分 = 0.6 * 适配度 + 0.4 * 模板强度
适配度按模板每个位置逐个算：
- 有候选式神：weight * 等级系数 * 技能系数 * 速度系数
- 缺位置：扣 weight * 0.5，并给出可替代的同类式神建议
"""
import io
import json
from pathlib import Path

from module.logger import logger
from module.lineup.roster import Shikigami, alias_map, find_shikigami, load_meta

TEMPLATES_FILE = 'assets/lineup/templates_zh-CN.json'

TASK_TAGS = {
    'Orochi': ['御魂'], 'OrochiMoans': ['御魂'], 'SixRealms': ['御魂'],
    'OtherWorldTwilight': ['御魂'], 'Sougenbi': ['御魂', '业原火'],
    'FallenSun': ['御魂', '日轮'], 'EternitySea': ['御魂', '永生之海'],
    'EvoZone': ['觉醒'], 'Exploration': ['探索'], 'AreaBoss': ['活动'],
    'Nian': ['活动'], 'Tako': ['活动'], 'Dokan': ['道馆'],
    'RealmRaid': ['结界'], 'RyouToppa': ['结界'], 'KekkaiUtilize': ['结界'],
    'DemonicEncounter': ['逢魔'], 'DemonEncounter': ['逢魔'], 'TrueOrochi': ['真蛇'],
}


def load_templates() -> list[dict]:
    path = Path.cwd() / TEMPLATES_FILE
    if not path.exists():
        return []
    try:
        with io.open(path, encoding='utf-8') as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return []
    return raw.get('templates', []) or []


def _score_slot(slot: dict, roster: dict[str, Shikigami],
                aliases: dict[str, str], meta: dict) -> dict:
    weight = float(slot.get('weight', 1))
    found = None
    matched = None
    for candidate in slot.get('candidates', []):
        shiki = find_shikigami(roster, candidate, aliases)
        if shiki is not None:
            found, matched = shiki, candidate
            break
    if found is None:
        alternatives = [name for name in slot.get('candidates', [])]
        return {
            'role': slot.get('role', ''),
            'matched': None,
            'score': -weight * 0.5,
            'weight': weight,
            'missing': True,
            'alternatives': alternatives,
        }

    level_factor = 1.0
    min_level = slot.get('min_level')
    if min_level and found.level < min_level:
        level_factor = max(0.3, found.level / float(min_level))

    skill_factor = 1.0
    min_skill = slot.get('min_skill')
    if min_skill and found.skill_total < int(min_skill):
        skill_factor = max(0.5, found.skill_total / float(min_skill))

    speed_factor = 1.0
    min_speed = slot.get('min_speed')
    if min_speed and found.speed is not None and found.speed < min_speed:
        speed_factor = 0.6

    score = weight * level_factor * skill_factor * speed_factor
    return {
        'role': slot.get('role', ''),
        'matched': matched,
        'score': score,
        'weight': weight,
        'missing': False,
        'level_factor': round(level_factor, 2),
        'skill_factor': round(skill_factor, 2),
        'speed_factor': round(speed_factor, 2),
    }


def score_template(template: dict, roster: dict[str, Shikigami],
                   meta: dict | None = None) -> dict:
    meta = meta or load_meta()
    aliases = alias_map(meta)
    details = [_score_slot(slot, roster, aliases, meta) for slot in template.get('slots', [])]
    total_weight = sum(d['weight'] for d in details) or 1.0
    raw_fit = sum(d['score'] for d in details) / total_weight
    fit = max(0.0, min(1.0, raw_fit))
    strength = float(template.get('strength', 50))
    final = 0.6 * fit * 100 + 0.4 * strength
    missing = [d for d in details if d['missing']]
    return {
        'template': template,
        'fit': round(fit, 3),
        'strength': strength,
        'score': round(final, 1),
        'details': details,
        'missing': missing,
    }


def rank_for_task(task_name: str, roster: dict[str, Shikigami],
                  limit: int = 5) -> list[dict]:
    tags = set(TASK_TAGS.get(task_name, []))
    templates = load_templates()
    candidates = []
    for tpl in templates:
        tpl_tags = set(tpl.get('tags', []))
        tag_hit = len(tags & tpl_tags)
        if tags and not tag_hit:
            continue
        result = score_template(tpl, roster)
        result['tag_hit'] = tag_hit
        candidates.append(result)
    candidates.sort(key=lambda r: (r['tag_hit'], r['score']), reverse=True)
    return candidates[:limit]


def best_for_task(task_name: str, roster: dict[str, Shikigami]) -> dict | None:
    ranked = rank_for_task(task_name, roster, limit=1)
    if not ranked:
        logger.warning(f'[AutoLineup] no template for task {task_name}')
        return None
    best = ranked[0]
    logger.info(
        f"[AutoLineup] optimizer picks `{best['template']['name']}` "
        f"score={best['score']} fit={best['fit']} missing={len(best['missing'])}")
    return best
