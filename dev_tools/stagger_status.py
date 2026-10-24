# -*- coding: utf-8 -*-
"""查看 OAS 跨实例「排队 / 错峰」状态的小工具。

用法（在仓库根目录）：
    .\\toolkit\\python.exe dev_tools\\stagger_status.py
"""
import io
import json
import os
from datetime import datetime
from pathlib import Path


def read_json(path: Path, default):
    try:
        with io.open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    state_file = root / 'log' / '.queue_state.json'
    state = read_json(state_file, {})

    print('=' * 56)
    print('OAS 排队 / 错峰状态')
    print('=' * 56)
    print(f'状态文件: {state_file}')
    if not state:
        print('（还没有状态文件：说明还没有实例以排队/错峰模式启动过）')
    else:
        print(f'当前持有者: {state.get("current")}')
        print(f'等待队列  : {state.get("queue")}')
        print(f'最后持有者: {state.get("last_holder")}')
        print(f'最后释放  : {state.get("last_release")}')
        resume_at = state.get('resume_at')
        if resume_at:
            try:
                remain = (datetime.fromisoformat(resume_at) - datetime.now()).total_seconds()
                print(f'错峰恢复  : {resume_at}（还剩 {max(0, int(remain))} 秒）')
            except ValueError:
                print(f'错峰恢复  : {resume_at}')
        else:
            print('错峰恢复  : 无')

    print('-' * 56)
    print('配置里的错峰设置：')
    config_dir = root / 'config'
    found = False
    for path in sorted(config_dir.glob('*.json')):
        data = read_json(path, {})
        stagger = (data.get('script') or {}).get('optimization', {}).get('stagger') or {}
        if not stagger.get('enable'):
            continue
        found = True
        print(f'  {path.stem:10} 分组={stagger.get("group", ""):12} '
              f'最小间隔={stagger.get("gap_minutes", 0)} 分钟')
    if not found:
        print('  （没有配置启用错峰）')


if __name__ == '__main__':
    main()
