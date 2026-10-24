# This file uses the following encoding: utf-8
"""式神录扫描：自动翻页、点卡片、OCR 名字，写入 roster.json。

坐标基于 1280x720（MuMu 默认分辨率），与 assets/lineup/ui_zh-CN.json 一致。
"""
import io
import json
import re
import time
from pathlib import Path

from module.logger import logger

# 庭院/式神录坐标（1280x720）
COURTYARD_SHRIN = (1108, 622)
BOTTOM_SHRIN = (1140, 665)
TABS = {'SP': (160, 148), 'SSR': (230, 148), 'SR': (300, 148), '全部': (60, 148)}
GRID_X = [115, 228, 340, 452]
GRID_Y = [225, 345, 465, 585, 700]
NAME_ROI = (555, 95, 95, 355)
SWIPE_UP = ((280, 660), (280, 250))

CJK = re.compile(r'[\u4e00-\u9fff]{2,}')


def _ocr_name(image, x, y, w, h):
    """竖排名字：尝试三种方向，取最长的中文片段。"""
    import cv2
    from module.atom.ocr import RuleOcr
    crop = image[y:y + h, x:x + w]
    candidates = []
    for img in (crop,
                cv2.rotate(crop, cv2.ROTATE_90_CLOCKWISE),
                cv2.rotate(crop, cv2.ROTATE_90_COUNTERCLOCKWISE)):
        ocr = RuleOcr(roi=(0, 0, img.shape[1], img.shape[0]),
                      area=(0, 0, img.shape[1], img.shape[0]),
                      mode='Full', method='Default', keyword='', name='roster_name')
        try:
            results = ocr.detect_and_ocr(img)
        except Exception as e:
            logger.debug(f'[RosterScan] ocr error: {e}')
            continue
        for r in results:
            text = (getattr(r, 'ocr', '') or '').strip()
            if text:
                candidates.append(text)
    if not candidates:
        return ''
    best = max(candidates, key=lambda t: len(CJK.findall(t)[0]) if CJK.findall(t) else 0)
    matched = CJK.findall(best)
    return matched[0] if matched else best


def _load_roster(path: Path) -> dict:
    if not path.exists():
        return {'shikigami': []}
    try:
        with io.open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {'shikigami': []}


def _save_roster(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with io.open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _click(device, x: int, y: int, wait: float = 0.4) -> None:
    """带清空点击记录的点击，避免 OAS 的“重复点击”保护误报。"""
    device.click(x, y, control_check=False)
    time.sleep(wait)
    try:
        device.click_record_clear()
    except Exception:
        pass


def _open_records(device) -> None:
    _click(device, *COURTYARD_SHRIN, wait=1.5)
    _click(device, *BOTTOM_SHRIN, wait=2.5)


def run_scan(device, cfg, progress=None) -> dict:
    """执行一次扫描。cfg 为 RosterScan 配置对象。"""
    rarities = [r.strip() for r in str(getattr(cfg, 'rarities', 'SP,SSR,SR')).split(',') if r.strip()]
    pages = int(getattr(cfg, 'pages_per_rarity', 2))
    out_path = Path(str(getattr(cfg, 'output_file', 'config/roster.json')))
    if not out_path.is_absolute():
        out_path = Path.cwd() / out_path
    capture_dir = Path(str(getattr(cfg, 'capture_dir', 'log/roster_scan')))
    if not capture_dir.is_absolute():
        capture_dir = Path.cwd() / capture_dir
    capture_dir.mkdir(parents=True, exist_ok=True)

    data = _load_roster(out_path)
    existing = {item.get('name'): item for item in data.get('shikigami', []) if item.get('name')}

    _open_records(device)
    found = {}
    for rarity in rarities:
        tab = TABS.get(rarity)
        if tab is None:
            logger.warning(f'[RosterScan] unknown rarity {rarity}, skip')
            continue
        _click(device, *tab, wait=1.0)
        for page in range(pages):
            for gy in GRID_Y:
                for gx in GRID_X:
                    _click(device, gx, gy, wait=0.45)
                    image = device.screenshot()
                    name = _ocr_name(image, *NAME_ROI)
                    if name and name not in found:
                        found[name] = rarity
                        if progress:
                            progress(f'{rarity} {name}')
                        logger.info(f'[RosterScan] {rarity} -> {name}')
            if page + 1 < pages:
                device.swipe(*SWIPE_UP, duration=0.4)
                time.sleep(1.0)

    # 合并：保留已有条目的等级/技能/御魂，扫描结果补名字
    merged = []
    for name, rarity in found.items():
        item = existing.get(name) or {
            'name': name,
            'level': 40,
            'skills': [5, 5, 5],
            'speed': None,
            'souls': [],
        }
        item['rarity'] = rarity
        merged.append(item)
    # 本次没扫到但原本存在的手动条目保留
    for name, item in existing.items():
        if name not in found:
            merged.append(item)

    data['shikigami'] = merged
    data['updated_at'] = time.strftime('%Y-%m-%d')
    _save_roster(out_path, data)
    logger.info(f'[RosterScan] saved {len(merged)} shikigami -> {out_path}')
    return {'count': len(merged), 'found': found, 'path': str(out_path)}
