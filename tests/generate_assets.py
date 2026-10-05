#!/usr/bin/env python3
"""《零刻》原创像素画与音频生成器；只使用 Pillow、numpy，无外部素材。

在项目根目录运行：
    python3 tests/generate_assets.py
    python3 tests/generate_assets.py --check

--check 严格只读，清单、联系图与修改时间均不覆写。
全部路径相对于项目根目录。画面、位图字体、动作姿势及 PCM 合成均定义
于本文件，随机数使用固定种子，可确定性重建。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ASSETS = Path("assets")
OUTPUT = Path("tests/output")
RATE = 22050
SEED = 731029
DOORS = [(114, 99, 129), (257, 240, 275), (429, 412, 447), (562, 547, 577)]
PLAYER = {"Idle": 5, "Run": 10, "Prerun": 4, "Stoprun": 3, "Jump": 10,
          "Land": 2, "Roll": 7, "Slash": 5, "Squat": 3, "Wallslide": 1, "Hit": 6}
BIG_TAGS = [("Idle", 0, 5), ("Switch", 6, 12), ("Hurt", 13, 17),
            ("Hit", 18, 21), ("Death", 22, 27), ("Walk", 28, 37), ("Run", 38, 43)]
SHIELD_TAGS = [("Idle", 0, 9), ("ShieldHit", 10, 10), ("Switch", 11, 14),
               ("ShieldAttact", 15, 19), ("Shoot", 20, 27), ("ShootEnd", 28, 29),
               ("Hit", 30, 38), ("Run", 39, 45), ("Walk", 46, 53)]
EFFECTS = {"VFX_Jump": (54, 54, 5), "VFX_Land": (54, 54, 2),
           "VFX_Roll": (24, 24, 6), "VFX_Slash": (98, 36, 5),
           "受击特效": (80, 54, 5), "大壮攻击特效": (54, 44, 3),
           "射击特效": (54, 54, 5)}
PROPS = {"Bullet": (16, 8), "Crate": (28, 28), "Barrel": (22, 32),
         "Portal": (24, 54), "Platform": (96, 8)}
SOUNDS_MS = {"sound_player_jump": 244, "sound_player_land": 169,
             "sound_player_landwire": 387, "sound_player_prerun": 431,
             "sound_player_roll": 1108,
             **{f"sound_player_running_{i}": d for i, d in enumerate((146, 151, 155, 159), 1)},
             **{f"sound_player_slash_{i}": d for i, d in enumerate((667, 680, 700), 1)},
             "sound_player_wallslide": 1000, "sound_playerdie": 2612,
             "Ambient": 6000, "Music": 12000}
# 手工设计的 5×7 位图字母表，不依赖系统字体或第三方图画。
FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10111", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "00010", "10010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
    "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    ":": ["00000", "00100", "00100", "00000", "00100", "00100", "00000"],
    "/": ["00001", "00001", "00010", "00100", "01000", "10000", "10000"],
}
CYAN = (101, 244, 251)
PINK = (247, 63, 157)
INK = (8, 11, 22)


def text(draw, xy, s, color, scale=1):
    x, y = map(int, xy)
    for ch in s.upper():
        rows = FONT.get(ch)
        if rows:
            for ry, row in enumerate(rows):
                for rx, bit in enumerate(row):
                    if bit == "1":
                        draw.rectangle((x + rx * scale, y + ry * scale,
                                        x + (rx + 1) * scale - 1, y + (ry + 1) * scale - 1), fill=color)
        x += 6 * scale


def canvas(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def glow(base, layer, radii=(9, 5, 3), amounts=(0.09, 0.16, 0.23)):
    """阶梯像素光晕，不使用抗锯齿或模糊绘画。"""
    alpha = layer.getchannel("A")
    rgb = np.asarray(layer)[..., :3]
    # 使用实色，保证扩展后的透明区域仍具有正确的光晕色彩。
    live = rgb[np.asarray(alpha) > 0]
    tint = tuple(np.median(live, axis=0).astype(int)) if len(live) else CYAN
    for radius, strength in zip(radii, amounts):
        mask = alpha.filter(ImageFilter.MaxFilter(radius)).point(lambda v: round(v * strength))
        halo = Image.new("RGBA", base.size, tint + (0,))
        halo.putalpha(mask)
        base.alpha_composite(halo)
    base.alpha_composite(layer)


def save_png(image, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)


def background():
    rng = np.random.default_rng(SEED)
    w, h = 676, 288
    a = np.zeros((h, w, 4), dtype=np.uint8)
    for y in range(h):
        t = min(y / 180, 1)
        a[y, :, :] = (int(8 + 8 * t), int(13 + 10 * t), int(29 + 12 * t), 255)
    im = Image.fromarray(a, "RGBA")
    d = ImageDraw.Draw(im)
    # 三层景深天际线：折角屋顶与错落亮窗。
    for band, step, top_range, color in [(0, 47, (5, 55), (13, 24, 41)),
                                        (1, 68, (25, 68), (16, 32, 48)),
                                        (2, 102, (55, 95), (19, 38, 52))]:
        for x in range(-18 - band * 17, w, step):
            bw = step - int(rng.integers(3, 11))
            top = int(rng.integers(*top_range))
            d.polygon([(x, 116), (x, top + 8), (x + 6, top + 8), (x + 6, top),
                       (x + bw - 5, top), (x + bw - 5, top + 6), (x + bw, top + 6),
                       (x + bw, 117)], fill=color)
            d.line((x + 7, top, x + bw - 6, top), fill=(30, 53, 68))
            d.line((x + bw - 3, top + 9, x + bw - 3, 115), fill=(10, 19, 32))
            for wx in range(x + 10, x + bw - 6, 11):
                for wy in range(top + 13, 113, 12):
                    if rng.random() < .46:
                        col = [(38, 79, 98), (62, 133, 143), (77, 78, 114), (142, 76, 131)][int(rng.integers(4))]
                        d.rectangle((wx, wy, wx + 3, wy + 5), fill=col)
                        d.point((wx, wy), fill=(123, 173, 177))
            if band == 0:
                d.line((x + bw // 2, top, x + bw // 2, top - 8), fill=(39, 52, 68))
                d.point((x + bw // 2, top - 8), fill=(206, 61, 123))
    # 屋顶雨槽、承重柱、墙面结构和砖缝。
    d.rectangle((0, 117, 675, 245), fill=(16, 25, 35))
    d.rectangle((0, 116, 675, 123), fill=(27, 49, 60))
    d.line((0, 116, 675, 116), fill=(69, 99, 108))
    d.line((0, 122, 675, 122), fill=(4, 12, 23), width=2)
    for y in range(130, 243, 10):
        d.line((0, y, 675, y), fill=(11, 19, 29))
        for x in range(-18 if (y // 10) % 2 else 0, 676, 36):
            d.line((x, y - 8, x, y - 1), fill=(12, 20, 29))
            if rng.random() < .15:
                d.line((x + 3, y - 2, x + 15, y - 2), fill=(23, 38, 47))
    for x in (6, 177, 337, 500, 659):
        d.polygon([(x, 120), (x + 13, 120), (x + 16, 246), (x - 2, 246)], fill=(24, 38, 48))
        d.line((x + 2, 123, x, 244), fill=(47, 63, 70), width=2)
        d.line((x + 13, 122, x + 15, 245), fill=(6, 15, 26), width=2)
        for y in (130, 175, 233):
            d.rectangle((x + 1, y, x + 11, y + 5), fill=(34, 49, 58))
            for sx in (x + 3, x + 9):
                d.point((sx, y + 2), fill=(107, 123, 130))
    # 上半部工业窗户、玻璃划痕、钢框与窗后机械剪影。
    for x, ww in ((29, 117), (194, 118), (354, 117), (517, 117)):
        d.rectangle((x - 3, 137, x + ww + 3, 188), fill=(6, 13, 25))
        d.rectangle((x, 140, x + ww, 184), fill=(28, 62, 73))
        for gy in range(141, 185):
            d.line((x + 1, gy, x + ww - 1, gy), fill=(19 + (gy - 140) // 5, 42 + (gy - 140) // 3, 54 + (gy - 140) // 3))
        for wx in range(x + 2, x + ww - 5, 24):
            d.polygon([(wx, 183), (wx + 8, 147), (wx + 13, 147), (wx + 4, 183)], fill=(27, 60, 70))
            d.rectangle((wx + 8, 166, wx + 16, 182), fill=(11, 29, 43))
            d.line((wx + 7, 146, wx + 15, 146), fill=(65, 102, 108))
        for wx in range(x + 22, x + ww, 23):
            d.rectangle((wx, 140, wx + 3, 185), fill=(13, 26, 37))
            d.line((wx + 1, 140, wx + 1, 185), fill=(54, 78, 86))
        d.rectangle((x, 157, x + ww, 159), fill=(14, 28, 38))
        d.line((x, 138, x + ww, 138), fill=(91, 111, 117))
        d.line((x - 2, 187, x + ww + 2, 187), fill=(47, 62, 72), width=2)
        for _ in range(8):
            xx, yy = int(rng.integers(x + 4, x + ww - 3)), int(rng.integers(143, 180))
            d.line((xx, yy, xx - 2, yy + 4), fill=(47, 81, 87))
    # 弧形架空电缆与带接箍的维修管道。
    for k in range(5):
        pts = [(x, int(84 + k * 4 + 15 * math.sin(x / 145 + k * .38))) for x in range(-5, 682, 5)]
        d.line(pts, fill=(4, 8, 17), width=3 if k == 1 else 2)
        if k < 2:
            d.line([(x, y - 1) for x, y in pts], fill=(41, 49, 63), width=1)
    for x in (43, 166, 326, 486, 641):
        d.line((x, 83, x, 126), fill=(4, 11, 22), width=3)
        d.rectangle((x - 4, 121, x + 4, 128), fill=(51, 65, 77))
    for py in (127, 131):
        d.line((0, py, 676, py), fill=(10, 16, 24), width=3)
        d.line((0, py - 1, 676, py - 1), fill=(47, 63, 71))
        for x in range(22, 676, 54):
            d.line((x, py - 2, x, py + 2), fill=(87, 99, 103))
    # 用原创位图字体构造霓虹字，各标牌具有独立外壳与螺栓。
    for sx, sy, label, scale, color in [(35, 39, "ZERO", 3, CYAN),
                                      (362, 48, "SECTOR", 2, PINK)]:
        sw, sh = len(label) * 6 * scale + 14, 7 * scale + 14
        d.polygon([(sx - 5, sy - 5), (sx + sw, sy - 5), (sx + sw + 4, sy + sh),
                   (sx - 5, sy + sh)], fill=(7, 15, 25))
        d.rectangle((sx - 2, sy - 2, sx + sw - 2, sy + sh - 2), outline=(46, 59, 78))
        neon = canvas(w, h)
        nd = ImageDraw.Draw(neon)
        text(nd, (sx + 5, sy + 5), label, color + (255,), scale)
        nd.line((sx + 5, sy + sh - 6, sx + sw - 9, sy + sh - 6), fill=color + (190,))
        glow(im, neon, (17, 9, 5), (.045, .09, .19))
        d = ImageDraw.Draw(im)
        for xx in (sx + 1, sx + sw - 5):
            d.point((xx, sy), fill=(138, 135, 152))
            d.point((xx, sy + sh - 4), fill=(138, 135, 152))
    # 屋顶空气处理机组：散热格栅、风扇圆环与品红状态灯。
    d.rectangle((535, 67, 625, 111), fill=(18, 32, 44), outline=(59, 81, 88))
    for fx in (555, 585):
        d.ellipse((fx - 12, 74, fx + 12, 99), fill=(8, 18, 32), outline=(65, 83, 89))
        for yy in range(77, 98, 3):
            d.line((fx - 9, yy, fx + 9, yy), fill=(35, 54, 69))
        d.line((fx - 8, 79, fx + 8, 95), fill=(73, 86, 91))
        d.line((fx + 8, 79, fx - 8, 95), fill=(73, 86, 91))
        d.ellipse((fx - 2, 84, fx + 2, 89), fill=(12, 24, 35))
    text(d, (541, 103), "HVAC-09", (89, 109, 122))
    # 门规格：中心 x114/257/429/562，真实门洞 y195..245。
    # 门洞闭区间严格使用指定坐标，外框可更宽。
    for index, (cx, aperture_left, aperture_right) in enumerate(DOORS, 1):
        d.rectangle((cx - 28, 191, cx + 28, 245), fill=(7, 13, 23))
        d.polygon([(cx - 27, 200), (cx - 19, 191), (cx + 19, 191), (cx + 27, 200),
                   (cx + 27, 245), (cx - 27, 245)], fill=(35, 48, 57))
        d.polygon([(cx - 23, 202), (cx - 17, 195), (cx + 17, 195), (cx + 23, 202),
                   (cx + 23, 245), (cx - 23, 245)], fill=(9, 18, 29))
        # 滑动门板具有斜角浮雕，不是空白方块。
        for side in (-1, 1):
            xa, xb = (cx - 21, cx - 1) if side < 0 else (cx + 1, cx + 21)
            d.polygon([(xa, 203), (xa + 4, 198), (xb - 3, 198), (xb, 203),
                       (xb, 241), (xa, 241)], fill=(23, 39, 49))
            d.line((xa + 2, 204, xa + 2, 239), fill=(52, 70, 78))
            d.polygon([(xa + 5, 209), (xb - 4, 207), (xb - 4, 228), (xa + 5, 231)], fill=(14, 27, 38))
            d.line((xa + 5, 231, xb - 4, 228), fill=(58, 78, 84))
            d.line((xa + 4, 237, xb - 3, 237), fill=(68, 88, 96))
            for gy in range(212, 223, 3):
                d.line((xa + 7, gy, xb - 6, gy), fill=(36, 56, 64))
        d.line((cx, 199, cx, 243), fill=(4, 11, 18), width=2)
        d.line((cx + 2, 203, cx + 2, 240), fill=(55, 109, 117))
        d.rectangle((cx - 24, 243, cx + 24, 245), fill=(72, 91, 97))
        for xx in range(cx - 22, cx + 23, 5):
            d.point((xx, 244), fill=(18, 37, 47))
        # 中央黑色入口遵循精确闭区间，雨丝与光晕也不得覆盖它。
        d.rectangle((aperture_left, 195, aperture_right, 245), fill=(6, 13, 23))
        d.rectangle((cx - 8, 183, cx + 8, 190), fill=(7, 16, 24))
        text(d, (cx - 5, 184), "0" + str(index), (129, 159, 162))
        d.rectangle((cx + 31, 211, cx + 38, 225), fill=(5, 15, 24), outline=(58, 72, 87))
        d.rectangle((cx + 33, 214, cx + 36, 218), fill=(71, 221, 211))
        d.line((cx + 33, 222, cx + 35, 222), fill=(199, 74, 127))
        for xx in (cx - 25, cx + 25):
            for yy in (200, 233):
                d.point((xx, yy), fill=(139, 153, 154))
        # 青蓝或品红顶灯，以及门框周围克制的墙面溢光。
        color = CYAN if index % 2 else PINK
        lamp = canvas(w, h)
        ld = ImageDraw.Draw(lamp)
        ld.line((cx - 18, 193, cx + 18, 193), fill=color + (245,), width=2)
        ld.line((cx - 25, 203, cx - 25, 229), fill=color + (155,))
        glow(im, lamp, (15, 7, 3), (.055, .1, .2))
        d = ImageDraw.Draw(im)
    # 墙面维修细节：设备柜、接线盒、导管、通风口。
    for x in (26, 192, 359, 601):
        d.rectangle((x, 199, x + 25, 237), fill=(11, 20, 30), outline=(48, 62, 74))
        d.polygon([(x + 3, 202), (x + 21, 202), (x + 23, 205), (x + 23, 232),
                   (x + 3, 232)], fill=(30, 42, 52))
        d.rectangle((x + 5, 206, x + 18, 217), fill=(8, 20, 29))
        for yy in range(208, 216, 2):
            d.line((x + 7, yy, x + 16, yy), fill=(60, 78, 85))
        text(d, (x + 5, 222), "HV", (113, 120, 112))
        d.line((x + 23, 200, x + 23, 191, x + 40, 191, x + 40, 187), fill=(52, 74, 84), width=2)
    for x in (71, 307, 474, 648):
        d.rectangle((x, 220, x + 8, 245), fill=(11, 18, 25), outline=(63, 80, 84))
        for yy in range(221, 245, 6):
            d.rectangle((x + 1, yy, x + 7, yy + 2), fill=(101, 93, 55))
            d.line((x + 1, yy + 2, x + 4, yy), fill=(20, 27, 31), width=2)
    # 地面严格从 y246 起，湿沥青与透视接缝。
    d.rectangle((0, 246, 675, 287), fill=(9, 17, 27))
    d.line((0, 246, 675, 246), fill=(105, 135, 143))
    d.line((0, 248, 675, 248), fill=(20, 42, 54), width=2)
    for yy in (255, 270, 287):
        d.line((0, yy, 675, yy), fill=(15, 26, 37))
    for xx in range(-90, 800, 89):
        d.line((int(338 + (xx - 338) * .8), 250, xx, 288), fill=(5, 12, 22))
        d.line((int(338 + (xx - 338) * .8) + 1, 250, xx + 1, 288), fill=(22, 34, 43))
    # 各亮门与标牌下方的破碎倒影，由渐变波纹片段构成。
    for cx, color in [(114, CYAN), (257, PINK), (429, CYAN), (562, PINK), (70, CYAN), (399, PINK)]:
        for yy in range(251, 287):
            span = int(7 + (yy - 250) * .48)
            strength = max(.03, .32 * (1 - (yy - 250) / 45))
            col = tuple(int(c * strength) for c in color)
            if yy % 3:
                left = cx - span + int(rng.integers(-6, 7))
                d.line((left, yy, cx + span + int(rng.integers(-4, 5)), yy), fill=col)
                if yy % 4 == 0:
                    d.line((left + 2, yy, left + 8, yy), fill=tuple(int(c * strength * 1.5) for c in color))
    for _ in range(240):
        x, y = int(rng.integers(w)), int(rng.integers(251, 288))
        d.line((x, y, x + int(rng.integers(1, 5)), y), fill=(26, 45, 55))
    for gx in (155, 328, 638):
        d.polygon([(gx - 15, 258), (gx + 13, 258), (gx + 17, 268), (gx - 19, 268)], fill=(6, 12, 20), outline=(44, 58, 66))
        for xx in range(gx - 12, gx + 13, 4):
            d.line((xx, 260, xx + 1, 266), fill=(42, 58, 67))
    # 细前景雨丝、屋顶水滴与积水溅点。
    rain = canvas(w, h)
    rd = ImageDraw.Draw(rain)
    for _ in range(350):
        x, y = int(rng.integers(w)), int(rng.integers(0, 286))
        length = int(rng.integers(2, 8))
        rd.line((x, y, x - 1, y + length), fill=(114, 164, 191, int(rng.integers(20, 68))))
    im.alpha_composite(rain)
    d = ImageDraw.Draw(im)
    for _, left, right in DOORS:
        d.rectangle((left, 195, right, 245), fill=(6, 13, 23, 255))
    d.line((0, 246, 675, 246), fill=(105, 135, 143, 255))
    return im


def poly(d, points, fill, outline=INK):
    points = [(round(x), round(y)) for x, y in points]
    d.polygon(points, fill=fill)
    if outline is not None:
        d.line(points + [points[0]], fill=outline, width=1)


def limb(d, start, joint, end, thick, colors):
    """带轮廓边界与接缝的折角三色关节肢体。"""
    shadow, mid, light = colors
    pts = [tuple(map(round, p)) for p in (start, joint, end)]
    d.line(pts, fill=INK, width=thick + 2)
    d.line(pts, fill=shadow, width=thick)
    d.line([(x - 1, y) for x, y in pts], fill=mid, width=max(1, thick - 2))
    d.line((pts[0], pts[1]), fill=light, width=1)
    d.point((pts[1][0] + 1, pts[1][1]), fill=light)


def boot(d, x, y, side=1, broad=False):
    x, y = round(x), round(y)
    ww = 7 if broad else 5
    poly(d, [(x - 3, y - 5), (x + 2, y - 5), (x + ww * side, y - 2),
             (x + ww * side, y), (x - 3, y)], (15, 28, 35))
    d.line((min(x - 2, x + ww * side), y, max(x - 2, x + ww * side), y), fill=(74, 100, 105))
    d.line((x - 1, y - 4, x + 2, y - 4), fill=(58, 79, 84))


def scarf(d, neck, phase, reach=19, down=False):
    x, y = neck
    delta = round(2 * math.sin(phase))
    endx = x - reach
    endy = y + (7 if down else -2) + delta
    poly(d, [(x + 2, y - 2), (x - 4, y - 2), (x - 9, y + delta),
             (endx, endy), (endx + 4, endy + 4), (x - 8, y + 4 + delta),
             (x + 2, y + 2)], (167, 31, 99))
    d.line((x - 5, y - 1, x - 10, y + delta, endx + 1, endy + 1), fill=PINK, width=2)
    d.point((endx + 4, endy + 2), fill=(255, 124, 190))


def katana(d, hand, tip, bright=True):
    hx, hy = map(round, hand)
    tx, ty = map(round, tip)
    dx, dy = tx - hx, ty - hy
    length = max(1, math.hypot(dx, dy))
    ux, uy = dx / length, dy / length
    start = (round(hx + ux * 5), round(hy + uy * 5))
    d.line((hx - round(ux * 4), hy - round(uy * 4), hx, hy), fill=INK, width=4)
    d.line((hx - round(ux * 3), hy - round(uy * 3), hx, hy), fill=(130, 76, 112), width=2)
    d.line((hx - round(uy * 3), hy + round(ux * 3), hx + round(uy * 3), hy - round(ux * 3)), fill=(239, 167, 139), width=2)
    d.line((start, (tx, ty)), fill=(18, 59, 73), width=4)
    d.line((start, (tx, ty)), fill=(67, 173, 192), width=2)
    d.line(((start[0] - 1, start[1]), (tx - 1, ty)), fill=(198, 255, 255) if bright else (112, 186, 192))
    d.point((tx, ty), fill=(242, 255, 255))


def player_frame(action, i, n):
    im = canvas(72, 54)
    d = ImageDraw.Draw(im)
    p = i / max(n - 1, 1)
    phase = i / n * math.tau
    # 姿势使用人体关节坐标，不是静态帧的平移复制。
    hip = (36, 35)
    chest = (35, 24)
    head = (35, 13)
    feet = [(30, 53), (41, 53)]
    knees = [(31, 44), (41, 44)]
    shoulders = [(31, 24), (40, 24)]
    hands = [(25, 36), (45, 34)]
    elbows = [(26, 30), (43, 30)]
    swordtip = (65, 18)
    sword = action not in ("Roll", "Hit")
    if action == "Idle":
        bob = (0, -1, -1, 0, 1)[i]
        chest = (35, 23 + bob)
        head = (35, 12 + bob)
        hands[1] = (43 + (i % 2), 34 + bob)
        swordtip = (61 + (i % 2), 16 + bob)
    elif action in ("Run", "Prerun", "Stoprun"):
        run = action == "Run"
        q = math.sin(phase) if run else (p if action == "Prerun" else 1 - p)
        spread = 13 if run else 4 + 7 * abs(q)
        chest = (40 + round(2 * abs(q)), 25 + (i % 2 if run else round(3 * q)))
        head = (43 + round(2 * abs(q)), chest[1] - 11)
        hip = (35, 35 + round(2 * abs(q)))
        feet = [(36 + round(spread * q), 53), (36 - round(spread * q), 53 - round(8 * max(0, math.cos(phase))))]
        knees = [(35 + round(7 * q), 44), (35 - round(10 * q), 42)]
        shoulders = [(36, chest[1]), (44, chest[1])]
        hands = [(27 - round(6 * q), 31 + round(3 * q)), (43 + round(10 * q), 32 - round(6 * q))]
        elbows = [(29, 30), (47 + round(5 * q), 28)]
        swordtip = (hands[1][0] - 22, hands[1][1] - 16)
    elif action == "Jump":
        rise = math.sin(p * math.pi)
        chest = (35 + round(3 * math.sin(p * math.tau)), 21 + round(3 * p))
        head = (chest[0], chest[1] - 11)
        hip = (34, 34)
        feet = [(26 + round(9 * p), 53), (46 - round(10 * p), 47 - round(6 * rise))]
        knees = [(27 - round(4 * rise), 40), (45, 36 + round(4 * p))]
        shoulders = [(chest[0] - 4, chest[1]), (chest[0] + 4, chest[1])]
        hands = [(21, 23 + round(10 * p)), (46, 23 - round(9 * rise))]
        elbows = [(25, 21), (45, 26 - round(8 * rise))]
        swordtip = (65, 9 + round(7 * p))
    elif action in ("Land", "Squat"):
        depth = (7 if i == 0 else 3) if action == "Land" else (4, 9, 6)[i]
        hip = (35, 37 + depth)
        chest = (37, 25 + depth)
        head = (40, 14 + depth)
        feet = [(25, 53), (46, 53)]
        knees = [(21, 44), (49, 43)]
        shoulders = [(33, chest[1]), (41, chest[1])]
        elbows = [(26, 35 + depth), (48, 35 + depth)]
        hands = [(28, 43 + min(3, depth)), (53, 39 + depth)]
        swordtip = (68, 32 + depth)
    elif action == "Slash":
        chest = (35 + i, 25 + (2 if i == 2 else 0))
        head = (37 + i, 14 + (i % 2))
        hip = (34, 36)
        feet = [(23, 53), (48, 53)]
        knees = [(27, 44), (45, 43)]
        hands[1], elbows[1], swordtip = [((34, 20), (43, 23), (14, 3)),
            ((48, 16), (44, 25), (61, 2)), ((49, 27), (43, 25), (69, 19)),
            ((48, 37), (44, 30), (67, 43)), ((43, 37), (43, 31), (60, 49))][i]
        hands[0], elbows[0] = (28 - i, 32 + i), (29, 29)
        shoulders = [(chest[0] - 5, chest[1]), (chest[0] + 4, chest[1])]
    elif action == "Wallslide":
        chest, head, hip = (39, 25), (39, 12), (35, 36)
        shoulders, elbows, hands = [(34, 23), (43, 23)], [(28, 16), (47, 19)], [(30, 8), (48, 10)]
        knees, feet, swordtip = [(26, 40), (43, 44)], [(30, 53), (47, 48)], (60, 33)
    if action in ("Roll", "Hit"):
        # 真正的翻滚与倒地序列，最终尸体仍贴合 y53。
        if action == "Roll":
            r = [0, 1, 2, 3, 4, 5, 6][i]
            centers = [(34, 40), (34, 39), (35, 38), (35, 38), (36, 39), (37, 40), (39, 38)]
            cx, cy = centers[r]
            angles = [-.1, -.7, -1.6, -2.5, -3.4, -4.5, -5.5]
            angle = angles[r]
            def rot(x, y):
                return (cx + x * math.cos(angle) - y * math.sin(angle),
                        cy + x * math.sin(angle) + y * math.cos(angle))
            poly(d, [rot(-9, -6), rot(5, -8), rot(12, -2), rot(9, 8), rot(-7, 9)], (20, 49, 61))
            poly(d, [rot(-5, -5), rot(3, -6), rot(8, 2), rot(3, 5), rot(-6, 3)], (38, 88, 98))
            hx, hy = rot(2, -9)
            d.ellipse((round(hx - 4), round(hy - 4), round(hx + 4), round(hy + 4)), fill=(188, 138, 136), outline=INK)
            d.polygon([rot(-3, -12), rot(5, -13), rot(7, -8), rot(1, -7)], fill=(6, 10, 20))
            scarf(d, (round(hx), round(hy + 4)), phase, 17, True)
            limb(d, rot(0, 5), rot(-10, 8), (28 + i % 3, 51), 5, ((13, 27, 38), (30, 59, 69), (74, 105, 106)))
            boot(d, 28 + i % 3, 53)
            boot(d, 44 - i % 3, 51)
            katana(d, (47, 44 - i % 3), (62, 32 + i % 2), False)
        else:
            if i < 3:
                cx, cy = 34 - i * 3, 26 + i * 7
                poly(d, [(cx - 6, cy - 4), (cx + 6, cy - 3), (cx + 8, cy + 12), (cx - 9, cy + 11)], (26, 58, 69))
                limb(d, (cx, cy + 9), (28, 45), (24, 51), 5, ((12, 23, 34), (28, 51, 64), (63, 89, 100)))
                limb(d, (cx + 3, cy + 9), (43, 44), (45, 51), 5, ((12, 23, 34), (28, 51, 64), (63, 89, 100)))
                boot(d, 24, 53)
                boot(d, 45, 53)
                d.ellipse((cx - 4, cy - 14, cx + 5, cy - 5), fill=(184, 125, 127), outline=INK)
                poly(d, [(cx - 5, cy - 13), (cx + 3, cy - 16), (cx + 7, cy - 10), (cx - 3, cy - 8)], (7, 11, 22))
                scarf(d, (cx, cy - 4), phase, 17, True)
                limb(d, (cx - 4, cy), (cx - 10, cy + 6), (cx - 12, cy - 2), 4, ((18, 34, 44), (33, 65, 75), (70, 98, 109)))
            else:
                settle = i - 3
                poly(d, [(19, 43 + settle), (30, 39 + settle), (45, 45), (50, 50), (47, 53), (20, 53)], (24, 52, 62))
                d.line((26, 45 + settle, 40, 48, 53, 49), fill=(68, 99, 107), width=2)
                boot(d, 55, 53)
                d.ellipse((10, 42 + settle, 21, 52), fill=(184, 123, 128), outline=INK)
                poly(d, [(9, 46), (11, 41 + settle), (18, 40 + settle), (22, 45 + settle), (16, 49), (9, 50)], (6, 10, 20))
                scarf(d, (22, 48), phase, 13, True)
                limb(d, (27, 47), (26, 50), (34, 51), 4, ((16, 31, 42), (31, 60, 73), (68, 93, 101)))
                d.line((47, 51, 68, 50), fill=(73, 160, 179), width=2)
                d.line((48, 50, 68, 49), fill=(167, 246, 245))
        return im
    # 身体后方的远侧手臂与飘动围巾。
    scarf(d, (head[0], head[1] + 8), phase, 22 if action == "Run" else 18)
    cloth = ((11, 24, 36), (24, 52, 65), (57, 91, 103))
    limb(d, shoulders[0], elbows[0], hands[0], 4, cloth)
    d.rectangle((round(hands[0][0] - 2), round(hands[0][1] - 1), round(hands[0][0] + 1), round(hands[0][1] + 2)), fill=(182, 126, 121))
    # 先绘远腿再绘近腿，表现关节褶皱与抬起的脚尖。
    for k in (1, 0):
        limb(d, (hip[0] + (-3 if k == 0 else 3), hip[1]), knees[k], (feet[k][0], feet[k][1] - 3), 6, cloth)
        d.line((round(knees[k][0] - 2), round(knees[k][1]), round(knees[k][0] + 2), round(knees[k][1] + 1)), fill=(78, 95, 107))
        boot(d, *feet[k])
    hx, hy = hip
    cx, cy = chest
    poly(d, [(cx - 6, cy - 3), (cx + 6, cy - 3), (cx + 7, cy + 5),
             (hx + 7, hy + 1), (hx - 6, hy + 2), (cx - 8, cy + 3)], (22, 49, 62))
    poly(d, [(cx - 4, cy - 2), (cx + 1, cy - 2), (hx + 1, hy - 2), (hx - 5, hy - 2)], (35, 74, 85), None)
    d.line((cx + 3, cy - 2, hx - 3, hy - 4), fill=(79, 108, 116), width=1)
    d.line((cx + 4, cy + 4, hx + 3, hy - 3), fill=(13, 30, 43), width=2)
    d.line((hx - 5, hy - 2, hx + 6, hy - 2), fill=(116, 63, 109), width=2)
    d.rectangle((hx + 1, hy - 3, hx + 3, hy - 1), fill=(206, 158, 125))
    # 短衣摆、交叉腰带与背后刀鞘。
    poly(d, [(hx - 5, hy), (hx + 5, hy), (hx + 8, hy + 5), (hx + 1, hy + 3), (hx - 8, hy + 6)], (13, 30, 42))
    d.line((cx - 8, cy - 4, hx - 9, hy + 7), fill=INK, width=3)
    d.line((cx - 9, cy - 4, hx - 10, hy + 7), fill=(68, 65, 97))
    # 面部、后梳黑发、青蓝亮边刘海与表现神情的单眼。
    xx, yy = head
    poly(d, [(xx - 4, yy - 4), (xx + 3, yy - 4), (xx + 6, yy), (xx + 5, yy + 5),
             (xx + 1, yy + 7), (xx - 4, yy + 4)], (207, 149, 141))
    d.line((xx + 4, yy + 3, xx + 5, yy + 3), fill=(248, 199, 171))
    d.line((xx - 2, yy + 5, xx + 1, yy + 6), fill=(146, 81, 102))
    poly(d, [(xx - 6, yy + 2), (xx - 7, yy - 3), (xx - 3, yy - 7), (xx + 3, yy - 7),
             (xx + 6, yy - 4), (xx + 7, yy - 1), (xx + 1, yy - 2), (xx - 1, yy + 3),
             (xx - 2, yy), (xx - 4, yy + 4)], (6, 10, 21))
    d.line((xx - 4, yy - 4, xx, yy - 5, xx + 4, yy - 3), fill=(37, 64, 81))
    d.point((xx + 3, yy), fill=(47, 25, 49) if action == "Idle" and i == 3 else (228, 244, 219))
    # 前景叠绘前臂、手指与亮青武士刀。
    limb(d, shoulders[1], elbows[1], hands[1], 4, cloth)
    fx, fy = map(round, hands[1])
    d.rectangle((fx - 1, fy - 1, fx + 2, fy + 2), fill=(216, 157, 137))
    d.point((fx + 2, fy), fill=(255, 203, 168))
    if sword:
        katana(d, hands[1], swordtip)
    return im


def big_frame(tag, i, n):
    im = canvas(72, 54)
    d = ImageDraw.Draw(im)
    p, ph = i / max(1, n - 1), i / n * math.tau
    cx, cy = 35, 27 + int(i % 3 == 1)
    hip = (34, 38)
    feet, knees = [(25, 53), (46, 53)], [(26, 45), (45, 45)]
    shoulders = [(24, 24), (45, 24)]
    hands, elbows = [(19, 37), (52, 36)], [(17, 29), (51, 29)]
    if tag == "Idle":
        # 六种缓慢呼吸姿势：肩膀、拳节与颈部倾斜均有变化。
        cy += (0, -1, -1, 0, 1, 1)[i]
        cx += (0, 0, 1, 1, 0, -1)[i]
        hands = [(19 - (0, 1, 2, 2, 1, 0)[i], 37 + (0, 0, 1, 2, 2, 1)[i]),
                 (52 + (0, 1, 1, 0, -1, -1)[i], 36 + (0, -1, -2, -1, 0, 1)[i])]
        elbows = [(17, 29 + i // 3), (51 + i % 2, 29 - i // 2)]
    elif tag in ("Walk", "Run"):
        q = math.sin(ph)
        spread = 11 if tag == "Walk" else 16
        feet = [(35 + round(spread * q), 53), (35 - round(spread * q), 53 - round(6 * max(0, math.cos(ph))))]
        knees = [(35 + round(7 * q), 44), (35 - round(9 * q), 44)]
        cx += 2 if tag == "Run" else 0
        cy += 1 if tag == "Run" else 0
        hands = [(19 - round(5 * q), 37), (51 + round(5 * q), 35 - round(3 * q))]
    elif tag == "Switch":
        cx -= round(3 * p)
        elbows[1], hands[1] = (48 - round(10 * p), 22 - round(7 * p)), (51 - round(18 * p), 26 - round(16 * p))
        hands[0] = (17, 35 + round(3 * p))
    elif tag == "Hit":
        cx += (1, 4, 5, 2)[i]
        elbows[1], hands[1] = (48 + 3 * i, 25), ((55, 23), (64, 25), (67, 29), (53, 34))[i]
        feet, knees = [(23, 53), (49, 53)], [(26, 45), (47, 44)]
    elif tag == "Hurt":
        cx -= round(5 * p)
        cy += round(7 * p)
        hands = [(14, 27 + round(14 * p)), (55, 22 + round(15 * p))]
        elbows = [(18, 24 + round(9 * p)), (48, 25 + round(9 * p))]
    elif tag == "Death":
        if i < 2:
            cx, cy = 31 - i * 4, 35 + i * 7
            shoulders = [(cx - 10, cy - 4), (cx + 10, cy - 4)]
            hip = (cx, 45)
            hands = [(14, 44), (53, 44 + i * 4)]
            elbows = [(16, 35 + i * 6), (47, 36 + i * 6)]
        else:
            poly(d, [(14, 43 + min(i, 4)), (23, 39 + min(i, 4)), (40, 43), (46, 48),
                     (52, 49), (55, 53), (14, 53)], (74, 34, 60))
            poly(d, [(20, 46), (28, 43 + i % 2), (39, 47), (40, 51), (23, 51)], (122, 55, 73))
            d.line((23, 47, 38, 49), fill=(184, 88, 92), width=2)
            limb(d, (30, 48), (42, 48), (53, 50), 7, ((16, 27, 38), (41, 51, 66), (96, 111, 115)))
            boot(d, 56, 53, broad=True)
            d.ellipse((7, 42 + i % 2, 20, 52), fill=(179, 121, 113), outline=INK)
            d.rectangle((7, 44 + i % 2, 14, 50), fill=(32, 36, 49))
            d.line((9, 43 + i % 2, 17, 43 + i % 2), fill=(76, 79, 85))
            limb(d, (25, 48), (21, 51), (31, 51), 6, ((114, 67, 69), (182, 116, 106), (224, 159, 129)))
            d.rectangle((29, 49, 35, 53), fill=(43, 58, 71), outline=INK)
            d.point((32, 50), fill=(144, 170, 175))
            return im
    # 厚重护甲躯干下方的靴子与工装裤。
    trousers = ((16, 25, 37), (35, 48, 63), (83, 98, 109))
    skin = ((108, 65, 69), (184, 122, 106), (225, 164, 131))
    limb(d, shoulders[0], elbows[0], hands[0], 7, skin)
    for k in (1, 0):
        limb(d, (hip[0] + (5 if k else -5), hip[1]), knees[k], (feet[k][0], feet[k][1] - 4), 8, trousers)
        d.rectangle((round(knees[k][0] - 4), 41, round(knees[k][0] + 3), 45), fill=(51, 61, 74), outline=INK)
        boot(d, *feet[k], broad=True)
    poly(d, [(cx - 13, cy - 8), (cx - 9, cy - 12), (cx + 9, cy - 11),
             (cx + 14, cy - 6), (cx + 11, hip[1] + 2), (cx - 10, hip[1] + 2)], (84, 35, 58))
    poly(d, [(cx - 8, cy - 8), (cx + 6, cy - 7), (cx + 8, cy + 6),
             (cx - 8, cy + 7)], (122, 52, 69))
    d.line((cx - 9, cy - 8, cx - 8, cy + 4), fill=(175, 81, 84), width=2)
    d.line((cx + 7, cy - 5, cx + 7, cy + 8), fill=(47, 27, 47), width=2)
    for yy in (cy - 4, cy + 1, cy + 5):
        d.line((cx - 5, yy, cx + 4, yy), fill=(55, 31, 49))
    text(d, (cx - 4, cy - 5), "0", (210, 129, 133))
    d.line((cx - 10, hip[1], cx + 10, hip[1]), fill=(14, 22, 35), width=3)
    d.rectangle((cx - 2, hip[1] - 1, cx + 2, hip[1] + 1), fill=(158, 144, 118))
    for xx in (cx - 11, cx + 9):
        d.rectangle((xx, hip[1] - 1, xx + 3, hip[1] + 3), fill=(41, 47, 59), outline=INK)
    # 粗颈、不对称短发与紧绷的面罩表情。
    hy = cy - 18
    d.rectangle((cx - 4, hy + 7, cx + 4, hy + 12), fill=(153, 92, 87))
    poly(d, [(cx - 7, hy - 4), (cx + 4, hy - 5), (cx + 8, hy),
             (cx + 7, hy + 8), (cx + 2, hy + 11), (cx - 7, hy + 7)], (191, 130, 113))
    d.polygon([(cx - 7, hy - 4), (cx - 5, hy - 6), (cx + 4, hy - 6), (cx + 7, hy - 3),
               (cx - 2, hy - 2), (cx - 5, hy + 1), (cx - 7, hy + 1)], fill=(33, 28, 42))
    d.line((cx - 4, hy - 4, cx + 3, hy - 4), fill=(79, 59, 66))
    d.line((cx + 2, hy + 1, cx + 6, hy), fill=(49, 21, 33), width=2)
    d.point((cx + 5, hy + 2), fill=(255, 178, 82))
    poly(d, [(cx - 1, hy + 5), (cx + 8, hy + 4), (cx + 6, hy + 9), (cx, hy + 9)], (38, 47, 61))
    d.line((cx + 1, hy + 6, cx + 5, hy + 6), fill=(116, 151, 157))
    limb(d, shoulders[1], elbows[1], hands[1], 8, skin)
    for hand in hands:
        x, y = map(round, hand)
        poly(d, [(x - 5, y - 4), (x + 5, y - 4), (x + 6, y + 3), (x - 5, y + 4)], (43, 55, 71))
        d.line((x - 4, y - 3, x + 4, y - 3), fill=(143, 163, 164), width=2)
        for xx in (x - 2, x + 1, x + 4):
            d.point((xx, y), fill=(204, 203, 177))
    return im


def shield_frame(tag, i, n):
    im = canvas(51, 44)
    d = ImageDraw.Draw(im)
    p, ph = i / max(1, n - 1), i / n * math.tau
    cx, cy = 23, 21 + int(i % 4 == 2)
    hip = (22, 31)
    feet, knees = [(16, 43), (29, 43)], [(17, 37), (28, 37)]
    shieldx, shieldy = 34, 23
    gunhand = (32, 24)
    muzzle = (47, 23)
    if tag == "Idle":
        # 十种不同的手部、护目镜瞄准微调，靴底始终贴底。
        cy += (0, 0, -1, -1, -1, 0, 0, 1, 1, 0)[i]
        cx += (0, 0, 0, 1, 1, 1, 0, 0, -1, -1)[i]
        shieldy += (0, -1, -1, -2, -1, 0, 1, 1, 0, 0)[i]
        shieldx += (0, 0, 1, 1, 0, -1, -1, 0, 0, 1)[i]
        gunhand = (31 + i % 2, 24 + (0, 1, 1, 0, -1, -1, 0, 0, 1, 1)[i])
        muzzle = (46 + i % 2, 23 + (0, 0, -1, -1, -2, -1, 0, 1, 1, 0)[i])
    elif tag in ("Walk", "Run"):
        q = math.sin(ph)
        span = 7 if tag == "Walk" else 10
        feet = [(23 + round(span * q), 43), (23 - round(span * q), 43 - round(4 * max(0, math.cos(ph))))]
        knees = [(23 + round(5 * q), 37), (23 - round(7 * q), 35)]
        cx += 1 if tag == "Run" else 0
        shieldy += round(2 * math.sin(ph))
        shieldx -= 2 if tag == "Run" else 0
        gunhand, muzzle = (29, 25 + i % 2), (44, 23 + i % 2)
    elif tag == "Switch":
        gunhand, muzzle = (29 + round(3 * p), 30 - round(8 * p)), (43 + round(4 * p), 31 - round(10 * p))
        shieldx -= round(3 * p)
    elif tag == "Shoot":
        recoil = (0, 3, 2, 1, 0, 3, 2, 0)[i]
        gunhand, muzzle = (32 - recoil, 22 + i // 4), (48 - recoil, 21 + (i % 3 - 1))
        cx -= recoil // 2
        shieldx -= 3
        shieldy += (0, -2, -1, 0, 1, -1, 0, 2)[i]
    elif tag == "ShootEnd":
        gunhand, muzzle = (32 - i, 24 + i * 5), (47 - i, 23 + i * 6)
    elif tag == "ShieldAttact":
        shift = (-2, 0, 4, 6, 2)[i]
        cx += shift // 2
        shieldx += shift
        shieldy -= 1
        feet = [(13, 43), (31, 43)]
    elif tag == "ShieldHit":
        shieldx, shieldy, cx = 31, 21, 21
        gunhand, muzzle = (26, 29), (40, 27)
    elif tag == "Hit":
        if i >= 4:
            settle = min(i - 4, 3)
            poly(d, [(8, 34 + settle), (18, 33 + settle), (30, 37), (39, 40),
                     (40, 43), (9, 43)], (26, 48, 62))
            d.line((15, 38 + settle // 2, 27, 40), fill=(79, 104, 114), width=2)
            boot(d, 40, 43)
            d.ellipse((4, 33 + settle, 14, 42), fill=(45, 61, 73), outline=INK)
            d.line((5, 37 + settle // 2, 10, 37 + settle // 2), fill=(85, 212, 219), width=2)
            poly(d, [(21, 39), (32, 36 + settle // 2), (42, 39), (39, 43), (22, 43)], (45, 68, 79))
            d.line((24, 40, 37, 39 + settle % 2), fill=(130, 164, 170))
            d.line((13, 41, 23 - i % 3, 41 - int(i == 8)), fill=(173, 128, 124), width=2)
            # 盾缝与手套逐渐落稳，最后保持姿势也具有不同帧。
            d.line((24 + i % 3, 41, 33 + i % 2, 41), fill=(28, 45, 57))
            return im
        cx -= i
        cy += 3 * i
        hip = (22 - i, 33 + i * 2)
        shieldx -= 2 * i
        shieldy += 2 * i
        gunhand, muzzle = (30 - i, 24 + 5 * i), (45 - i, 25 + 4 * i)
    suit = ((12, 25, 39), (29, 52, 70), (65, 92, 111))
    limb(d, (cx - 5, cy), (cx - 9, cy + 4), (cx - 8, cy + 11), 4, suit)
    for k in (1, 0):
        limb(d, (hip[0] + (3 if k else -3), hip[1]), knees[k], (feet[k][0], feet[k][1] - 3), 5, suit)
        d.line((round(knees[k][0] - 2), round(knees[k][1]), round(knees[k][0] + 2), round(knees[k][1])), fill=(120, 130, 126))
        boot(d, *feet[k])
    poly(d, [(cx - 7, cy - 5), (cx + 6, cy - 5), (cx + 8, cy + 1),
             (hip[0] + 6, hip[1]), (hip[0] - 6, hip[1]), (cx - 8, cy + 1)], (35, 59, 75))
    poly(d, [(cx - 4, cy - 3), (cx + 3, cy - 3), (cx + 3, cy + 7), (cx - 5, cy + 7)], (55, 77, 88))
    d.line((cx - 4, cy - 3, cx - 4, cy + 6), fill=(100, 132, 137))
    for yy in (cy, cy + 3, cy + 6):
        d.line((cx - 3, yy, cx + 3, yy), fill=(24, 40, 57))
    d.line((hip[0] - 5, hip[1], hip[0] + 5, hip[1]), fill=(99, 86, 88), width=2)
    # 头盔叠层面罩、耳机与品红战术条纹。
    hy = cy - 11
    poly(d, [(cx - 6, hy - 6), (cx - 2, hy - 8), (cx + 4, hy - 7),
             (cx + 7, hy - 3), (cx + 7, hy + 5), (cx + 2, hy + 7), (cx - 6, hy + 3)], (44, 60, 74))
    d.line((cx - 3, hy - 6, cx + 2, hy - 6, cx + 5, hy - 3), fill=(118, 136, 140), width=2)
    d.line((cx - 5, hy - 1, cx + 7, hy - 1), fill=INK, width=4)
    d.line((cx - 1, hy - 1, cx + 6, hy - 1), fill=(83, 226, 232), width=2)
    d.point((cx + 5, hy - 2), fill=(222, 255, 255))
    d.rectangle((cx - 6, hy - 1, cx - 4, hy + 3), fill=(96, 58, 100), outline=INK)
    d.line((cx - 3, hy + 4, cx + 3, hy + 4), fill=(118, 103, 111))
    d.line((cx - 3, hy - 5, cx - 1, hy - 5), fill=PINK)
    # 持枪臂、手套、扳机护圈与随后坐力变化的枪机。
    limb(d, (cx + 4, cy - 1), (cx + 8, cy + 4), gunhand, 4, suit)
    gx, gy = gunhand
    d.rectangle((gx - 1, gy, gx + 3, gy + 3), fill=(146, 115, 113), outline=INK)
    mx, my = muzzle
    poly(d, [(gx, gy - 3), (mx, my - 2), (mx, my + 2), (gx + 5, gy + 1),
             (gx + 3, gy + 6), (gx, gy + 5)], (45, 43, 58))
    d.line((gx + 1, gy - 3, mx - 1, my - 2), fill=(146, 153, 161))
    d.line((gx + 4, gy, mx - 1, my), fill=(20, 21, 32))
    d.point((mx, my - 1), fill=(105, 225, 231))
    # 盾牌是不对称斜边八角形，带螺栓与内凹观察狭缝。
    sx, sy = shieldx, shieldy
    poly(d, [(sx - 7, sy - 10), (sx + 2, sy - 12), (sx + 8, sy - 7),
             (sx + 8, sy + 10), (sx + 4, sy + 16), (sx - 6, sy + 14),
             (sx - 9, sy + 8), (sx - 9, sy - 5)], (41, 67, 79))
    poly(d, [(sx - 5, sy - 7), (sx + 1, sy - 9), (sx + 5, sy - 5),
             (sx + 5, sy + 9), (sx + 2, sy + 12), (sx - 4, sy + 11), (sx - 6, sy + 6)], (66, 91, 103))
    d.line((sx - 7, sy - 6, sx - 7, sy + 8), fill=(140, 176, 181), width=2)
    d.line((sx + 6, sy - 5, sx + 6, sy + 8), fill=(14, 35, 50), width=2)
    d.rectangle((sx - 4, sy - 5, sx + 3, sy - 2), fill=(5, 18, 30), outline=(103, 136, 143))
    d.line((sx - 3, sy - 4, sx + 1, sy - 4), fill=(71, 175, 187))
    d.line((sx - 4, sy + 5, sx + 2, sy + 5), fill=(162, 93, 121), width=2)
    d.line((sx - 3, sy + 8, sx + 1, sy + 8), fill=(162, 93, 121))
    for xx, yy in ((sx - 4, sy - 8), (sx + 4, sy - 5), (sx + 3, sy + 10), (sx - 5, sy + 9)):
        d.point((xx, yy), fill=(213, 212, 192))
    return im


def sheet(w, h, count, fn):
    im = canvas(w * count, h)
    for i in range(count):
        frame = fn(i)
        im.alpha_composite(frame, (w * i, 0))
    return im


def aseprite(filename, w, h, tags):
    count = tags[-1][2] + 1
    frames = {}
    for index in range(count):
        tag = next(name for name, first, last in tags if first <= index <= last)
        duration = 130 if filename == "盾牌男.png" and tag == "Walk" else 100
        frames[f"{Path(filename).stem} {index}.aseprite"] = {
            "frame": {"x": index * w, "y": 0, "w": w, "h": h},
            "rotated": False, "trimmed": False,
            "spriteSourceSize": {"x": 0, "y": 0, "w": w, "h": h},
            "sourceSize": {"w": w, "h": h}, "duration": duration}
    return {"frames": frames, "meta": {"app": "原创程序化像素画生成器",
            "version": "1.0", "image": filename, "format": "RGBA8888",
            "size": {"w": w * count, "h": h}, "scale": "1",
            "frameTags": [{"name": name, "from": start, "to": end, "direction": "forward"}
                          for name, start, end in tags],
            "layers": [{"name": "original", "opacity": 255, "blendMode": "normal"}]}}


def effect_frame(name, w, h, i, n):
    rng = np.random.default_rng(SEED + i * 431 + sum(map(ord, name)))
    im = canvas(w, h)
    layer = canvas(w, h)
    d = ImageDraw.Draw(layer)
    p = i / max(1, n - 1)
    if name in ("VFX_Jump", "VFX_Land"):
        floor = h - 3
        spread = 8 + round(16 * p)
        height = (30 - round(10 * p)) if name == "VFX_Jump" else 11 - i * 4
        for sign in (-1, 1):
            poly(d, [(27, floor), (27 + sign * 7, floor - 7),
                     (27 + sign * spread, floor - height), (27 + sign * (spread - 3), floor - 7),
                     (27 + sign * (spread + 4), floor - 2)], (41, 140, 182, max(35, 155 - i * 22)), None)
            d.line((27 + sign * 7, floor - 2, 27 + sign * spread, floor - height), fill=(151, 248, 249, 215 - i * 30), width=2)
        for k in range(3):
            rx = spread + k * 2
            ry = 2 + k
            d.arc((27 - rx, floor - ry, 27 + rx, floor + ry), 185, 355, fill=(108, 224, 241, 180 - i * 25 - k * 30), width=1)
        for k in range(15):
            xx = int(rng.integers(4, w - 4))
            yy = int(rng.integers(max(1, floor - height - 6), floor))
            d.rectangle((xx, yy, xx + 1, yy + 1), fill=(191, 244, 247, int(rng.integers(70, 210))))
            if k % 3 == 0:
                d.line((xx, yy, xx - 1, yy + 3), fill=(63, 180, 216, 110))
        if name == "VFX_Jump":
            for k in range(3):
                xx = 23 + 4 * k
                d.line((xx, floor - 4 - i * 3, xx + (k - 1) * 2, floor - 20 - i * 4), fill=(86, 233, 237, 125 - i * 15), width=2)
    elif name == "VFX_Roll":
        radius = 6 + i
        d.arc((12 - radius, 12 - radius, 12 + radius, 12 + radius), 80 + i * 13, 310 + i * 8,
              fill=(202, 51, 157, 115), width=4)
        d.arc((13 - radius, 12 - radius, 13 + radius, 12 + radius), 160 + i * 18, 340 + i * 11,
              fill=(77, 222, 237, 210 - i * 14), width=2)
        d.arc((14 - radius, 11 - radius, 14 + radius, 11 + radius), 180 + i * 10, 300 + i * 14,
              fill=(199, 255, 251, 230 - i * 20), width=1)
        for j in range(6):
            x, y = int(rng.integers(1, 22)), int(rng.integers(5, 23))
            d.line((x, y, x - 2, y + 1), fill=(101, 232, 248, 170 - i * 17))
    elif name == "VFX_Slash":
        # 新月刀光几何：刻意设计五种不同挥刀角度。
        angle = [-.9, -.48, -.05, .37, .7][i]
        center = (16, 18)
        outer, inner = [], []
        for t in np.linspace(-.72 + angle, .72 + angle, 35):
            outer.append((center[0] + 78 * math.cos(t), center[1] + 19 * math.sin(t)))
            inner.append((center[0] + 59 * math.cos(t), center[1] + 12 * math.sin(t)))
        poly(d, outer + inner[::-1], (49, 194, 227, 140), None)
        outer2 = [(x - 6, y) for x, y in outer]
        d.line([(round(x), round(y)) for x, y in outer2], fill=(200, 255, 250, 238), width=2)
        d.line([(round(x), round(y)) for x, y in outer], fill=(120, 243, 250, 190), width=1)
        d.line([(round(x - 14), round(y + 2)) for x, y in outer], fill=(246, 55, 156, 85), width=3)
        for k in range(17):
            xx, yy = int(rng.integers(20, 94)), int(rng.integers(2, 34))
            d.line((xx, yy, min(97, xx + int(rng.integers(2, 9))), yy - 1), fill=(113, 237, 246, int(rng.integers(70, 210))))
        d.line((11, 19 + i - 2, 67 + 4 * i, 18), fill=(227, 255, 252, 230), width=1)
    elif name == "受击特效":
        cx, cy = 24, 27
        for k in range(22):
            theta = float(rng.uniform(-1.25, 1.25))
            radius = float(rng.uniform(9, 45)) * (.55 + .45 * p)
            xx, yy = cx + radius * math.cos(theta), cy + radius * math.sin(theta) * .6 + p * p * 8
            shade = [(107, 13, 58, 160), (177, 25, 79, 210), (250, 51, 113, 235), (255, 147, 171, 225)][k % 4]
            d.line((round(xx - 5 * (1 - p)), round(yy - 1), round(xx), round(yy)), fill=shade, width=2 if k % 3 else 3)
            if k % 5 == 0:
                d.rectangle((round(xx), round(yy), round(xx + 2), round(yy + 2)), fill=shade)
        if i < 3:
            poly(d, [(cx - 7, cy), (cx - 1, cy - 4), (cx + 3, cy - 14 + i * 3),
                     (cx + 7, cy - 5), (cx + 23 - i * 4, cy - 1), (cx + 7, cy + 4),
                     (cx + 3, cy + 12 - i * 2), (cx, cy + 4)], (244, 79, 129, 220 - i * 30), None)
            d.line((cx - 3, cy, cx + 10, cy), fill=(255, 233, 222, 250 - i * 30), width=2)
    elif name == "大壮攻击特效":
        cx, cy = 33 + 2 * i, 22
        for radius, col, width in [(17 + 3 * i, (239, 51, 146, 90), 5),
                                   (13 + 3 * i, (251, 123, 184, 190), 2),
                                   (10 + 2 * i, (255, 224, 229, 220), 1)]:
            d.arc((cx - radius, cy - radius, cx + radius, cy + radius), 265, 85, fill=col, width=width)
        for k in range(10):
            yy = int(rng.integers(7, h - 6))
            xx = int(rng.integers(5, 36))
            d.line((xx, yy, min(53, xx + int(rng.integers(8, 19))), yy), fill=(255, 140, 199, 130 - i * 15), width=1)
        d.line((13, cy, 48, cy), fill=(255, 229, 225, 210 - i * 35), width=2)
    else:  # 枪口效果：叠层等离子核心、光线、烟雾与迸射火星。
        cx, cy = 13, 27
        length = (29, 37, 28, 20, 12)[i]
        alpha = 230 - i * 35
        poly(d, [(cx - 3, cy - 3), (cx + 7, cy - 5), (cx + length, cy - 1),
                 (cx + 9, cy + 5), (cx - 3, cy + 3)], (35, 166, 224, alpha), None)
        poly(d, [(cx, cy - 2), (cx + 9, cy - 2), (cx + length - 5, cy),
                 (cx + 7, cy + 2), (cx, cy + 2)], (187, 255, 247, alpha), None)
        d.line((cx + 3, cy, cx + length - 6, cy), fill=(252, 255, 223, alpha), width=2)
        for k in range(12):
            angle = float(rng.uniform(-1.2, 1.2))
            rr = float(rng.uniform(8, 29))
            x, y = cx + rr * math.cos(angle), cy + rr * math.sin(angle)
            d.line((round(x), round(y), round(x + 3), round(y + math.sin(angle) * 3)), fill=(140, 229, 248, max(20, alpha - 40)), width=1)
        for k in range(4):
            xx, yy = 7 + i * 4 + k * 4, 22 - i * 2 + k % 2
            d.ellipse((xx - 4, yy - 4, xx + 5, yy + 5), fill=(72, 122, 154, 45 - i * 5), outline=(102, 189, 207, 60 - i * 6))
    glow(im, layer, (7, 5, 3), (.055, .10, .18))
    return im


def props():
    result = {}
    im = canvas(16, 8)
    d = ImageDraw.Draw(im)
    poly(d, [(0, 3), (8, 2), (12, 1), (15, 3), (15, 4), (12, 6), (8, 5), (0, 4)], (31, 125, 174, 150), None)
    d.line((4, 3, 13, 3), fill=(131, 251, 249), width=2)
    d.line((9, 3, 14, 3), fill=(255, 255, 227))
    d.line((0, 4, 7, 4), fill=(66, 174, 215, 130))
    result["Bullet"] = im
    im = canvas(28, 28)
    d = ImageDraw.Draw(im)
    poly(d, [(2, 3), (23, 0), (27, 4), (27, 26), (4, 27), (0, 22), (0, 6)], (42, 30, 41))
    poly(d, [(3, 5), (23, 3), (23, 24), (3, 25)], (91, 60, 63))
    for yy in (6, 11, 16, 21):
        d.line((4, yy, 22, yy - 1), fill=(45, 32, 45))
        d.line((5, yy + 1, 22, yy), fill=(139, 95, 78))
    poly(d, [(3, 4), (7, 4), (23, 21), (23, 25), (19, 25), (3, 8)], (171, 113, 78))
    poly(d, [(3, 22), (20, 4), (23, 4), (23, 8), (7, 25), (3, 25)], (129, 81, 67))
    d.line((4, 23, 21, 5), fill=(213, 156, 99))
    d.polygon([(24, 5), (27, 4), (27, 26), (24, 24)], fill=(50, 41, 53))
    for x, y in ((4, 5), (21, 5), (4, 23), (21, 23)):
        d.rectangle((x, y, x + 1, y + 1), fill=(201, 178, 141))
    d.line((1, 7, 1, 22), fill=(76, 134, 135))
    result["Crate"] = im
    im = canvas(22, 32)
    d = ImageDraw.Draw(im)
    d.ellipse((1, 0, 20, 6), fill=(143, 66, 102), outline=INK)
    poly(d, [(1, 3), (20, 3), (21, 27), (18, 31), (3, 31), (0, 27)], (114, 40, 73))
    d.rectangle((3, 5, 7, 27), fill=(166, 58, 91))
    d.line((4, 6, 4, 26), fill=(230, 102, 137))
    d.rectangle((15, 5, 18, 27), fill=(65, 29, 56))
    for yy in (6, 24):
        d.rectangle((1, yy, 20, yy + 2), fill=(28, 39, 49))
        d.line((2, yy, 18, yy), fill=(111, 130, 138))
    d.ellipse((1, 26, 20, 31), outline=(143, 90, 110), width=2)
    poly(d, [(11, 10), (18, 20), (5, 20)], (239, 178, 83))
    d.line((11, 13, 11, 16), fill=(46, 31, 43), width=2)
    d.point((11, 18), fill=(46, 31, 43))
    d.ellipse((5, 1, 10, 4), fill=(20, 34, 44), outline=(228, 123, 155))
    result["Barrel"] = im
    im = canvas(24, 54)
    d = ImageDraw.Draw(im)
    poly(d, [(4, 0), (19, 0), (23, 5), (23, 48), (19, 53), (4, 53), (0, 48), (0, 5)], (20, 39, 59))
    poly(d, [(6, 4), (17, 4), (20, 8), (20, 46), (17, 49), (6, 49), (3, 45), (3, 8)], (43, 50, 84))
    for yy in range(7, 48):
        for xx in range(4, 20):
            u = math.sin(xx * .62 + yy * .30) + math.cos(yy * .23 - xx * .36)
            col = (round(53 + 24 * u), round(52 + 15 * u), round(108 + 31 * u), 190)
            d.point((xx, yy), fill=col)
    d.line((3, 8, 3, 45), fill=(62, 219, 228), width=2)
    d.line((20, 8, 20, 46), fill=PINK, width=2)
    for k in range(4):
        d.arc((5 + k % 2, 8 + k * 7, 19 - k % 2, 27 + k * 7), 90, 285, fill=(149, 210, 246, 135), width=1)
    for yy in (3, 50):
        d.line((7, yy, 16, yy), fill=(189, 243, 250), width=2)
    for xx in (1, 22):
        for yy in (8, 23, 40):
            d.point((xx, yy), fill=(173, 180, 204))
    result["Portal"] = im
    im = canvas(96, 8)
    d = ImageDraw.Draw(im)
    poly(d, [(2, 0), (93, 0), (95, 2), (95, 5), (91, 7), (4, 7), (0, 5), (0, 2)], (28, 47, 57))
    d.line((2, 0, 93, 0), fill=(113, 165, 168))
    d.rectangle((2, 2, 93, 3), fill=(53, 81, 89))
    for x in range(5, 94, 10):
        d.line((x, 2, x + 4, 2), fill=(153, 141, 97))
        d.line((x + 3, 4, x + 5, 6), fill=INK, width=2)
        d.point((x + 2, 5), fill=(101, 124, 132))
    d.line((6, 7, 89, 7), fill=(12, 24, 33))
    result["Platform"] = im
    return result


def noise(rng, length, smooth=1):
    x = rng.standard_normal(length)
    if smooth > 1:
        x = np.convolve(x, np.ones(smooth) / smooth, mode="same")
        x /= max(1e-9, float(np.std(x)))
    return x


def fade_edges(x, attack=.004, release=.025):
    x = x.copy()
    a, r = min(len(x) // 3, round(attack * RATE)), min(len(x) // 3, round(release * RATE))
    if a:
        x[:a] *= np.linspace(0, 1, a)
    if r:
        x[-r:] *= np.linspace(1, 0, r)
    return x


def echoes(x, delay, gain, repeats=3):
    out = x.copy()
    step = round(delay * RATE)
    for k in range(1, repeats + 1):
        offset = step * k
        if offset < len(x):
            out[offset:] += x[:-offset] * gain ** k
    return out


def one_shot(name, ms, index):
    rng = np.random.default_rng(SEED + index * 997)
    length = round(ms * RATE / 1000)
    t = np.arange(length) / RATE
    n = noise(rng, length)
    low = noise(rng, length, 13)
    high = n - np.roll(n, 1)
    duration = ms / 1000
    # 相位积分实现扫频：sin(2pi*(f0*t + .5*k*t^2))。
    def sweep(f0, f1, decay):
        phase = math.tau * (f0 * t + .5 * (f1 - f0) * t * t / duration)
        return np.sin(phase) * np.exp(-t * decay)
    if name.endswith("jump"):
        x = .20 * high * np.exp(-t * 24) + .26 * sweep(170, 730, 10)
        x += .12 * np.sin(math.tau * 130 * t) * np.exp(-t * 30)
        x = echoes(x, .044, .22)
    elif name.endswith("landwire"):
        x = .36 * low * np.exp(-t * 42) + .16 * high * np.exp(-t * 70)
        for f, amp in ((740, .14), (1297, .10), (2280, .05), (3511, .035)):
            x += amp * np.sin(math.tau * f * t + .2) * np.exp(-t * (8 + f / 270))
        x = echoes(x, .047, .24)
    elif name.endswith("land") or "running" in name:
        variant = int(name[-1]) if "running" in name else 0
        x = .37 * low * np.exp(-t * (42 + variant)) + .21 * high * np.exp(-t * 62)
        x += .28 * sweep(118 + variant * 5, 48, 31)
        x += .11 * np.sin(math.tau * (712 + 81 * variant) * t) * np.exp(-t * 44)
        offset = round(.022 * RATE)
        x[offset:] += .08 * high[:-offset] * np.exp(-t[:-offset] * 55)
        x = echoes(x, .035, .17, 2)
    elif name.endswith("prerun"):
        env = np.exp(-((t - .075) / .038) ** 2)
        x = .17 * high * env + .22 * low * np.exp(-t * 35) + .12 * sweep(310, 90, 15)
        for start in (.11, .23):
            u = np.maximum(0, t - start)
            x += .10 * low * np.exp(-u * 55) * (t >= start)
        x = echoes(x, .056, .19)
    elif name.endswith("roll"):
        env = (np.sin(np.pi * np.minimum(t / .55, 1)) ** 2) * np.exp(-t * 2.5)
        x = .12 * low * env + .085 * high * env
        x += .19 * sweep(340, 80, 4) * (1 - np.exp(-t * 55))
        for start in (.08, .25, .47, .64):
            u = np.maximum(0, t - start)
            x += .14 * low * np.exp(-u * 48) * (t >= start)
        x = echoes(x, .087, .23)
    elif "slash" in name:
        variant = int(name[-1])
        env = np.exp(-((t - (.07 + variant * .008)) / .043) ** 2)
        x = .20 * high * env + .16 * low * env + .18 * sweep(1500 + variant * 270, 170, 13)
        for f, amp in ((1980 + variant * 71, .10), (3130 + variant * 91, .055), (4471, .025)):
            x += amp * np.sin(math.tau * f * t) * np.exp(-t * 10) * (1 - np.exp(-t * 140))
        x = echoes(x, .077, .27, 4)
    elif name.endswith("wallslide"):
        env = (.4 + .6 * np.sin(math.tau * 9.5 * t) ** 2) * (1 - np.exp(-t * 35))
        x = .065 * high * env + .10 * low * env
        x += .035 * np.sin(math.tau * 822 * t + 3 * np.sin(math.tau * 17 * t)) * env
        x = echoes(x, .06, .15, 2)
    else:  # 死亡与时间倒转冲击，不采样人声或借用录音。
        x = .29 * low * np.exp(-t * 20) + .13 * high * np.exp(-t * 35)
        x += .22 * sweep(105, 22, 1.9) + .075 * sweep(880, 85, 2.0)
        for start, f in ((.13, 146), (.33, 103), (.68, 67), (1.1, 48)):
            u = np.maximum(0, t - start)
            x += .06 * np.sin(math.tau * f * u) * np.exp(-u * 4) * (t >= start)
        x = echoes(x, .15, .34, 5)
    return fade_edges(x, .002, min(.10, duration * .2))


def ambient(seconds=6):
    """周期性雨声、风声频谱及电源、风机低鸣，可精确循环。"""
    n = round(seconds * RATE)
    rng = np.random.default_rng(SEED + 991)
    freqs = np.fft.rfftfreq(n, 1 / RATE)
    # 逆快速傅里叶变换生成周期性有色噪声，避免拼接接缝。
    spectrum = rng.standard_normal(len(freqs)) + 1j * rng.standard_normal(len(freqs))
    spectrum *= 1 / np.maximum(55, freqs) ** .48
    spectrum[freqs < 28] = 0
    spectrum[freqs > 7500] = 0
    rain = np.fft.irfft(spectrum, n=n)
    rain /= np.std(rain)
    t = np.arange(n) / RATE
    x = .045 * rain * (.85 + .15 * np.cos(math.tau * t / seconds))
    x += .025 * np.sin(math.tau * 50 * t) + .018 * np.sin(math.tau * 100 * t)
    x += .012 * np.sin(math.tau * 183 * t + .6 * np.sin(math.tau * t / seconds))
    # 管道水滴共鸣以环形累加方式写入，尾音同样跨循环边界。
    for start in (.22, .87, 1.61, 2.83, 3.49, 4.16, 5.31):
        u = np.arange(round(.34 * RATE)) / RATE
        drip = (.036 * np.sin(math.tau * 1680 * u) + .022 * np.sin(math.tau * 2440 * u)) * np.exp(-u * 24)
        drip = fade_edges(drip, .001, .02)
        indexes = (np.arange(len(drip)) + round(start * RATE)) % n
        np.add.at(x, indexes, drip)
    return x


def music(seconds=12):
    """原创 120 BPM、六小节霓虹黑色电影节奏，小调贝斯与分解和弦。

    所有音符、打击乐和混响尾音均写入环形缓冲区。音轨本身周期连续，
    不是在每次循环边界淡出成静音再拼接。
    """
    n = round(seconds * RATE)
    x = np.zeros(n)
    rng = np.random.default_rng(SEED + 881)
    def add(start, y, gain=1):
        indexes = (np.arange(len(y)) + round(start * RATE)) % n
        np.add.at(x, indexes, y * gain)
    def tone(midi, dur, kind):
        t = np.arange(round(dur * RATE)) / RATE
        f = 440 * 2 ** ((midi - 69) / 12)
        if kind == "bass":
            y = np.sin(math.tau * f * t) + .28 * np.sin(math.tau * f * 2 * t) + .10 * np.sin(math.tau * f * 3 * t)
            y *= np.exp(-t * 3.5)
        elif kind == "arp":
            y = np.sin(math.tau * f * t) + .35 * np.sin(math.tau * f * 2 * t) + .12 * np.sin(math.tau * f * 4 * t)
            y *= np.exp(-t * 7)
        else:
            y = np.sin(math.tau * f * t) + .20 * np.sin(math.tau * f * 1.003 * t) + .12 * np.sin(math.tau * f * 2 * t)
            y *= np.sin(np.pi * np.minimum(t / dur, 1)) ** 2
        return fade_edges(y, .008, .06)
    # 原创六小节和声进行：Dm / Bb / F / C / Gm / Am。
    roots = (38, 34, 41, 36, 43, 45)
    chords = ((62, 65, 69), (58, 62, 65), (60, 65, 69), (60, 64, 67), (62, 67, 70), (60, 64, 69))
    for bar in range(6):
        start = bar * 2.
        for beat in range(4):
            at = start + beat * .5
            t = np.arange(round(.36 * RATE)) / RATE
            kick = np.sin(math.tau * (49 * t + (120 - 49) * (1 - np.exp(-t * 28)) / 28)) * np.exp(-t * 14)
            kick += .10 * noise(rng, len(t)) * np.exp(-t * 95)
            add(at, fade_edges(kick, .001, .02), .17)
            if beat % 2:
                t = np.arange(round(.23 * RATE)) / RATE
                snare = .64 * noise(rng, len(t)) * np.exp(-t * 27) + .25 * np.sin(math.tau * 181 * t) * np.exp(-t * 24)
                add(at, fade_edges(snare, .001, .025), .10)
                add(at + .055, fade_edges(snare, .001, .025), .023)
            add(at + (.25 if beat == 3 else 0), tone(roots[bar] + (12 if beat == 2 else 0), .46, "bass"), .095)
        for tick in range(8):
            at = start + tick * .25
            t = np.arange(round(.095 * RATE)) / RATE
            white = noise(rng, len(t))
            hat = (white - np.roll(white, 1)) * np.exp(-t * 72)
            add(at + .125, fade_edges(hat, .001, .012), .027 if tick % 2 else .018)
            midi = chords[bar][(0, 2, 1, 2, 0, 1, 2, 1)[tick]] + (12 if tick in (3, 7) else 0)
            note = tone(midi, .72, "arp")
            add(at, note, .034)
            add(at + .375, note, .013)
            add(at + .75, note, .0045)
        for midi in chords[bar]:
            add(start, tone(midi - 12, 2.3, "pad"), .018)
    return x


def write_wav(path, samples):
    # 音乐使用整体增益，避免各层分别硬削波。
    peak = float(np.max(np.abs(samples)))
    if peak > .87:
        samples = samples * (.87 / peak)
    pcm = np.rint(np.clip(samples, -.999, .999) * 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(pcm.tobytes())


def expected_pngs():
    out = {"assets/Background.png": (676, 288, 1, False)}
    out.update({f"assets/武士零主角/{name}.png": (72, 54, n, True) for name, n in PLAYER.items()})
    out["assets/大壮动作.png"] = (72, 54, 44, True)
    out["assets/盾牌男.png"] = (51, 44, 54, True)
    out.update({f"assets/{name}.png": (w, h, n, False) for name, (w, h, n) in EFFECTS.items()})
    out.update({f"assets/{name}.png": (w, h, 1, False) for name, (w, h) in PROPS.items()})
    return out


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate():
    errors, records = [], []
    pngs = expected_pngs()
    expected = set(pngs) | {f"assets/{name}.wav" for name in SOUNDS_MS} | {"assets/大壮动作.json", "assets/盾牌男.json"}
    # 引擎预览自动生成的 .meta 是资源标识旁车文件，不是生成器新增的美术素材。
    found = {p.as_posix() for p in ASSETS.rglob("*") if p.is_file() and p.suffix != ".meta"}
    if found != expected:
        errors.append(f"资产文件集合不一致：缺少={sorted(expected - found)}，多余={sorted(found - expected)}")
    uuids = set()
    for sidecar in sorted(ASSETS.rglob("*.meta")):
        if sidecar.as_posix()[:-5] not in expected:
            errors.append(f"{sidecar}：没有对应的被消费素材")
        try:
            uuid = json.loads(sidecar.read_text(encoding="utf-8"))["uuid"]
            if not isinstance(uuid, str) or not uuid or uuid in uuids:
                errors.append(f"{sidecar}：UUID 缺失或重复")
            uuids.add(uuid)
        except (OSError, ValueError, KeyError) as e:
            errors.append(f"{sidecar}：引擎旁车配置无效，{e}")
    for name, (w, h, n, grounded) in pngs.items():
        path = Path(name)
        try:
            with Image.open(path) as source:
                im = source.convert("RGBA")
                if source.mode != "RGBA":
                    errors.append(f"{name}：需要 RGBA，实际为 {source.mode}")
            if im.size != (w * n, h):
                errors.append(f"{name}：图集尺寸 {im.size} 错误，需要 {(w * n, h)}")
                continue
            frames = []
            for index in range(n):
                a = np.asarray(im.crop((index * w, 0, (index + 1) * w, h)))
                alpha = a[..., 3]
                bbox = Image.fromarray(alpha).getbbox()
                foot_pixels = int(np.count_nonzero(alpha[-1]))
                if bbox is None:
                    errors.append(f"{name} 第 {index} 帧：空白帧")
                if grounded and foot_pixels == 0:
                    errors.append(f"{name} 第 {index} 帧：脚底未贴合最后一行")
                if grounded and not np.any(alpha == 0):
                    errors.append(f"{name} 第 {index} 帧：缺少透明背景")
                frames.append({"index": index, "rectangle": [index * w, 0, w, h],
                               "content_bounds": list(bbox) if bbox else None, "last_row_alpha_pixels": foot_pixels,
                               "sha256": hashlib.sha256(a.tobytes()).hexdigest()})
            unique = len({f["sha256"] for f in frames})
            if n > 1 and unique != n:
                errors.append(f"{name}：存在重复动作帧，只有 {unique}/{n} 帧不同")
            if name == "assets/Background.png":
                pixels = np.asarray(im)
                if not np.all(pixels[..., 3] == 255):
                    errors.append("背景必须完全不透明")
                for cx, left, right in DOORS:
                    if not np.all(pixels[195:246, left:right + 1] == (6, 13, 23, 255)):
                        errors.append(f"门中心 {cx} 的黑色入口不符合 x{left}..{right}、y195..245")
                    if not np.all(pixels[246, left:right + 1, :3] == (105, 135, 143)):
                        errors.append(f"门中心 {cx} 下方地面边缘必须为 y246")
            records.append({"path": name, "type": "png", "width": w * n, "height": h,
                            "frame_width": w, "frame_height": h, "frame_count": n,
                            "layout": "single_row_no_padding", "foot_anchor": [w / 2, h - 1] if grounded else None,
                            "unique_frames": unique, "frames": frames, "sha256": sha256(path)})
        except (OSError, ValueError) as e:
            errors.append(f"{name}: {e}")
    for filename, w, h, tags in [("大壮动作", 72, 54, BIG_TAGS), ("盾牌男", 51, 44, SHIELD_TAGS)]:
        path = ASSETS / (filename + ".json")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            wanted = aseprite(filename + ".png", w, h, tags)
            if data != wanted:
                errors.append(f"{path}：Aseprite 标签、帧或时长与精确规格不一致")
            records.append({"path": path.as_posix(), "type": "aseprite_json", "frame_count": len(data["frames"]),
                            "tags": data["meta"]["frameTags"], "sha256": sha256(path)})
        except (OSError, ValueError, KeyError) as e:
            errors.append(f"{path}: {e}")
    for name, ms in SOUNDS_MS.items():
        path = ASSETS / (name + ".wav")
        try:
            with wave.open(str(path), "rb") as f:
                channels, width, rate, frames = f.getnchannels(), f.getsampwidth(), f.getframerate(), f.getnframes()
                data = np.frombuffer(f.readframes(frames), dtype="<i2")
            if (channels, width, rate, frames) != (1, 2, RATE, round(ms * RATE / 1000)):
                errors.append(f"{path}：WAV 格式或时长不一致")
            values = data.astype(np.float64) / 32768
            peak = float(np.max(np.abs(values)))
            rms = float(np.sqrt(np.mean(values ** 2)))
            if peak >= .999 or rms < .002:
                errors.append(f"{path}：削波或静音，峰值={peak}，均方根={rms}")
            if abs(float(np.mean(values))) > .02:
                errors.append(f"{path}：直流偏置过大")
            seam = abs(int(data[-1]) - int(data[0]))
            derivative_rms = float(np.sqrt(np.mean(np.diff(data.astype(float)) ** 2)))
            # 氛围声与音乐的首尾差应与正常相邻采样变化相当。
            if name in ("Ambient", "Music") and seam > max(128, derivative_rms * 5):
                errors.append(f"{path}：循环首尾接缝不连续，差值={seam}")
            records.append({"path": path.as_posix(), "type": "wav", "sample_rate": rate,
                            "channels": channels, "bits_per_sample": width * 8, "sample_count": frames,
                            "requested_duration_ms": ms, "duration_ms": frames / rate * 1000,
                            "peak": round(peak, 6), "rms": round(rms, 6),
                            "loop": name in ("Ambient", "Music"), "loop_seam_sample_delta": seam,
                            "sha256": sha256(path)})
        except (OSError, ValueError, wave.Error) as e:
            errors.append(f"{path}: {e}")
    return records, errors


def contact_sheet():
    # 最近邻放大，完整展示所有 191 个图像单元。
    all_rows = []
    for action, n in PLAYER.items():
        all_rows.append(("PLAYER / " + action.upper(), ASSETS / "武士零主角" / (action + ".png"), 72, 54, n, 2))
    all_rows.append(("BRUISER / 44 FRAMES", ASSETS / "大壮动作.png", 72, 54, 44, 1))
    all_rows.append(("SHIELD / 54 FRAMES", ASSETS / "盾牌男.png", 51, 44, 54, 1))
    for name, (w, h, n) in EFFECTS.items():
        label = {"受击特效": "BLOOD IMPACT", "大壮攻击特效": "BRUISER PUNCH", "射击特效": "GUNSHOT"}.get(name, name.upper())
        all_rows.append((label, ASSETS / (name + ".png"), w, h, n, 2))
    total_height = 658 + 16 + 174 + 28
    for _, _, w, h, n, scale in all_rows:
        perrow = min(n, (1440 - 52) // (w * scale + 2))
        total_height += 16 + math.ceil(n / perrow) * (h * scale + 2) + 10
    result = Image.new("RGBA", (1440, total_height), (8, 14, 24, 255))
    d = ImageDraw.Draw(result)
    text(d, (30, 20), "ZERO HOUR / ORIGINAL PIXEL ART", CYAN, 3)
    with Image.open(ASSETS / "Background.png") as bg:
        result.alpha_composite(bg.resize((1352, 576), Image.Resampling.NEAREST), (44, 63))
    y = 658
    for label, path, w, h, n, scale in all_rows:
        text(d, (26, y + 3), label, (119, 160, 175), 1)
        y += 16
        perrow = min(n, (1440 - 52) // (w * scale + 2))
        with Image.open(path) as source:
            for index in range(n):
                xx = 26 + (index % perrow) * (w * scale + 2)
                yy = y + (index // perrow) * (h * scale + 2)
                d.rectangle((xx, yy, xx + w * scale - 1, yy + h * scale - 1), fill=(18, 28, 39))
                # 棋盘背景显露透明边界与贴底的靴底像素。
                for ty in range(0, h * scale, 8):
                    for tx in range(0, w * scale, 8):
                        if (ty // 8 + tx // 8) % 2:
                            d.rectangle((xx + tx, yy + ty, min(xx + tx + 7, xx + w * scale - 1), min(yy + ty + 7, yy + h * scale - 1)), fill=(25, 37, 48))
                frame = source.crop((index * w, 0, (index + 1) * w, h)).resize((w * scale, h * scale), Image.Resampling.NEAREST)
                result.alpha_composite(frame, (xx, yy))
        y += math.ceil(n / perrow) * (h * scale + 2) + 10
    text(d, (26, y), "BULLET / CRATE / BARREL / PORTAL / PLATFORM", CYAN, 1)
    y += 18
    xx = 26
    for name, (w, h) in PROPS.items():
        with Image.open(ASSETS / (name + ".png")) as prop:
            result.alpha_composite(prop.resize((w * 3, h * 3), Image.Resampling.NEAREST), (xx, y))
        xx += w * 3 + 32
    y += 174
    text(d, (26, y), "PCM16 / 22050 HZ / ORIGINAL LAYERED SYNTHESIS", PINK, 2)
    # 按实际内容分配完整联系图，仅裁去无用底部留白。
    return result.crop((0, 0, result.width, min(result.height, y + 28)))


def generate():
    ASSETS.mkdir(exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    save_png(background(), ASSETS / "Background.png")
    print("绘制背景：676x288；地面 y246；门中心 114,257,429,562")
    for action, count in PLAYER.items():
        image = sheet(72, 54, count, lambda i, a=action, n=count: player_frame(a, i, n))
        save_png(image, ASSETS / "武士零主角" / (action + ".png"))
        print(f"绘制主角 {action}：{count} 帧 x 72x54，无帧间留白")
    for name, w, h, tags, fn in [("大壮动作", 72, 54, BIG_TAGS, big_frame), ("盾牌男", 51, 44, SHIELD_TAGS, shield_frame)]:
        frames = []
        for tag, first, last in tags:
            frames.extend(fn(tag, i, last - first + 1) for i in range(last - first + 1))
        image = canvas(w * len(frames), h)
        for index, frame in enumerate(frames):
            image.alpha_composite(frame, (index * w, 0))
        save_png(image, ASSETS / (name + ".png"))
        (ASSETS / (name + ".json")).write_text(json.dumps(aseprite(name + ".png", w, h, tags), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"绘制 {name}：{len(frames)} 帧 x {w}x{h} + Aseprite JSON")
    for name, (w, h, count) in EFFECTS.items():
        image = sheet(w, h, count, lambda i, nm=name, ww=w, hh=h, n=count: effect_frame(nm, ww, hh, i, n))
        save_png(image, ASSETS / (name + ".png"))
        print(f"绘制特效 {name}：{count} 帧 x {w}x{h}")
    for name, image in props().items():
        save_png(image, ASSETS / (name + ".png"))
        print(f"绘制道具 {name}：{image.width}x{image.height}")
    for index, (name, ms) in enumerate(SOUNDS_MS.items()):
        samples = ambient() if name == "Ambient" else music() if name == "Music" else one_shot(name, ms, index)
        write_wav(ASSETS / (name + ".wav"), samples)
        print(f"合成 {name}：{ms}ms / PCM16 单声道 {RATE}Hz / {len(samples)} 采样")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="严格只读检查已有输出")
    args = parser.parse_args()
    if not Path("tests/generate_assets.py").is_file():
        parser.error("请从项目根目录运行；全部资产与输出路径均为相对路径")
    if not args.check:
        generate()
    records, errors = validate()
    if args.check:
        try:
            manifest = json.loads((OUTPUT / "asset_manifest.json").read_text(encoding="utf-8"))
            if manifest["assets"] != records:
                errors.append("资产清单已过期，或与现有资源不一致")
            sidecars = sorted(p.as_posix() for p in ASSETS.rglob("*.meta"))
            if manifest["engine_sidecars"]["paths"] != sidecars:
                errors.append("引擎旁车清单与当前文件不一致")
            with Image.open(OUTPUT / "asset_contact.png") as contact:
                if contact.width != 1440 or contact.height < 2500:
                    errors.append("联系图尺寸或内容不完整")
            if sha256(OUTPUT / "asset_contact.png") != manifest["contact_sheet"]["sha256"]:
                errors.append("联系图 SHA256 校验不一致")
        except (OSError, ValueError, KeyError) as e:
            errors.append(f"证据输出缺失或无效：{e}")
    elif not errors:
        save_png(contact_sheet(), OUTPUT / "asset_contact.png")
        manifest = {"generator": "tests/generate_assets.py", "seed": SEED,
                    "originality": "全部像素、位图字体、姿势、频谱与音乐均由代码原创，无外部素材",
                    "background": {"size": [676, 288], "ground_y": 246, "door_center_x": [114, 257, 429, 562],
                                   "door_aperture_y": [195, 245],
                                   "door_apertures": [{"center_x": cx, "x_min": left, "x_max": right, "y_min": 195, "y_max": 245}
                                                      for cx, left, right in DOORS]},
                    "assets": records, "asset_file_count": len(records),
                    "engine_sidecars": {"count": len(list(ASSETS.rglob("*.meta"))),
                                        "paths": sorted(p.as_posix() for p in ASSETS.rglob("*.meta")),
                                        "purpose": "官方 build 自动生成并消费的逐文件 UUID 导入管理配置；非生成器素材，不覆写或删除"},
                    "animation_indexing": "图集与 JSON 索引从零开始；x=帧索引*帧宽，y=0；无帧间留白",
                    "rendering": "最近邻采样；角色锚点=(帧宽/2,帧高-1)",
                    "audio": {"sample_rate": RATE, "channels": 1, "bits_per_sample": 16,
                              "duration_tolerance_ms": 1000 / RATE / 2,
                              "loop_files": ["assets/Ambient.wav", "assets/Music.wav"]},
                    "contact_sheet": {"path": "tests/output/asset_contact.png", "sha256": sha256(OUTPUT / "asset_contact.png")},
                    "verification": {"errors": [], "png_dimensions": "pass", "frame_alpha": "pass",
                                     "all_character_feet_last_row": "pass", "unique_animation_frames": "pass",
                                     "exact_aseprite_tags_and_durations": "pass", "wav_format_duration_peak": "pass",
                                     "loop_seams": "pass", "no_unused_asset_files": "pass",
                                     "exact_door_apertures": "pass", "engine_sidecars": "pass"}}
        (OUTPUT / "asset_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for error in errors:
        print("错误：", error)
    frame_count = sum(r["frame_count"] for r in records if r["type"] == "png")
    char_count = sum(n for _, _, n, ground in expected_pngs().values() if ground)
    print(f"{'检查' if args.check else '生成'} {'失败' if errors else '通过'}："
          f"{len(records)} 项资产 / {len(expected_pngs())} PNG / {frame_count} 图像帧 / "
          f"{char_count} 角色帧逐帧贴底 / {len(SOUNDS_MS)} WAV / 2 Aseprite JSON")
    print(f"引擎旁车：{len(list(ASSETS.rglob('*.meta')))} 个 UUID 导入配置，已检查且未修改")
    if args.check:
        print("严格只读：检查未新建、覆写、移除文件或修改文件的修改时间")
    elif not errors:
        print("证据：tests/output/asset_manifest.json 与 tests/output/asset_contact.png")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
