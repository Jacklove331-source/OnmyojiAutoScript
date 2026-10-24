# This file uses the following encoding: utf-8
"""脚本全局的自动阵容设置。

放在 Script 下作为独立分组（与 optimization / error 同级），
字段保持平铺，避免 OAS 配置界面生成器（只支持一层分组）报错。
"""
from enum import Enum

from pydantic import BaseModel, Field


class LineupSource(str, Enum):
    LOCAL = 'local'   # 只读本地 config/auto_lineup.json
    WEB = 'web'       # 从 web_url 拉取 JSON（带缓存）
    OCR = 'ocr'       # 从游戏「阵容助手」识别后写入本地表
    AUTO = 'auto'     # 本地 → 联网 → OCR 依次尝试


class LineupMatch(str, Enum):
    TASK = 'task'     # 按任务/关卡名称匹配
    ENEMY = 'enemy'   # 按敌方名称（馆主/鬼王等）匹配
    BOTH = 'both'     # 先敌方，匹配不到再按任务


class LineupApply(str, Enum):
    PRESET = 'preset'              # 写游戏预设队伍（1-7 组 × 1-5 队）
    QUICK_LOADOUT = 'quick_loadout'  # 写任务里的 QuickLoadout 一键配置
    BOTH = 'both'


class LineupStrategy(str, Enum):
    TABLE = 'table'          # 按阵容表/任务映射直接选
    OPTIMIZER = 'optimizer'  # 按你的式神池、技能、速度、御魂打分择优


class AutoLineup(BaseModel):
    """自动阵容：战斗任务开始前自动挑选并套用最合适的阵容。"""

    enable: bool = Field(default=False, description='auto_lineup_enable_help')
    source: LineupSource = Field(default=LineupSource.LOCAL, description='auto_lineup_source_help')
    strategy: LineupStrategy = Field(default=LineupStrategy.TABLE, description='auto_lineup_strategy_help')
    match_mode: LineupMatch = Field(default=LineupMatch.BOTH, description='auto_lineup_match_help')
    apply_mode: LineupApply = Field(default=LineupApply.PRESET, description='auto_lineup_apply_help')
    roster_file: str = Field(default='config/roster.json', description='auto_lineup_roster_file_help')
    min_score: int = Field(default=55, ge=0, le=100, description='auto_lineup_min_score_help')
    data_file: str = Field(default='config/auto_lineup.json', description='auto_lineup_data_file_help')
    web_url: str = Field(default='', description='auto_lineup_web_url_help')
    web_cache_hours: int = Field(default=24, ge=0, le=24 * 30, description='auto_lineup_web_cache_help')
    default_preset_group: int = Field(default=1, ge=1, le=7, description='auto_lineup_default_group_help')
    default_preset_team: int = Field(default=1, ge=1, le=5, description='auto_lineup_default_team_help')
    overwrite_manual: bool = Field(default=False, description='auto_lineup_overwrite_help')
