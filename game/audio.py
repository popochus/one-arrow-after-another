"""音效：全部用代码合成波形，不依赖任何外部音频文件。

README 里声明了项目「不使用第三方素材」，所以四个反馈音都由正弦波现场合成：

    fly    飞出成功   短促上扬的滑音
    hit    碰撞失误   低频下坠
    undo   撤销       两声短促的同音
    win    通关       三音上行的琶音

三点设计取舍：

1. **不引入 numpy**。pygame 生成波形通常走 `pygame.sndarray`，但它依赖 numpy，
   而项目只装了 pygame + pillow。这里改用 `mixer.Sound(buffer=...)`，
   把原始 PCM 字节直接喂给 pygame，零新依赖。

2. **没有声卡就静默降级**。`pygame.mixer.init()` 在无音频设备的机器上会抛异常，
   所以初始化被包在 try 里：失败即进入「关闭」状态，之后所有播放都是空操作。
   否则在没有声卡的环境里游戏会直接起不来。

3. **惰性初始化**。import 本模块不会做任何事，必须显式调用 `init()`——
   这样自动化测试、截图脚本与录制脚本都不会被动地打开音频设备。

4. **音量与音高都取保守值**。初版峰值 0.42、fly 收在 1180 Hz，试玩反馈"有点刺耳"；
   现在峰值降到 0.24、频段整体下移一档，起音另加了淡入。三个改动叠加，
   目标是"听得清但不扎耳朵"。所有听感相关参数都集中在本文件顶部，便于继续微调。
"""

import array
import math

import pygame

# 采样率。音效都只有零点几秒，22.05 kHz 足够，合成和播放的负担都更小。
_SAMPLE_RATE = 22050

# 音量峰值（0~1）。原为 0.42，试玩反馈"刺耳"，降到 0.24（约 -5 dB）。
# 这一项对听感的影响最直接：短促的高频音在小音量下依然清晰，
# 但响度一大就会显得尖锐。
_AMPLITUDE = 0.24

# 起音段占整段时长的比例。这一段做线性淡入，让声音"缓一下再出声"。
# 原来的包络是两端对称的正弦，0.1 秒的音在约 25 毫秒处就冲到七成响度，
# 起音太陡，听感上就是"啾"的一下尖响。
_ATTACK = 0.14

# 各音效的频率轨迹：[(起始频率 Hz, 结束频率 Hz, 时长 秒), ...]
# 起点与终点相同即为固定音高；多段依次拼接，用来构琶音。
#
# 频率整体比初版下调了一档：初版 fly 收在 1180 Hz、win 冲到 784 Hz，
# 都落在人耳最敏感频段的边缘，短促响起时很像电子啸叫，是"刺耳"的主因。
_RECIPES = {
    # 飞出：短促上扬，听感上像"嗖"地一下飞走
    "fly":  [(480, 780, 0.12)],
    # 碰撞：低频下坠，像撞了一下
    "hit":  [(300, 130, 0.18)],
    # 撤销：两声短促同音，像"退回一步"
    "undo": [(520, 520, 0.05), (410, 410, 0.08)],
    # 通关：三音上行琶音（G4-C5-E5，C 大调内的和弦音）
    "win":  [(392, 392, 0.11), (523, 523, 0.11), (659, 659, 0.22)],
}

_enabled = False        # 音频是否可用（设备缺失时为 False）
_sounds = {}            # 音效名 -> pygame.mixer.Sound
_voices = {}            # 音效名 -> 专属声道，避免同名音效叠加
_rate = _SAMPLE_RATE    # 实际协商到的采样率
_channels = 2           # 实际协商到的声道数


def _envelope(progress):
    """单段声音的音量包络，输入输出都是 0~1。

    快起缓落：前 _ATTACK 段线性淡入，之后按二次曲线衰减到 0。
    两端都取到 0，所以起止不会有爆音；衰减末端斜率也是 0，
    收尾平滑，不会"咔"地截断。相比原来两端对称的正弦包络，
    主要好处是起音不那么陡。
    """
    if progress < _ATTACK:
        return progress / _ATTACK
    tail = (progress - _ATTACK) / (1 - _ATTACK)
    return (1 - tail) ** 2


def _synth(points):
    """按频率轨迹合成一段声音，返回可直接播放的 Sound。

    逐采样累加相位，而不是直接算 sin(2πft)：频率随时间变化时，
    后者会在每个采样点用新频率重算相位，产生跳变，听感上是"咔"的杂音。
    累加相位则天然连续。

    每一段都套上 _envelope 的包络：
    起止处不会爆音，多段拼接时也能听出音与音之间的分离。
    """
    samples = array.array("h")          # 16 位有符号，与 mixer 的 size=-16 对应
    phase = 0.0

    for start_freq, end_freq, duration in points:
        count = int(_rate * duration)
        for index in range(count):
            progress = index / (count - 1) if count > 1 else 0.0
            freq = start_freq + (end_freq - start_freq) * progress
            phase += 2 * math.pi * freq / _rate

            value = math.sin(phase) * _envelope(progress) * _AMPLITUDE
            samples.append(int(max(-1.0, min(1.0, value)) * 32767))

    # 立体声需要把单声道采样交错复制一份；单声道则原样使用
    if _channels >= 2:
        stereo = array.array("h")
        for value in samples:
            stereo.append(value)
            stereo.append(value)
        samples = stereo

    return pygame.mixer.Sound(buffer=samples.tobytes())


def init():
    """打开音频设备并合成全部音效，返回音频是否可用。

    没有可用设备（或设备不支持 16 位格式）时返回 False 并保持关闭状态，
    不抛异常——调用方不需要为这件事做任何判断。
    """
    global _enabled, _rate, _channels

    if _enabled:
        return True

    try:
        pygame.mixer.init(frequency=_SAMPLE_RATE, size=-16, channels=2, buffer=512)
    except pygame.error:
        _enabled = False
        return False

    configured = pygame.mixer.get_init()
    if not configured:
        _enabled = False
        return False

    # 以实际协商到的参数为准：设备不一定接受请求的采样率与声道数
    _rate, size, _channels = configured
    if size != -16:
        # 非 16 位有符号格式无法用当前方式合成，宁可不出声也不要出杂音
        _enabled = False
        return False

    try:
        _sounds.update({name: _synth(points) for name, points in _RECIPES.items()})
    except (pygame.error, ValueError):
        _sounds.clear()
        _voices.clear()
        _enabled = False
        return False

    _enabled = True
    return True


def shutdown():
    """关闭音频，回到「不可用」状态。

    供自动化测试模拟"这台机器没有声卡"，也可在退出前显式释放设备。
    """
    global _enabled
    _enabled = False
    _sounds.clear()
    _voices.clear()
    try:
        pygame.mixer.quit()
    except pygame.error:
        pass


def enabled():
    """音频当前是否可用。"""
    return _enabled


def loaded():
    """已成功合成的音效名（按字母序）。供测试与排查使用。"""
    return tuple(sorted(_sounds))


def play(name):
    """播放指定音效，返回是否真的播了出去。

    音频不可用或音效名不存在时什么都不做——调用点因此不必写 if 判断。
    """
    if not _enabled:
        return False
    sound = _sounds.get(name)
    if sound is None:
        return False

    # 每个音效独占一个声道。默认的 sound.play() 会挑一个空闲声道，
    # 于是连点时同一个音会好几份叠着播，响度成倍上去——这也是
    # "点得快就更刺耳"的来源之一。走专属声道则新音直接打断旧的。
    if name not in _voices:
        try:
            _voices[name] = pygame.mixer.Channel(len(_voices))
        except pygame.error:
            _voices[name] = None        # 声道不够，退回默认行为

    channel = _voices[name]
    if channel is None:
        sound.play()
    else:
        channel.play(sound)
    return True
