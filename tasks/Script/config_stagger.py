# This file uses the following encoding: utf-8
# 错峰执行设置：同一分组内的配置轮流运行，且两次运行之间强制间隔。
from pydantic import BaseModel, Field


class Stagger(BaseModel):
    """跨配置错峰执行。

    多个配置（如 oas1 与 oas3）如果共用一个模拟器/一台电脑，同时跑会互相抢设备。
    开启后，同组配置通过共享状态文件串行执行：上一个实例结束后至少间隔
    gap_minutes 分钟，才允许同组的下一个实例开始。
    """

    enable: bool = Field(default=False, description='stagger_enable_help')
    group: str = Field(default='', description='stagger_group_help')
    gap_minutes: int = Field(default=15, ge=0, le=720, description='stagger_gap_minutes_help')
