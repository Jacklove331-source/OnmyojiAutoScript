# -*- coding: utf-8 -*-
"""阵容知识库版本信息 / 更新检查。

用法：
    .\\toolkit\\python.exe dev_tools\\lineup_update.py
    .\\toolkit\\python.exe dev_tools\\lineup_update.py --url <远端json地址>
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='', help='远端版本信息的 JSON 地址')
    args = parser.parse_args()

    from module.lineup import meta

    info = meta.version_info()
    print('本地知识库：')
    for k, v in info.items():
        print(f'  {k:22} {v}')

    if args.url:
        result = meta.check_remote(args.url)
        print('\n远端检查：')
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
