# -*- coding: utf-8 -*-
"""阵容助手截图工具：连接当前配置的模拟器，截一张游戏画面存到 log/lineup_capture/。

用途：把「阵容助手」界面截图发给开发者，用于确定 OCR 区域。

用法（仓库根目录）：
    .\\toolkit\\python.exe dev_tools\\lineup_capture.py oas1
    .\\toolkit\\python.exe dev_tools\\lineup_capture.py oas1 --name lineup_panel
"""
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('config', nargs='?', default='oas1', help='配置名，如 oas1')
    parser.add_argument('--name', default='lineup', help='文件名前缀')
    args = parser.parse_args()

    import cv2
    from module.config.config import Config
    from module.device.device import Device

    config = Config(args.config)
    device = Device(config)
    image = device.screenshot()

    out_dir = ROOT / 'log' / 'lineup_capture'
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = out_dir / f'{args.name}_{ts}.png'
    cv2.imwrite(str(path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
    print(f'saved: {path}')
    print(f'size : {image.shape[1]}x{image.shape[0]}')


if __name__ == '__main__':
    main()
