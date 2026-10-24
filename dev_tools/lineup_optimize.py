# -*- coding: utf-8 -*-
"""阵容求解器 CLI：按你的式神池给某个任务推荐阵容。

用法（仓库根目录）：
    .\\toolkit\\python.exe dev_tools\\lineup_optimize.py Orochi
    .\\toolkit\\python.exe dev_tools\\lineup_optimize.py Dokan --roster config/roster.json
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('task', help='任务名，如 Orochi / Sougenbi / EvoZone')
    parser.add_argument('--roster', default='config/roster.json')
    parser.add_argument('--top', type=int, default=5)
    args = parser.parse_args()

    from module.lineup import scoring
    from module.lineup.roster import ensure_default_roster, load_roster

    ensure_default_roster(args.roster)
    roster = load_roster(args.roster)
    print(f'式神池: {len(roster)} 个 -> {sorted(roster)[:10]}')
    ranked = scoring.rank_for_task(args.task, roster, limit=args.top)
    if not ranked:
        print(f'没有匹配 {args.task} 的阵容模板')
        return
    for i, r in enumerate(ranked, 1):
        tpl = r['template']
        print(f"\n[{i}] {tpl['name']}  总分={r['score']}  适配={r['fit']}  "
              f"强度={r['strength']}  预设={tpl.get('preset_group')}-{tpl.get('preset_team')}")
        if tpl.get('soul_hint'):
            print(f"    御魂: {tpl['soul_hint']}")
        for d in r['details']:
            if d['missing']:
                print(f"    ✗ {d['role']}: 缺，候选 {d['alternatives']}")
            else:
                print(f"    ✓ {d['role']}: {d['matched']} "
                      f"(等级x{d['level_factor']} 技能x{d['skill_factor']} 速度x{d['speed_factor']})")


if __name__ == '__main__':
    main()
