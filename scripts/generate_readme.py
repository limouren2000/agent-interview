#!/usr/bin/env python3
"""Regenerate README.md hero stats and catalog tables from data/index.json.

The designed preamble (hero image, navigation, usage, copyright) is kept in
this script so later collection runs do not fall back to the old plain header.
Existing catalog rows are preserved in place and only updated when index
fields change; new index entries are inserted in date-descending order.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "data" / "index.json"
README_PATH = ROOT / "README.md"
HEADER_PATH = ROOT / "assets" / "header.png"

MARKER = {
    "agent": ("<!-- catalog:agent:start -->", "<!-- catalog:agent:end -->"),
    "backend": ("<!-- catalog:backend:start -->", "<!-- catalog:backend:end -->"),
}

FOLDER_HEADING = {
    "agent": "### Agent / 大模型应用开发",
    "backend": "### 后端开发",
}

TABLE_HEADER = "| 发帖日期 | 标题 | 文件 | 原文 |\n| --- | --- | --- | --- |"

ROW_RE = re.compile(
    r"^\| (?P<date>[^|]+) \| (?P<title>.*) \| \[文件\]\((?P<path>[^)]+)\) \| \[原文\]\((?P<url>[^)]+)\) \|$"
)

GENERIC_COMPANIES = {
    "小厂",
    "未具名公司",
    "未注明公司",
    "某小公司",
    "某厂",
    "未知",
}

FONT_CJK_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_CJK_REGULAR = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_GEIST_MONO = "/usr/share/fonts/truetype/sand-box/google/Geist Mono/GeistMono-VariableFont_wght.ttf"
FONT_GEIST = "/usr/share/fonts/truetype/sand-box/google/Geist/Geist-VariableFont_wght.ttf"
FONT_INTER = "/usr/share/fonts/truetype/sand-box/google/Inter/Inter-VariableFont_opsz,wght.ttf"

# Noto Sans CJK SC is face index 2 in the Debian TTC packages.
CJK_SC_INDEX = 2


@dataclass(frozen=True)
class Entry:
    path: str
    title: str
    url: str
    folder: str
    publish_time: str
    typ: str | None = None

    @property
    def date(self) -> str:
        return str(self.publish_time)[:10]

    @property
    def source(self) -> str:
        host = urlparse(self.url).netloc.lower()
        if "xiaohongshu" in host or host.endswith("xhslink.com"):
            return "xiaohongshu"
        if "nowcoder" in host:
            return "nowcoder"
        return host or "unknown"


@dataclass
class CatalogRow:
    date: str
    title: str
    path: str
    url: str
    raw: str | None = None

    def render(self) -> str:
        if self.raw is not None:
            return self.raw
        title = self.title.replace("|", "\\|")
        return f"| {self.date} | {title} | [文件]({self.path}) | [原文]({self.url}) |"


@dataclass(frozen=True)
class Stats:
    total: int
    agent: int
    backend: int
    nowcoder: int
    xiaohongshu: int
    other_sources: int
    date_start: str
    date_end: str
    date_start_month: str
    date_end_month: str
    top_companies: tuple[str, ...]


def load_entries(index_path: Path = INDEX_PATH) -> list[Entry]:
    data = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("data/index.json must be a list")
    entries: list[Entry] = []
    for item in data:
        entries.append(
            Entry(
                path=item["path"],
                title=item["title"],
                url=item["url"],
                folder=item["folder"],
                publish_time=item["publish_time"],
                typ=item.get("type"),
            )
        )
    return entries


def company_from_path(path: str) -> str:
    name = Path(path).stem
    parts = name.split("-")
    if len(parts) >= 4 and re.match(r"\d{4}$", parts[0]) and re.match(r"\d{2}$", parts[1]) and re.match(r"\d{2}$", parts[2]):
        return parts[3]
    return "未知"


def compute_stats(entries: Iterable[Entry], company_limit: int = 12) -> Stats:
    entries = list(entries)
    if not entries:
        raise ValueError("index is empty")
    folders = Counter(e.folder for e in entries)
    sources = Counter(e.source for e in entries)
    dates = [e.date for e in entries]
    date_start, date_end = min(dates), max(dates)
    companies = Counter(
        company_from_path(e.path)
        for e in entries
        if company_from_path(e.path) not in GENERIC_COMPANIES
    )
    top = tuple(name for name, _ in companies.most_common(company_limit))
    other = sum(v for k, v in sources.items() if k not in {"nowcoder", "xiaohongshu"})
    return Stats(
        total=len(entries),
        agent=folders.get("agent", 0),
        backend=folders.get("backend", 0),
        nowcoder=sources.get("nowcoder", 0),
        xiaohongshu=sources.get("xiaohongshu", 0),
        other_sources=other,
        date_start=date_start,
        date_end=date_end,
        date_start_month=date_start[:7],
        date_end_month=date_end[:7],
        top_companies=top,
    )


def format_month_range(start_month: str, end_month: str) -> str:
    def pretty(month: str) -> str:
        year, mon = month.split("-")
        return f"{year}.{mon}"

    if start_month == end_month:
        return pretty(start_month)
    return f"{pretty(start_month)}–{pretty(end_month)}"


def _var_font(path: str, size: int, weight: int, opsz: int | None = None) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(path, size=size)
    axes = {item["name"]: item for item in font.get_variation_axes()}
    values = []
    if "opsz" in axes:
        values.append(float(opsz if opsz is not None else size))
    if "wght" in axes:
        values.append(float(weight))
    if values:
        font.set_variation_by_axes(values)
    return font


def _cjk_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size=size, index=CJK_SC_INDEX)


def _draw_text_spaced(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, ...],
    spacing: float,
) -> float:
    x, y = xy
    for i, ch in enumerate(text):
        draw.text((x, y), ch, font=font, fill=fill)
        box = draw.textbbox((x, y), ch, font=font)
        x = box[2] + (spacing if i < len(text) - 1 else 0)
    return x


def _rounded_rect(
    draw: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float],
    radius: int,
    fill: tuple[int, ...] | None = None,
    outline: tuple[int, ...] | None = None,
    width: int = 2,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def render_header(stats: Stats, dest: Path = HEADER_PATH) -> Path:
    width, height = 2400, 640
    bg = (7, 11, 20, 255)
    ink = (244, 247, 251, 255)
    muted = (168, 180, 198, 255)
    faint = (26, 36, 54, 255)
    accent = (124, 156, 255, 255)
    mint = (62, 224, 197, 255)
    pill_bg = (18, 26, 40, 255)
    pill_border = (42, 53, 72, 255)
    pill_label = (139, 150, 168, 255)
    accent_pill_border = (90, 122, 214, 255)

    base = Image.new("RGBA", (width, height), bg)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)

    # Soft typographic glow behind the title, not an illustration.
    gdraw.ellipse((980, -80, 1880, 620), fill=(70, 96, 190, 70))
    gdraw.ellipse((1600, 80, 2500, 780), fill=(28, 120, 130, 40))
    glow = glow.filter(ImageFilter.GaussianBlur(80))
    base = Image.alpha_composite(base, glow)

    draw = ImageDraw.Draw(base)

    # Fine grid
    for x in range(0, width, 80):
        draw.line((x, 0, x, height), fill=faint, width=1)
    for y in range(0, height, 80):
        draw.line((0, y, width, y), fill=faint, width=1)

    # Top accent bar
    for i in range(width):
        t = i / (width - 1)
        r = int(124 * (1 - t) + 62 * t)
        g = int(156 * (1 - t) + 224 * t)
        b = int(255 * (1 - t) + 197 * t)
        draw.line((i, 0, i, 8), fill=(r, g, b, 255))

    # Left accent spine
    for y in range(height):
        t = y / (height - 1)
        r = int(124 * (1 - t) + 62 * t)
        g = int(156 * (1 - t) + 224 * t)
        b = int(255 * (1 - t) + 197 * t)
        draw.line((0, y, 8, y), fill=(r, g, b, 255))

    kicker_font = _var_font(FONT_GEIST_MONO, 28, weight=500)
    title_font = _cjk_font(FONT_CJK_BOLD, 92)
    subtitle_font = _cjk_font(FONT_CJK_REGULAR, 34)
    pill_label_font = _cjk_font(FONT_CJK_REGULAR, 28)
    pill_value_font = _var_font(FONT_GEIST, 36, weight=650)
    # Geist may not cover CJK; values are numeric / latin. Labels use CJK font.

    pad_x = 96
    y = 70
    kicker = "AGENT  /  RAG  /  BACKEND  /  INTERVIEW NOTES"
    _draw_text_spaced(draw, (pad_x, y), kicker, kicker_font, accent, spacing=6)

    title = "Agent / 后端面经合集"
    draw.text((pad_x, 150), title, font=title_font, fill=ink)

    subtitle = "公开整理的 Agent 开发、大模型应用与后端开发面经"
    draw.text((pad_x, 286), subtitle, font=subtitle_font, fill=muted)

    pills = [
        ("收录", f"{stats.total}", True),
        ("Agent", f"{stats.agent}", False),
        ("后端", f"{stats.backend}", False),
        ("牛客", f"{stats.nowcoder}", False),
        ("小红书", f"{stats.xiaohongshu}", False),
        ("跨度", format_month_range(stats.date_start_month, stats.date_end_month), False),
    ]

    x = pad_x
    pill_y = 400
    pill_h = 92
    inner_pad = 28
    gap = 18
    for label, value, featured in pills:
        label_box = draw.textbbox((0, 0), label, font=pill_label_font)
        value_box = draw.textbbox((0, 0), value, font=pill_value_font)
        label_w = label_box[2] - label_box[0]
        value_w = value_box[2] - value_box[0]
        w = inner_pad + label_w + 16 + value_w + inner_pad
        box = (x, pill_y, x + w, pill_y + pill_h)
        _rounded_rect(
            draw,
            box,
            radius=20,
            fill=pill_bg,
            outline=accent_pill_border if featured else pill_border,
            width=3 if featured else 2,
        )
        text_y_label = pill_y + (pill_h - (label_box[3] - label_box[1])) / 2 - label_box[1]
        text_y_value = pill_y + (pill_h - (value_box[3] - value_box[1])) / 2 - value_box[1]
        lx = x + inner_pad
        draw.text((lx, text_y_label), label, font=pill_label_font, fill=pill_label)
        vx = lx + label_w + 16
        draw.text((vx, text_y_value), value, font=pill_value_font, fill=ink if not featured else accent)
        x += w + gap

    dest.parent.mkdir(parents=True, exist_ok=True)
    rgb = base.convert("RGB")
    rgb.save(dest, format="PNG", optimize=True)
    return dest


def parse_catalog_rows(text: str, folder: str) -> list[CatalogRow]:
    rows: list[CatalogRow] = []
    for line in text.splitlines():
        if not line.startswith("| "):
            continue
        if line.startswith("| 发帖日期") or line.startswith("| ---"):
            continue
        match = ROW_RE.match(line)
        if not match:
            raise ValueError(f"unrecognized catalog row in {folder}: {line}")
        rows.append(
            CatalogRow(
                date=match.group("date").strip(),
                title=match.group("title"),
                path=match.group("path"),
                url=match.group("url"),
                raw=line,
            )
        )
    return rows


def extract_existing_catalogs(readme_text: str) -> dict[str, list[CatalogRow]]:
    catalogs: dict[str, list[CatalogRow]] = {}
    for folder, (start, end) in MARKER.items():
        if start in readme_text and end in readme_text:
            body = readme_text.split(start, 1)[1].split(end, 1)[0]
            catalogs[folder] = parse_catalog_rows(body, folder)
            continue
        heading = FOLDER_HEADING[folder]
        if heading not in readme_text:
            catalogs[folder] = []
            continue
        after = readme_text.split(heading, 1)[1]
        # Stop at the next heading or EOF.
        cut = re.split(r"\n##+ ", after, maxsplit=1)[0]
        catalogs[folder] = parse_catalog_rows(cut, folder)
    return catalogs


def merge_catalog(existing: list[CatalogRow], entries: list[Entry], folder: str) -> list[CatalogRow]:
    folder_entries = [e for e in entries if e.folder == folder]
    by_path = {e.path: e for e in folder_entries}
    used: set[str] = set()
    merged: list[CatalogRow] = []

    for row in existing:
        entry = by_path.get(row.path)
        if entry is None:
            # Keep a row that is still in the README even if temporarily
            # missing from the index, to avoid accidental catalog loss.
            merged.append(row)
            continue
        used.add(row.path)
        if row.date == entry.date and row.title == entry.title and row.url == entry.url:
            merged.append(row)
        else:
            merged.append(
                CatalogRow(
                    date=entry.date,
                    title=entry.title,
                    path=entry.path,
                    url=entry.url,
                    raw=None,
                )
            )

    new_entries = [e for e in folder_entries if e.path not in used]
    # Oldest new entries first, so later (newer) inserts land above them.
    # Same-date items are appended at the end of that date group, sorted by path.
    for entry in sorted(new_entries, key=lambda e: (e.date, e.path)):
        new_row = CatalogRow(
            date=entry.date,
            title=entry.title,
            path=entry.path,
            url=entry.url,
            raw=None,
        )
        insert_at = len(merged)
        for i, row in enumerate(merged):
            if row.date < entry.date:
                insert_at = i
                break
        merged.insert(insert_at, new_row)
    return merged


def render_catalog_block(folder: str, rows: list[CatalogRow]) -> str:
    start, end = MARKER[folder]
    lines = [FOLDER_HEADING[folder], "", start, TABLE_HEADER]
    lines.extend(row.render() for row in rows)
    lines.append(end)
    return "\n".join(lines)


def render_company_tags(stats: Stats) -> str:
    if not stats.top_companies:
        return ""
    tags = " ".join(f"`{name}`" for name in stats.top_companies)
    return f"文件名中较常见的公司（不完全统计，不含未具名条目）：{tags}"


def render_source_cell(stats: Stats) -> str:
    parts = [f"牛客 {stats.nowcoder}", f"小红书 {stats.xiaohongshu}"]
    if stats.other_sources:
        parts.append(f"其他 {stats.other_sources}")
    return " · ".join(parts)


def render_readme(stats: Stats, catalogs: dict[str, list[CatalogRow]]) -> str:
    company_line = render_company_tags(stats)
    company_block = f"\n{company_line}\n" if company_line else "\n"
    source_cell = render_source_cell(stats)
    span = format_month_range(stats.date_start_month, stats.date_end_month)

    preamble = f"""<div align="center">

<img src="assets/header.png" alt="Agent / 后端面经合集" width="100%">

公开整理的 Agent 开发、大模型应用与后端开发面经。每篇分三部分：一行基本信息、速览、面经正文（原文只整理格式，不改内容）。

`Agent` · `RAG` · `大模型应用` · `后端` · `校招` · `实习` · `社招`

[如何使用](#如何使用) · [仓库统计](#仓库统计) · [目录](#目录) · [Agent 索引](#agent--大模型应用开发) · [后端索引](#后端开发) · [版权](#版权)

</div>

## 如何使用

- 从下方[索引](#索引)按发帖日期浏览，或直接打开目录里的 Markdown 文件。
- 每篇开头是基本信息（公司、岗位、轮次、来源链接），接着是速览，再是按原文顺序整理的面经正文。
- 检索和去重可看 [`data/index.json`](data/index.json)。
- 纠错、补充或侵权删除请开 Issue。

## 仓库统计

| 收录 | Agent / 大模型应用 | 后端 | 来源 | 发帖跨度 |
| --- | --- | --- | --- | --- |
| {stats.total} 篇 | {stats.agent} | {stats.backend} | {source_cell} | {span} |

统计与 [`data/index.json`](data/index.json) 及 `agent/`、`backend/` 目录文件一致，随收录更新。本仓库整理已公开的帖子，不声称对每篇都做了独立真伪核验。
{company_block}
## 目录

- [`agent/`](agent/)：Agent / 大模型应用开发（[索引](#agent--大模型应用开发)）
- [`backend/`](backend/)：后端开发（[索引](#后端开发)）
- [`data/index.json`](data/index.json)：索引与去重用

## 索引

{render_catalog_block("agent", catalogs["agent"])}

{render_catalog_block("backend", catalogs["backend"])}

## 更新说明

工作日会收集新面经并更新本仓库。欢迎 Issue 反馈纠错或侵权删除。

新增条目请先写入对应目录和 `data/index.json`，再运行：

```bash
python3 scripts/generate_readme.py
```

脚本会按索引刷新页首统计和头图，并在不打乱既有顺序的前提下把新条目插入索引表。

## 版权

面经版权归原作者所有。本仓库仅做公开帖子的整理归档，如有侵权请提 Issue，确认后删除。
"""
    return preamble.strip() + "\n"


def generate(root: Path = ROOT) -> dict[str, int]:
    index_path = root / "data" / "index.json"
    readme_path = root / "README.md"
    header_path = root / "assets" / "header.png"

    entries = load_entries(index_path)
    stats = compute_stats(entries)
    existing = extract_existing_catalogs(readme_path.read_text(encoding="utf-8")) if readme_path.exists() else {"agent": [], "backend": []}
    catalogs = {
        "agent": merge_catalog(existing.get("agent", []), entries, "agent"),
        "backend": merge_catalog(existing.get("backend", []), entries, "backend"),
    }
    render_header(stats, header_path)
    readme_path.write_text(render_readme(stats, catalogs), encoding="utf-8")
    return {
        "total": stats.total,
        "agent": stats.agent,
        "backend": stats.backend,
        "nowcoder": stats.nowcoder,
        "xiaohongshu": stats.xiaohongshu,
        "agent_rows": len(catalogs["agent"]),
        "backend_rows": len(catalogs["backend"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regenerate README and header art from data/index.json")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    args = parser.parse_args(argv)
    summary = generate(args.root.resolve())
    print(
        f"README updated: {summary['total']} 篇 "
        f"(agent {summary['agent']}/backend {summary['backend']}; "
        f"nowcoder {summary['nowcoder']}/xiaohongshu {summary['xiaohongshu']})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
