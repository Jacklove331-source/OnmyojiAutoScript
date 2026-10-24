# This file uses the following encoding: utf-8
"""自动阵容匹配器。

匹配顺序由 LineupMatch 决定：
- task  ：按任务名（task_map）匹配
- enemy ：按敌方名称（lineups[*].enemy）匹配，priority 大的优先
- both ：先敌方，匹配不到再按任务
"""
from module.logger import logger
from module.lineup.data import LineupEntry


def _select_by_task(entries: dict[str, LineupEntry], task_map: dict, task_name: str):
    target = task_map.get(task_name) or task_map.get(task_name.lower())
    if target is None:
        return None, 'no task_map entry'
    if isinstance(target, str):
        entry = entries.get(target)
        return (entry, f'task_map:{task_name}->{target}') if entry else (None, 'task_map target missing')
    if isinstance(target, dict):
        name = target.get('lineup') or target.get('name')
        if name and name in entries:
            return entries[name], f'task_map:{task_name}->{name}'
        # 允许直接在 task_map 里写完整配置
        if any(k in target for k in ('preset_group', 'preset_team')):
            entry = LineupEntry.from_dict(f'{task_name}@inline', target)
            return entry, f'task_map:{task_name} (inline)'
    return None, 'task_map entry invalid'


def _select_by_enemy(entries: dict[str, LineupEntry], enemy_name: str):
    if not enemy_name:
        return None, 'no enemy name'
    candidates = []
    for entry in entries.values():
        for pattern in entry.enemy:
            if pattern and (pattern in enemy_name or enemy_name in pattern):
                candidates.append(entry)
                break
    if not candidates:
        return None, f'no lineup for enemy {enemy_name}'
    best = sorted(candidates, key=lambda e: (e.priority, e.name), reverse=True)[0]
    return best, f'enemy:{enemy_name}->{best.name}'


def resolve(entries: dict[str, LineupEntry], task_map: dict, task_name: str,
            enemy_name: str | None = None, match_mode: str = 'both'):
    """返回 (LineupEntry | None, 原因说明)。"""
    results = []
    if match_mode in ('enemy', 'both'):
        entry, reason = _select_by_enemy(entries, enemy_name or '')
        if entry:
            logger.info(f'[AutoLineup] matched by {reason}')
            return entry, reason
        results.append(reason)
    if match_mode in ('task', 'both'):
        entry, reason = _select_by_task(entries, task_map, task_name)
        if entry:
            logger.info(f'[AutoLineup] matched by {reason}')
            return entry, reason
        results.append(reason)
    return None, '; '.join(results) or 'no data'
