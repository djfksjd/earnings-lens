"""Gaddong(가똥) 마스코트: Morphloom으로 모델링한 3D 오브 캐릭터를 기분에 맞춰 움직인다.

모델 static/mascot/gaddong.glb, 런타임 static/mascot/mascot.bundle.js(three.js, 원본 static/mascot/src/mascot.js).
Streamlit 정적 서빙은 .js를 text/plain으로 보내므로, iframe에서 번들을 텍스트로 받아 <script>로 실행한다.
WebGL을 못 쓰거나 파일을 못 받으면 회색 CSS 오브로 대신한다.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import streamlit.components.v1 as components

_STATIC = Path(__file__).resolve().parents[2] / "static" / "mascot"


def _version() -> str:
    """번들·모델이 바뀌면 주소가 바뀌게 해 브라우저 캐시(force-cache)에 옛 파일이 남지 않게 한다."""
    h = hashlib.sha256()
    for name in ("mascot.bundle.js", "gaddong.glb"):
        p = _STATIC / name
        h.update(f"{name}:{p.stat().st_size}:{p.stat().st_mtime_ns}".encode() if p.exists() else name.encode())
    return h.hexdigest()[:12]


_VERSION = _version()

MOODS = ("ecstatic", "happy", "proud", "content", "hello", "curious", "thinking", "worried", "sad", "shocked", "sleepy")

# 헤드라인 판정 → (기분, 말풍선)
VERDICT = {
    "big_beat": ("ecstatic", "어닝 서프라이즈!"),
    "beat": ("happy", "컨센서스 상회!"),
    "inline": ("content", "예상대로예요"),
    "miss": ("worried", "조금 아쉬워요…"),
    "big_miss": ("shocked", "헉, 어닝 쇼크!"),
    "na": ("curious", "컨센서스가 없어요"),
}
# 컨콜 톤 라벨 → 기분
TONE = {"자신감": "proud", "긍정": "happy", "중립": "content", "신중": "worried", "부정": "sad"}

_FALLBACK = ('<div style="width:64px;height:64px;margin:auto;border-radius:50%;'
             'background:radial-gradient(circle at 32% 28%,#F1F2F5,#C5C8D1 50%,#9EA2AE)"></div>')

_TEMPLATE = """<div id="m" style="width:100%;height:{h}px"></div>
<style>html,body{{margin:0;background:transparent;overflow:hidden}}</style>
<script>
(async () => {{
  const el = document.getElementById('m');
  const opts = {opts};
  try {{
    const base = window.parent.location.origin + '/app/static/mascot/';
    if (!window.GaddongMascot) {{
      const res = await fetch(base + 'mascot.bundle.js?v={ver}', {{ cache: 'force-cache' }});
      const s = document.createElement('script');
      s.textContent = await res.text();
      document.head.appendChild(s);
    }}
    await GaddongMascot.boot(el, {{ ...opts, glbUrl: base + 'gaddong.glb?v={ver}' }});
  }} catch (e) {{
    el.innerHTML = opts.fallback;
  }}
}})();
</script>"""


def tone_mood(tone: dict) -> str:
    if not tone:
        return "sleepy"
    if tone.get("label") in TONE:
        return TONE[tone["label"]]
    s = tone.get("score")
    if s is None:
        return "content"
    return "proud" if s > 0.6 else "happy" if s > 0.25 else "content" if s > -0.1 else "worried" if s > -0.45 else "sad"


def render(mood: str, *, height: int = 120, hue: int | None = None, label: str | None = None,
           bubble: bool = True, framing: float = 1.0) -> None:
    """기분(MOODS 중 하나)에 맞춰 움직이는 마스코트를 그린다. 클릭하면 반응하고, 마우스를 따라 본다."""
    opts = {"mood": mood if mood in MOODS else "content", "hue": hue, "label": label, "bubble": bubble,
            "framing": framing, "fallback": _FALLBACK}
    # json.dumps는 '</script>'를 막지 못하므로 '<'를 이스케이프한다(label에 사용자 입력이 들어갈 수 있다)
    payload = json.dumps(opts, ensure_ascii=False).replace("<", "\\u003c")
    components.html(_TEMPLATE.format(h=height, opts=payload, ver=_VERSION), height=height)
