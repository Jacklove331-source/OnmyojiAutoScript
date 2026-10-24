# 兼容层：把各任务自己的 page.py 聚合起来，供移植任务按原样 `import tasks.GameUi.task_pages as pages` 使用。
from tasks.GameUi.page import *  # noqa: F401,F403

from tasks.FrogChallenge.page import *  # noqa: F401,F403
from tasks.IbukiArena.page import *  # noqa: F401,F403
from tasks.GuguArtStudio.page import *  # noqa: F401,F403
from tasks.LBS.page import *  # noqa: F401,F403
from tasks.MartialArts.page import *  # noqa: F401,F403
from tasks.WeeklyPurchase.page import *  # noqa: F401,F403
