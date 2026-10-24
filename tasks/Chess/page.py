from tasks.Chess.assets import ChessAssets
from tasks.GameUi.page_check_assets import PageCheckAssets as GameUiAssets
from tasks.GameUi.page import any_of, page_entertainment, page_town
from tasks.GameUi.page_definition import Page
from tasks.GlobalGame.assets import GlobalGameAssets

page_chess = Page(GameUiAssets.I_CHECK_CHESS, category="global")
page_entertainment.connect(
    page_chess,
    GameUiAssets.I_ENTERTAINMENT_GOTO_CHESS,
    key="page_entertainment->page_chess",
    on_leave_failure=[ChessAssets.I_SKIP],
    on_enter_failure=[ChessAssets.I_SKIP],
)
page_chess.connect(
    page_entertainment,
    GlobalGameAssets.I_UI_BACK_YELLOW,
    key="page_chess->page_entertainment",
)

# 棋局内页面属于全局异常恢复节点。任意任务启动时若停留在遗留棋局，
# 导航器会先调用统一退出流程返回棋局大厅，再继续规划原目标页面。
page_chess_battle = Page(
    any_of(GameUiAssets.I_CHECK_CHESS_BATTLE, ChessAssets.I_SELECT_SIXREALMS),
    category="global",
    priority=95,
)
page_chess_battle.connect(
    page_chess,
    GlobalGameAssets.I_UI_BACK_YELLOW,
    key="page_chess_battle->page_chess",
)
# 棋局可能在脚本已判定进入超时后才落到名次结算页。将全部既有结算
# 标志注册为独立全局页面，使任何导航过程都能继续结算并返回大厅。
page_chess_result = Page(
    any_of(
        GameUiAssets.I_CHESS_EXIT_TO_LOBBY,
        GameUiAssets.I_CHESS_EXIT_TO_LOBBY_2,
        GlobalGameAssets.I_UI_REWARD,
        ChessAssets.I_SHARE,
        GameUiAssets.I_CHECK_CHESS_RANK,
        GameUiAssets.I_CHESS_RANK_GOTO_LOBBY,
    ),
    category="global",
    priority=96,
)
page_chess_result.connect(
    page_chess,
    GlobalGameAssets.I_UI_BACK_YELLOW,
    key="page_chess_result->page_chess",
)
page_entertainment.connect(
    page_town,
    GlobalGameAssets.I_UI_BACK_YELLOW,
    key="page_entertainment->page_town",
)

