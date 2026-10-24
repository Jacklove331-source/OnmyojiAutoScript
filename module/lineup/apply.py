# This file uses the following encoding: utf-8
"""把匹配到的阵容写入任务配置。

支持两种落点：
1. 预设队伍：task.conf.general_battle_config.preset_enable/group/team
2. QuickLoadout：task.conf 上带 *quick_loadout* 的配置项（如 MartialArts）
另外可选：SwitchSoul 按名称切换御魂（entry.soul_group/soul_team）
"""
from module.config.utils import convert_to_underscore
from module.lineup import data
from module.lineup.resolver import resolve
from module.logger import logger

APPLY_PRESET = 'preset'
APPLY_QUICK = 'quick_loadout'
APPLY_BOTH = 'both'


def _apply_preset(conf, entry, overwrite: bool) -> bool:
    gb = getattr(conf, 'general_battle_config', None)
    if gb is None:
        return False
    if getattr(gb, 'preset_enable', False) and not overwrite:
        logger.info('[AutoLineup] task already has preset enabled, keep it')
        return False
    if entry.preset_group is None or entry.preset_team is None:
        return False
    gb.preset_enable = True
    gb.preset_group = int(entry.preset_group)
    gb.preset_team = int(entry.preset_team)
    logger.info(
        f'[AutoLineup] preset -> group {gb.preset_group}, team {gb.preset_team} '
        f'({entry.name})')
    return True


def _find_quick_loadout(conf):
    if conf is None:
        return None
    direct = getattr(conf, 'quick_loadout_config', None)
    if direct is not None:
        return direct
    for name in dir(conf):
        if name.endswith('quick_loadout_config'):
            return getattr(conf, name)
    return None


def _apply_quick_loadout(conf, entry, overwrite: bool) -> bool:
    ql = _find_quick_loadout(conf)
    if ql is None:
        return False
    if getattr(ql, 'enable', False) and not overwrite:
        logger.info('[AutoLineup] task already has quick_loadout enabled, keep it')
        return False
    cfg = entry.quick_loadout or {}
    if not cfg and entry.preset_group is not None:
        cfg = {'group_number': int(entry.preset_group),
               'preset_number': int(entry.preset_team or 1)}
    if not cfg:
        return False
    for key in ('mode', 'group_number', 'preset_number', 'group_name', 'preset_name'):
        if key in cfg and hasattr(ql, key):
            setattr(ql, key, cfg[key])
    ql.enable = True
    logger.info(f'[AutoLineup] quick_loadout applied ({entry.name})')
    return True


def _apply_soul(conf, entry, overwrite: bool) -> bool:
    soul = getattr(conf, 'switch_soul_config', None)
    if soul is None or not entry.soul_group:
        return False
    if getattr(soul, 'enable_switch_by_name', False) and not overwrite:
        return False
    soul.enable_switch_by_name = True
    soul.group_name = entry.soul_group
    soul.team_name = entry.soul_team
    logger.info(f'[AutoLineup] switch soul by name: {entry.soul_group}/{entry.soul_team}')
    return True


def _load_entries_by_source(auto_lineup_cfg) -> tuple[dict, dict]:
    """按 source 设置加载阵容数据（local / web / ocr / auto）。

    合并优先级：内置参考库 < 联网缓存 < 本地文件（你自己的编辑优先）。
    """
    source = getattr(auto_lineup_cfg, 'source', 'local')
    source = getattr(source, 'value', source)
    data_file = getattr(auto_lineup_cfg, 'data_file', None)
    url = getattr(auto_lineup_cfg, 'web_url', '')
    cache_hours = int(getattr(auto_lineup_cfg, 'web_cache_hours', 24))

    if source == 'web':
        data.fetch_remote(url, data_file, cache_hours)
        return data.load_merged(data_file, use_remote=True)
    if source == 'ocr':
        # OCR 识别的结果由 OCR 工具写入本地表，这里直接读本地
        return data.load_merged(data_file)
    if source == 'auto':
        local_raw = data.load_raw(data_file)
        if not local_raw.get('lineups') and url:
            data.fetch_remote(url, data_file, cache_hours)
        return data.load_merged(data_file, use_remote=True)
    return data.load_merged(data_file)


def apply_for_task(config_model, task_name: str, enemy_name: str | None = None,
                   apply_mode: str = APPLY_PRESET, dry_run: bool = False) -> dict:
    """根据任务配置挑阵容并写入。返回执行结果字典（便于日志/测试）。"""
    conf = getattr(config_model, convert_to_underscore(task_name), None)
    if conf is None:
        return {'applied': False, 'reason': f'{task_name} has no config group'}

    auto_cfg = getattr(config_model.script, 'auto_lineup', None)
    strategy = getattr(getattr(auto_cfg, 'strategy', None), 'value', 'table')
    entry = None
    reason = ''

    if strategy == 'optimizer' and auto_cfg is not None:
        from module.lineup import roster as roster_mod
        from module.lineup import scoring
        roster = roster_mod.load_roster(getattr(auto_cfg, 'roster_file', None))
        if not roster:
            reason = 'roster empty, fallback to table'
            logger.warning('[AutoLineup] roster empty, fallback to table strategy')
        else:
            best = scoring.best_for_task(task_name, roster)
            if best is None:
                reason = 'optimizer found no template'
            elif best['score'] < int(getattr(auto_cfg, 'min_score', 55)):
                reason = (f"best `{best['template']['name']}` score {best['score']} "
                          f"< min_score {getattr(auto_cfg, 'min_score', 55)}")
                logger.warning(f'[AutoLineup] {reason}')
            else:
                tpl = best['template']
                entry = data.LineupEntry(
                    name=tpl.get('name', 'template'),
                    preset_group=tpl.get('preset_group'),
                    preset_team=tpl.get('preset_team'),
                    tags=list(tpl.get('tags') or []),
                    priority=int(best['score']),
                    note=tpl.get('soul_hint', ''),
                )
                reason = (f"optimizer:{tpl.get('name')} score={best['score']} "
                          f"fit={best['fit']} missing={len(best['missing'])}")
                logger.info(f'[AutoLineup] {reason}')
                if best['missing']:
                    for miss in best['missing']:
                        logger.warning(
                            f"[AutoLineup] missing {miss['role']}: "
                            f"candidates {miss['alternatives']}")

    if entry is None:
        entries, task_map = _load_entries_by_source(auto_cfg) if auto_cfg else data.load_entries()
        entry, table_reason = resolve(entries, task_map, task_name, enemy_name, match_mode='both')
        reason = reason + ' | ' + table_reason if reason else table_reason
        if entry is None:
            return {'applied': False, 'reason': reason}
        logger.info(f'[AutoLineup] matched by {table_reason}')
    result = {'applied': False, 'reason': reason, 'lineup': entry.name}
    if dry_run:
        result['preview'] = {
            'preset_group': entry.preset_group,
            'preset_team': entry.preset_team,
            'quick_loadout': entry.quick_loadout,
            'soul': [entry.soul_group, entry.soul_team],
        }
        return result

    overwrite = bool(getattr(config_model.script.auto_lineup, 'overwrite_manual', False))
    done = []
    if apply_mode in (APPLY_PRESET, APPLY_BOTH) and _apply_preset(conf, entry, overwrite):
        done.append('preset')
    if apply_mode in (APPLY_QUICK, APPLY_BOTH) and _apply_quick_loadout(conf, entry, overwrite):
        done.append('quick_loadout')
    if _apply_soul(conf, entry, overwrite):
        done.append('switch_soul')
    result['applied'] = bool(done)
    result['fields'] = done
    return result
