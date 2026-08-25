# -*- coding: utf-8 -*-
"""养成猫 SVG 生成。可爱要点：大头小身(幼态)、大眼低位、腮红、全圆角、无锐角。"""
import os, subprocess

EYES = {
  "open": """
  <ellipse cx="96" cy="97" rx="13" ry="15.5" fill="{eye}"/>
  <ellipse cx="144" cy="97" rx="13" ry="15.5" fill="{eye}"/>
  <circle cx="101" cy="91" r="4.6" fill="#fff"/>
  <circle cx="149" cy="91" r="4.6" fill="#fff"/>
  <circle cx="92" cy="103" r="2.3" fill="#fff" opacity="0.75"/>
  <circle cx="140" cy="103" r="2.3" fill="#fff" opacity="0.75"/>""",

  "smug": """
  <path d="M83 93h26c0 10-6 18-13 18s-13-8-13-18z" fill="{eye}"/>
  <path d="M131 93h26c0 10-6 18-13 18s-13-8-13-18z" fill="{eye}"/>
  <circle cx="102" cy="100" r="3.6" fill="#fff"/>
  <circle cx="150" cy="100" r="3.6" fill="#fff"/>""",

  "happy": """
  <g fill="none" stroke="{eye}" stroke-width="5.5" stroke-linecap="round">
    <path d="M84 101 c6 -13 18 -13 24 0"/>
    <path d="M132 101 c6 -13 18 -13 24 0"/>
  </g>""",
}

TPL = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240" width="240" height="240">
<defs>
  <clipPath id="hd"><ellipse cx="120" cy="94" rx="66" ry="58"/></clipPath>
  <clipPath id="bd"><path d="M120 132c34 0 52 22 52 48c0 24-20 36-52 36c-32 0-52-12-52-36c0-26 18-48 52-48z"/></clipPath>
</defs>

<path d="M154 205C192 208 213 190 219 165C221 156 217 148 210 149C204 150 204 155 202 161C198 176 186 187 172 191C165 193 159 194 153 193Z"
      fill="{fur}" stroke="{line}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>

<path d="M120 132c34 0 52 22 52 48c0 24-20 36-52 36c-32 0-52-12-52-36c0-26 18-48 52-48z" fill="{fur}" stroke="{line}" stroke-width="3"/>
<g clip-path="url(#bd)">{body_patch}</g>
<path d="M120 132c34 0 52 22 52 48c0 24-20 36-52 36c-32 0-52-12-52-36c0-26 18-48 52-48z" fill="none" stroke="{line}" stroke-width="3"/>
<ellipse cx="120" cy="193" rx="29" ry="23" fill="{belly}" opacity="0.95"/>
<ellipse cx="99" cy="209" rx="15" ry="9" fill="{belly}" stroke="{line}" stroke-width="2.5"/>
<ellipse cx="141" cy="209" rx="15" ry="9" fill="{belly}" stroke="{line}" stroke-width="2.5"/>

<path d="M74 58C62 20 66 8 76 10c12 3 30 16 40 30z" fill="{ear_l}" stroke="{line}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>
<path d="M166 58C178 20 174 8 164 10c-12 3-30 16-40 30z" fill="{ear_r}" stroke="{line}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>
<path d="M82 52C74 26 77 19 83 21c7 3 18 11 24 20z" fill="{ear_in}"/>
<path d="M158 52C166 26 163 19 157 21c-7 3-18 11-24 20z" fill="{ear_in}"/>

<ellipse cx="120" cy="94" rx="66" ry="58" fill="{fur}" stroke="{line}" stroke-width="3"/>
<g clip-path="url(#hd)">{head_patch}</g>
<ellipse cx="120" cy="94" rx="66" ry="58" fill="none" stroke="{line}" stroke-width="3"/>

<g stroke="{line}" stroke-width="2.4" stroke-linecap="round" opacity="0.5">
  <path d="M54 94h-16"/><path d="M56 105l-15 6"/>
  <path d="M186 94h16"/><path d="M184 105l15 6"/>
</g>

<ellipse cx="76" cy="113" rx="13" ry="7.5" fill="#FF8FA6" opacity="0.45"/>
<ellipse cx="164" cy="113" rx="13" ry="7.5" fill="#FF8FA6" opacity="0.45"/>
{eyes}
<path d="M114 113h12l-6 7z" fill="#F2748C" stroke="#D9566F" stroke-width="1.4" stroke-linejoin="round"/>
<path d="M120 120v4" stroke="{line}" stroke-width="2.2" stroke-linecap="round"/>
<path d="M120 124c-4 6-12 5-14 0" fill="none" stroke="{line}" stroke-width="2.2" stroke-linecap="round"/>
<path d="M120 124c4 6 12 5 14 0" fill="none" stroke="{line}" stroke-width="2.2" stroke-linecap="round"/>
</svg>"""

SPECS = {
  # 橘猫 · 元气：亮橘 + 睁大眼
  "orange": dict(fur="#F6A85C", line="#B06A2C", belly="#FFF4E2", ear_in="#FFCBA4",
                 eyes="open", head_patch="", body_patch=""),
  # 奶牛猫 · 毒舌：白底黑斑 + 眯眼
  "cow": dict(fur="#FCFCFC", line="#8C8C8C", belly="#FFFFFF", ear_in="#F6BFCB",
              eyes="smug", ear_l="#3B3B3B",
              head_patch='<path d="M54 20C86 24 106 44 100 66C92 88 66 92 44 78C34 60 38 32 54 20Z" fill="#3B3B3B"/>',
              body_patch='<ellipse cx="86" cy="176" rx="34" ry="30" fill="#3B3B3B"/>'),
  # 三花 · 温柔：白底橘+棕斑 + 笑眼
  "calico": dict(fur="#FFF9F2", line="#C09A78", belly="#FFFFFF", ear_in="#F6BFCB",
                 eyes="happy", ear_l="#5A4436", ear_r="#F0A050",
                 head_patch='<path d="M52 22C82 26 100 44 94 64C86 84 62 88 42 76C32 58 36 34 52 22Z" fill="#5A4436"/>'
                            '<path d="M186 26C202 40 200 66 186 78C170 90 148 84 142 66C138 46 158 24 186 26Z" fill="#F0A050"/>',
                 body_patch='<ellipse cx="150" cy="178" rx="30" ry="26" fill="#F0A050"/>'),
}

OUT = os.path.dirname(os.path.abspath(__file__))
for name, spec in SPECS.items():
    args = dict(spec)
    args.setdefault("ear_l", spec["fur"])
    args.setdefault("ear_r", spec["fur"])
    args["eyes"] = EYES[spec["eyes"]].format(line=spec["line"], eye=spec.get("eye", "#3A2A22"))
    svg = TPL.format(**args)
    p = os.path.join(OUT, name + ".svg")
    open(p, "w").write(svg)
    subprocess.run(["rsvg-convert", "-w", "480", "-h", "480", p, "-o",
                    os.path.join(OUT, name + ".png")], check=True)
    print("生成", name)
