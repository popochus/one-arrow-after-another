"""生成 README / 博客所需的玩法演示 GIF。

用法（项目根目录）：
    python tools/make_gif.py

脚本用 SDL dummy 驱动离屏渲染，把「开始界面 → 选关 → 游戏（含一次碰撞）
→ 通关结算」录成一段动画，存到 docs/screenshots/demo.gif。

依赖 Pillow（仅生成 GIF 时需要，游戏本身不依赖）。
改动界面或动画参数后重新跑一次即可。

参数在下方常量里调整：
    FPS    每秒采样帧数，越小文件越小、动作越顿
    SCALE  输出缩放比例，越小文件越小
    COLORS 调色板颜色数，越小文件越小
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pygame                                     # noqa: E402
from PIL import Image                             # noqa: E402

from game import config as C                      # noqa: E402
from game import renderer                         # noqa: E402
from game.app import Game                         # noqa: E402
from game.solver import solve                     # noqa: E402

OUT_PATH = ROOT / "docs" / "screenshots" / "demo.gif"

FPS = 12          # 采样帧率
SCALE = 0.5       # 输出尺寸比例（720x1280 -> 360x640）
COLORS = 128      # 调色板颜色数

# 各阶段的停留时长（秒），按演示节奏手调
HOLD_MENU = 0.75
HOLD_SELECT = 0.75
HOLD_ENTER = 0.50
HOLD_COLLISION = 0.70
HOLD_FLY_OUT = 0.60
HOLD_RESULT = 1.60


class Recorder:
    """按固定帧率采样游戏画面，累积成 GIF 帧序列。"""

    def __init__(self, game, screen):
        self.game = game
        self.screen = screen
        self.dt = 1.0 / FPS
        self.size = (int(C.WINDOW_WIDTH * SCALE), int(C.WINDOW_HEIGHT * SCALE))
        self.frames = []

    def tick(self):
        """推进一帧时间，渲染并记录下来。"""
        self.game.update(self.dt)
        renderer.render(self.screen, self.game)
        raw = pygame.image.tostring(self.screen, "RGB")
        image = Image.frombytes("RGB", self.screen.get_size(), raw)
        self.frames.append(image.resize(self.size, Image.Resampling.LANCZOS))

    def hold(self, seconds):
        """保持当前画面若干秒。"""
        for _ in range(max(1, round(seconds * FPS))):
            self.tick()

    def save(self, path):
        """统一调色板后写成 GIF。

        所有帧共用同一张调色板（取中间一帧量化得到），
        比逐帧自适应调色板小很多，颜色也不会闪烁。
        """
        reference = self.frames[len(self.frames) // 2].quantize(colors=COLORS)
        frames = [f.quantize(palette=reference, dither=Image.Dither.NONE)
                  for f in self.frames]

        path.parent.mkdir(parents=True, exist_ok=True)
        frames[0].save(
            str(path),
            save_all=True,
            append_images=frames[1:],
            duration=int(1000 / FPS),
            loop=0,
            optimize=True,
        )


def record(game, screen):
    """录一段完整演示：开始 → 选关 → 游戏（含碰撞）→ 通关。"""
    rec = Recorder(game, screen)

    # 1. 开始界面
    rec.hold(HOLD_MENU)

    # 2. 点「开始游戏」进入选关界面
    game.on_click(renderer.menu_button_rect().center)
    rec.hold(HOLD_SELECT)

    # 3. 点第 1 关卡片，进入游戏
    game.on_click(renderer.select_card_rect(0).center)
    rec.hold(HOLD_ENTER)

    # 4. 故意点一个被阻挡的箭头，演示碰撞反馈
    #    第 1 关左上角 (0, 0) 朝右，右侧紧邻一个箭头，必定被阻挡
    game.on_click(renderer.cell_center(game.origin, 0, 0))
    rec.hold(HOLD_COLLISION)

    # 5. 按求解器给出的顺序，逐个点掉能飞的箭头
    for arrow in solve(game.board):
        game.on_click(renderer.cell_center(game.origin, arrow.row, arrow.col))
        rec.hold(HOLD_FLY_OUT)

    # 6. 通关结算界面
    rec.hold(HOLD_RESULT)

    return rec


def main():
    pygame.init()
    screen = pygame.display.set_mode((C.WINDOW_WIDTH, C.WINDOW_HEIGHT))

    game = Game(screen)
    rec = record(game, screen)
    rec.save(OUT_PATH)

    pygame.quit()

    size_kb = OUT_PATH.stat().st_size / 1024
    print(f"已生成 {OUT_PATH.relative_to(ROOT)}")
    print(f"  帧数 {len(rec.frames)}，尺寸 {rec.size[0]}x{rec.size[1]}，"
          f"{FPS} fps，约 {len(rec.frames) / FPS:.1f} 秒，{size_kb:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
