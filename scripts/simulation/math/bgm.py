"""
给动画配一段无版权问题的背景音乐。

Ludovico Einaudi 的《Experience》是受版权保护的商业录音，不能直接拿来用。
这里改用**程序合成**的慢速极简钢琴氛围曲：D 小调、约 50 BPM、
Dm - B♭ - F - C 循环、八分音符琶音 + 低音踏板 + 长混响，听感接近同类风格，
而且是原创波形，没有授权问题。

单独跑：
    python bgm.py [秒数]
产出同目录下的 bgm.wav（44.1 kHz / 16-bit 立体声）。

如果你自己有合法音源（比如买了正版《Experience》），直接把它命名成
bgm.wav / bgm.mp3 / bgm.m4a 放在本目录，主脚本会优先用它，不再合成。
"""

import sys
from pathlib import Path

import numpy as np

SR = 44100
BPM = 50.0
BEAT = 60.0 / BPM          # 一拍 1.2 秒
BAR = BEAT * 4             # 一小节 4.8 秒

# ---- 和弦进行：D 小调 i - VI - III - VII，非常 cinematic 的一圈 ----
# 每项 = (低音踏板 MIDI, 琶音音级 MIDI 列表)
PROGRESSION = [
    (38, [62, 65, 69, 74, 69, 65]),   # Dm  : D4 F4 A4 D5 A4 F4
    (34, [58, 62, 65, 70, 65, 62]),   # B♭  : B♭3 D4 F4 B♭4 F4 D4
    (41, [57, 60, 65, 69, 65, 60]),   # F   : A3 C4 F4 A4 F4 C4
    (36, [60, 64, 67, 72, 67, 64]),   # C   : C4 E4 G4 C5 G4 E4
]


def midi_to_hz(m):
    return 440.0 * (2.0 ** ((m - 69) / 12.0))


def piano_note(freq, dur, amp):
    """合成一个钢琴音：谐波叠加 + 轻微非谐性 + 快起音长衰减包络。"""
    n = int(dur * SR)
    t = np.arange(n) / SR

    # 谐波：振幅递减，越高次衰减越快（模拟真实琴弦）
    partials = [1, 2, 3, 4, 5, 6, 8]
    y = np.zeros(n)
    for k in partials:
        inharm = 1.0 + 0.0006 * k * k          # 轻微非谐性，钢琴味的关键
        decay = 3.2 / (1.0 + 0.55 * (k - 1))  # 高次谐波衰减更快
        a = amp / (k ** 1.35)
        y += a * np.sin(2 * np.pi * freq * k * inharm * t) * np.exp(-t / decay)

    # 起音：极快的 attack，避免爆音
    y *= (1.0 - np.exp(-t / 0.006))
    # 收尾淡出，防止截断咔哒声
    fade = int(0.12 * SR)
    if n > fade:
        y[-fade:] *= np.linspace(1.0, 0.0, fade)
    return y


def add_note(buf, start_sec, midi, dur, amp):
    i = int(start_sec * SR)
    if i >= len(buf):
        return
    y = piano_note(midi_to_hz(midi), dur, amp)
    j = min(len(buf), i + len(y))
    buf[i:j] += y[: j - i]


def reverb(x, tail=3.0, mix=0.34):
    """用合成的脉冲响应做 FFT 卷积混响（指数衰减噪声，模拟大厅）。"""
    n = len(x)
    ir_len = int(tail * SR)
    rng = np.random.default_rng(7)
    ir = rng.standard_normal(ir_len) * np.exp(-np.arange(ir_len) / (0.32 * SR))
    ir /= np.abs(ir).max()

    size = 1
    while size < n + ir_len:
        size *= 2
    wet = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[:n]
    wet /= max(1e-9, np.abs(wet).max())
    return x * (1.0 - mix) + wet * mix * float(np.abs(x).max())


def render(duration):
    n = int(duration * SR) + SR
    left = np.zeros(n)
    right = np.zeros(n)

    chord_i = 0
    t = 0.0
    while t < duration:
        bass, arp = PROGRESSION[chord_i % len(PROGRESSION)]
        chord_i += 1

        # 低音踏板：整小节按住，很轻
        add_note(left, t, bass, BAR * 1.15, 0.30)
        add_note(right, t, bass, BAR * 1.15, 0.30)

        # 八分音符琶音：一小节 8 个音
        step = BEAT / 2.0
        for k in range(8):
            midi = arp[k % len(arp)]
            amp = 0.26 if k % 2 == 0 else 0.19   # 强弱交替，像手弹的
            # 左右声道错开几毫秒 + 微失谐，做出宽度
            add_note(left, t + k * step, midi, BEAT * 1.6, amp)
            add_note(right, t + k * step + 0.012, midi, BEAT * 1.6, amp * 0.92)

        # 小节末尾一个高音点缀
        add_note(left, t + BAR - step, arp[-1] + 12, BEAT * 2.2, 0.12)
        add_note(right, t + BAR - step, arp[-1] + 12, BEAT * 2.2, 0.10)

        t += BAR

    left = reverb(left)
    right = reverb(right)

    # 整体淡入淡出
    fade_in = int(2.0 * SR)
    fade_out = int(4.0 * SR)
    ramp = np.linspace(0.0, 1.0, fade_in)
    left[:fade_in] *= ramp
    right[:fade_in] *= ramp
    ramp2 = np.linspace(1.0, 0.0, fade_out)
    left[-fade_out:] *= ramp2
    right[-fade_out:] *= ramp2

    stereo = np.stack([left, right], axis=1)
    peak = np.abs(stereo).max()
    if peak > 0:
        stereo *= 0.82 / peak
    return stereo


def write_wav(path, data):
    import wave

    pcm = np.clip(data, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 72.0
    out = Path(__file__).resolve().parent / "bgm.wav"
    write_wav(out, render(dur))
    print(f"{out}  ({dur:.1f}s)")
