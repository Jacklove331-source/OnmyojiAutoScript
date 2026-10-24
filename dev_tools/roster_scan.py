# -*- coding: utf-8 -*-
"""账号数据扫描辅助工具：控制 MuMu 上的阴阳师，截图/点击/滑动，供后续 OCR 建花名册。

用法（仓库根目录）：
    .\\toolkit\\python.exe dev_tools\\roster_scan.py shot
    .\\toolkit\\python.exe dev_tools\\roster_scan.py launch
    .\\toolkit\\python.exe dev_tools\\roster_scan.py click 1128 405
    .\\toolkit\\python.exe dev_tools\\roster_scan.py swipe 640 600 640 200
    .\\toolkit\\python.exe dev_tools\\roster_scan.py wait 10

所有截图保存到 log/lineup_capture/。
"""
import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

CONFIG_NAME = 'oas1'
OUT_DIR = ROOT / 'log' / 'lineup_capture'
PACKAGE = 'com.netease.onmyoji.wyzymnqsd_cps'


def get_device():
    from module.config.config import Config
    from module.device.device import Device
    return Device(Config(CONFIG_NAME))


def save_shot(device, prefix='scan') -> Path:
    import cv2
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    image = device.screenshot()
    path = OUT_DIR / f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    cv2.imwrite(str(path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
    print(f'saved: {path}')
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('shot')
    sub.add_parser('launch')
    p_click = sub.add_parser('click')
    p_click.add_argument('x', type=int)
    p_click.add_argument('y', type=int)
    p_click.add_argument('--wait', type=float, default=1.0)
    p_swipe = sub.add_parser('swipe')
    p_swipe.add_argument('x1', type=int)
    p_swipe.add_argument('y1', type=int)
    p_swipe.add_argument('x2', type=int)
    p_swipe.add_argument('y2', type=int)
    p_swipe.add_argument('--duration', type=float, default=0.5)
    p_wait = sub.add_parser('wait')
    p_wait.add_argument('seconds', type=float)
    p_name = sub.add_parser('name')
    p_name.add_argument('x', type=int)
    p_name.add_argument('y', type=int)
    args = parser.parse_args()

    if args.cmd == 'wait':
        time.sleep(args.seconds)
        return

    device = get_device()
    if args.cmd == 'launch':
        device.app_start()
        print('app_start sent:', PACKAGE)
        time.sleep(2)
        save_shot(device, 'launch')
    elif args.cmd == 'shot':
        save_shot(device, 'scan')
    elif args.cmd == 'name':
        import cv2
        from module.atom.ocr import RuleOcr
        device.click(args.x, args.y)
        time.sleep(1.2)
        image = device.screenshot()
        x, y, w, h = 555, 95, 95, 355
        crop = image[y:y + h, x:x + w]
        for label, img in (('raw', crop), ('rot90', cv2.rotate(crop, cv2.ROTATE_90_CLOCKWISE))):
            ocr = RuleOcr(roi=(0, 0, img.shape[1], img.shape[0]), area=(0, 0, img.shape[1], img.shape[0]),
                          mode='Full', method='Default', keyword='', name=f'name_{label}')
            results = ocr.detect_and_ocr(img)
            texts = [r.ocr for r in results]
            print(f'{label}: {texts}')
        save_shot(device, 'name')
    elif args.cmd == 'click':
        device.click(args.x, args.y)
        time.sleep(args.wait)
        save_shot(device, 'click')
    elif args.cmd == 'swipe':
        device.swipe((args.x1, args.y1), (args.x2, args.y2), duration=args.duration)
        time.sleep(0.8)
        save_shot(device, 'swipe')


if __name__ == '__main__':
    main()
