# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from pydantic import BaseModel, ValidationError, validator, Field

from module.logger import logger
from tasks.Component.config_base import Time

class WhenTaskQueueEmpty(str, Enum):
    GOTO_MAIN = 'goto_main'
    CLOSE_GAME = 'close_game'

class ScheduleRule(str, Enum):
    FILTER = 'Filter'  # 默认的基于过滤器，（按照开发者设定的调度规则进行调度）
    FIFO = 'FIFO'  # 先来后到，（按照任务的先后顺序进行调度）
    PRIORITY = 'Priority'  # 基于优先级，同一个优先级的任务按照先来后到的顺序进行调度，优先级高的任务先调度

class Optimization(BaseModel):
    screenshot_interval: float = Field(default=0.3,
                                       description='screenshot_interval_help')
    combat_screenshot_interval: float = Field(default=1.0,
                                              description='combat_screenshot_interval_help')
    task_hoarding_duration: float = Field(default=0,
                                          description='task_hoarding_duration_help')
    when_task_queue_empty: WhenTaskQueueEmpty = Field(default=WhenTaskQueueEmpty.GOTO_MAIN,
                                                      description='when_task_queue_empty_help')
    close_game_wait_duration: Time = Field(default=Time(minute=0),
                                          description='close_game_wait_duration_help')
    close_emulator_wait_duration: Time = Field(default=Time(minute=0),
                                              description='close_emulator_wait_duration_help')
    emulator_startup_lead_time: Time = Field(default=Time(minute=2),
                                            description='emulator_startup_lead_time_help')
    schedule_rule: ScheduleRule = Field(default=ScheduleRule.FILTER, description='schedule_rule_help')
    # 排队模式：多个实例排队依次执行任务，避免同时执行造成服务器压力
    queue_mode: bool = Field(default=False, description='queue_mode_help')
    # 释放执行权的空闲阈值（分钟），仅 queue_mode=True 时生效
    queue_idle_threshold: int = Field(default=10, description='queue_idle_threshold_help')
    # 错峰执行：同组配置任务级互斥，跑完一个任务立刻交接（oas1/oas3 不会同时执行任务）
    stagger_enable: bool = Field(default=False, description='stagger_enable_help')
    # 错峰分组：逗号分隔的配置名列表，例如 oas1,oas3
    stagger_group: str = Field(default='', description='stagger_group_help')
    # 最小间隔（分钟）：0 表示跑完立刻让给同组另一个实例
    stagger_gap_minutes: int = Field(default=0, ge=0, le=720, description='stagger_gap_minutes_help')

