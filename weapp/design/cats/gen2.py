# -*- coding: utf-8 -*-
"""养成猫 SVG v2：蓬松毛边轮廓 + 柔和渐变 + 多层高光眼 + 虎斑 + 奶白口鼻。"""
import math, os, subprocess

def hx(c):
    c = c.lstrip('#'); return tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
def mix(c1, c2, t):
    a, b = hx(c1), hx(c2)
    return '#%02X%02X%02X' % tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
lighten = lambda c, t: mix(c, '#FFFFFF', t)
darken  = lambda c, t: mix(c, '#000000', t)

def fluffy(cx, cy, rx, ry, lobes=20, bulge=1.055, start=0.0):
    """在椭圆基础上生成一圈柔和的毛尖，作为蓬松轮廓（比光滑椭圆更像有毛）。"""
    pts = []
    for i in range(lobes + 1):
        a = start + 2 * math.pi * i / lobes
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"
    for i in range(lobes):
        a0 = start + 2 * math.pi * i / lobes
        a1 = start + 2 * math.pi * (i + 1) / lobes
        am = (a0 + a1) / 2
        # 交替内外，形成细微的毛尖起伏
        b = bulge if i % 2 == 0 else (1 + (bulge - 1) * 0.35)
        qx = cx + rx * b * math.cos(am)
        qy = cy + ry * b * math.sin(am)
        px, py = pts[i + 1]
        d += f" Q{qx:.1f} {qy:.1f} {px:.1f} {py:.1f}"
    return d + " Z"

HEAD = fluffy(120, 92, 67, 59, lobes=30, bulge=1.022)
BODY = fluffy(120, 178, 54, 44, lobes=26, bulge=1.020)

def build(fur, line, belly, ear_in, eye_iris, stripes="", head_patch="", body_patch="",
          ear_l=None, ear_r=None):
    ear_l = ear_l or fur
    ear_r = ear_r or fur
    hi = lighten(fur, .30)
    lo = darken(fur, .10)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240" width="240" height="240">
<defs>
  <radialGradient id="gh" cx="38%" cy="28%" r="78%">
    <stop offset="0%" stop-color="{hi}"/><stop offset="100%" stop-color="{fur}"/>
  </radialGradient>
  <radialGradient id="gb" cx="42%" cy="24%" r="82%">
    <stop offset="0%" stop-color="{hi}"/><stop offset="100%" stop-color="{lo}"/>
  </radialGradient>
  <radialGradient id="gm" cx="50%" cy="35%" r="70%">
    <stop offset="0%" stop-color="#FFFFFF"/><stop offset="100%" stop-color="{belly}"/>
  </radialGradient>
  <clipPath id="hd"><path d="{HEAD}"/></clipPath>
  <clipPath id="bd"><path d="{BODY}"/></clipPath>
</defs>

<!-- 尾巴（在身体之下） -->
<path d="M150 206C192 209 214 190 220 164C222 154 218 146 211 147C205 148 205 154 203 161C199 177 186 189 170 193C163 195 157 195 150 194Z"
      fill="{lo}" stroke="{line}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>

<!-- 身体 -->
<path d="{BODY}" fill="url(#gb)" stroke="{line}" stroke-width="3" stroke-linejoin="round"/>
<g clip-path="url(#bd)">{body_patch}</g>
<path d="{BODY}" fill="none" stroke="{line}" stroke-width="3" stroke-linejoin="round"/>
<!-- 胸口奶白 -->
<ellipse cx="120" cy="192" rx="30" ry="26" fill="url(#gm)" opacity="0.95"/>
<!-- 前爪 -->
<ellipse cx="100" cy="209" rx="16" ry="10" fill="{belly}" stroke="{line}" stroke-width="2.6"/>
<ellipse cx="140" cy="209" rx="16" ry="10" fill="{belly}" stroke="{line}" stroke-width="2.6"/>
<g stroke="{line}" stroke-width="1.6" opacity="0.45" stroke-linecap="round">
  <path d="M96 204v9"/><path d="M104 204v9"/>
  <path d="M136 204v9"/><path d="M144 204v9"/>
</g>

<!-- 耳朵 -->
<path d="M74 56C63 21 70 8 82 14c12 6 27 19 35 30z" fill="{ear_l}" stroke="{line}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>
<path d="M166 56C177 21 170 8 158 14c-12 6-27 19-35 30z" fill="{ear_r}" stroke="{line}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>
<path d="M83 49C74 25 79 17 86 21c8 4 18 13 24 21z" fill="{ear_in}"/>
<path d="M157 49C166 25 161 17 154 21c-8 4-18 13-24 21z" fill="{ear_in}"/>
<!-- 耳内绒毛 -->
<g stroke="#FFFFFF" stroke-width="2" opacity="0.65" stroke-linecap="round">
  <path d="M87 42l6 6"/><path d="M92 31l6 6"/>
  <path d="M153 42l-6 6"/><path d="M148 31l-6 6"/>
</g>

<!-- 头 -->
<path d="{HEAD}" fill="url(#gh)" stroke="{line}" stroke-width="3" stroke-linejoin="round"/>
<g clip-path="url(#hd)">{head_patch}{stripes}</g>
<path d="{HEAD}" fill="none" stroke="{line}" stroke-width="3" stroke-linejoin="round"/>

<!-- 口鼻区（奶白），大眼下方的浅色块能显著提升幼态感 -->
<path d="M120 110c15 0 25 7 25 15c0 9-11 14-25 14c-14 0-25-5-25-14c0-8 10-15 25-15z" fill="url(#gm)" opacity="0.9"/>

<!-- 胡须 -->
<g stroke="{darken(line,.05)}" stroke-width="2.2" stroke-linecap="round" opacity="0.45" fill="none">
  <path d="M60 104C48 102 40 100 33 96"/><path d="M60 112C48 113 40 116 34 120"/>
  <path d="M180 104C192 102 200 100 207 96"/><path d="M180 112C192 113 200 116 206 120"/>
</g>

<!-- 腮红 -->
<ellipse cx="72" cy="114" rx="14" ry="8" fill="#FF8FA6" opacity="0.42"/>
<ellipse cx="168" cy="114" rx="14" ry="8" fill="#FF8FA6" opacity="0.42"/>

<!-- 眼睛：琥珀虹膜 + 深瞳 + 三层高光 -->
<g>
  <ellipse cx="96" cy="97" rx="17.5" ry="19.5" fill="{eye_iris}"/>
  <ellipse cx="144" cy="97" rx="17.5" ry="19.5" fill="{eye_iris}"/>
  <ellipse cx="96" cy="99" rx="12.5" ry="15" fill="#2B1A12"/>
  <ellipse cx="144" cy="99" rx="12.5" ry="15" fill="#2B1A12"/>
  <circle cx="103" cy="89" r="6" fill="#fff"/>
  <circle cx="151" cy="89" r="6" fill="#fff"/>
  <circle cx="89" cy="106" r="3.1" fill="#fff" opacity="0.8"/>
  <circle cx="137" cy="106" r="3.1" fill="#fff" opacity="0.8"/>
</g>

<!-- 鼻子 + 嘴 -->
<path d="M113 116h14l-7 8z" fill="#F58BA0" stroke="#DE6A83" stroke-width="1.5" stroke-linejoin="round"/>
<path d="M120 124v4" stroke="{line}" stroke-width="2.2" stroke-linecap="round"/>
<path d="M120 128c-4 6-12 5-14 0" fill="none" stroke="{line}" stroke-width="2.2" stroke-linecap="round"/>
<path d="M120 128c4 6 12 5 14 0" fill="none" stroke="{line}" stroke-width="2.2" stroke-linecap="round"/>
</svg>'''

ORANGE = "#F2A05A"
spec = dict(
    fur=ORANGE, line="#B5702F", belly="#FFF6E8", ear_in="#FFC3A8", eye_iris="#B9762F",
    # 额头虎斑（经典 M 纹）+ 侧脸条纹
    stripes=f'''
      <g fill="{darken(ORANGE,.16)}" opacity="0.85">
        <path d="M120 34c4 0 6 4 6 12s-2 12-6 12s-6-4-6-12s2-12 6-12z"/>
        <path d="M100 38c4 1 5 5 4 12c-1 7-4 11-7 10c-4-1-4-6-3-12c1-6 3-11 6-10z"/>
        <path d="M140 38c-4 1-5 5-4 12c1 7 4 11 7 10c4-1 4-6 3-12c-1-6-3-11-6-10z"/>
      </g>''',
)

OUT = os.path.dirname(os.path.abspath(__file__))
svg = build(**spec)
open(os.path.join(OUT, "orange2.svg"), "w").write(svg)
subprocess.run(["rsvg-convert", "-w", "480", "-h", "480",
                os.path.join(OUT, "orange2.svg"), "-o",
                os.path.join(OUT, "orange2.png")], check=True)
print("ok")
