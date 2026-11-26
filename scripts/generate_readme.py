#!/usr/bin/env python3
"""Regenerate README.md hero stats and catalog tables from data/index.json.

The designed preamble (hero image, badges, navigation, usage, copyright) is
kept in this script so later collection runs do not fall back to a plain
header. Existing catalog rows are preserved in place and only updated when
index fields change; new index entries are inserted in date-descending order.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "data" / "index.json"
README_PATH = ROOT / "README.md"
HEADER_PATH = ROOT / "assets" / "header.png"

REPO_SLUG = "limouren2000/agent-interview"
STAR_HISTORY_CACHE = "20261125"
SHANGHAI = ZoneInfo("Asia/Shanghai")

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

# Path segments that are rounds or recruitment types, not a job title.
ROLE_SKIP = {
    "局部",
    "一面",
    "二面",
    "三面",
    "四面",
    "五面",
    "HR面",
    "HRBP面",
    "HRBP",
    "HR",
    "一面二面",
    "一面二面三面",
    "一面二面HRBP面",
    "第一轮",
    "第二轮",
    "第三轮",
    "一二面",
    "二三面",
    "二面三面",
    "实习",
    "日常实习",
    "秋招",
    "校招",
    "社招",
    "暑期实习",
    "转正",
    "提前批",
    "春招",
    "AI面",
}

CATALOG_RECENT = 30
LATEST_N = 10
BAR_WIDTH = 20

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
    top_company_counts: tuple[tuple[str, int], ...]
    monthly_counts: tuple[tuple[str, int], ...]
    top_roles: tuple[tuple[str, int], ...]
    type_counts: tuple[tuple[str, int], ...]
    generated_on: str


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


def role_from_path(path: str) -> str | None:
    name = Path(path).stem
    parts = name.split("-")
    if len(parts) >= 5 and re.match(r"\d{4}$", parts[0]) and re.match(r"\d{2}$", parts[1]) and re.match(r"\d{2}$", parts[2]):
        role = parts[4]
        if role and role not in GENERIC_COMPANIES and role not in ROLE_SKIP:
            return role
    return None


def today_shanghai(now: datetime | None = None) -> str:
    current = now or datetime.now(SHANGHAI)
    if current.tzinfo is None:
        current = current.replace(tzinfo=SHANGHAI)
    return current.astimezone(SHANGHAI).date().isoformat()


def compute_stats(
    entries: Iterable[Entry],
    company_limit: int = 15,
    role_limit: int = 15,
    now: datetime | None = None,
) -> Stats:
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
    top_counts = tuple(companies.most_common(company_limit))
    top = tuple(name for name, _ in top_counts)
    roles = Counter(role for e in entries if (role := role_from_path(e.path)))
    types = Counter(e.typ for e in entries if e.typ)
    months = Counter(str(e.publish_time)[:7] for e in entries)
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
        top_company_counts=top_counts,
        monthly_counts=tuple(sorted(months.items())),
        top_roles=tuple(roles.most_common(role_limit)),
        type_counts=tuple(types.most_common()),
        generated_on=today_shanghai(now),
    )


def format_month_range(start_month: str, end_month: str) -> str:
    def pretty(month: str) -> str:
        year, mon = month.split("-")
        return f"{year}.{mon}"

    if start_month == end_month:
        return pretty(start_month)
    return f"{pretty(start_month)}–{pretty(end_month)}"


def format_date_range(start: str, end: str) -> str:
    """Full publish-date span from index (YYYY-MM-DD, or month-only if that is all the index has)."""
    if start == end:
        return start
    return f"{start} 至 {end}"


def latest_entries(entries: Iterable[Entry], n: int = LATEST_N) -> list[Entry]:
    items = list(entries)
    return sorted(items, key=lambda e: e.date, reverse=True)[:n]


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


def render_catalog_block(folder: str, rows: list[CatalogRow], recent_n: int = CATALOG_RECENT) -> str:
    start, end = MARKER[folder]
    recent = rows[:recent_n]
    older = rows[recent_n:]
    lines = [FOLDER_HEADING[folder], "", start, TABLE_HEADER]
    lines.extend(row.render() for row in recent)
    if older:
        lines.append("")
        lines.append("<details>")
        lines.append(f"<summary>更早的 {len(older)} 篇</summary>")
        lines.append("")
        lines.append(TABLE_HEADER)
        lines.extend(row.render() for row in older)
        lines.append("")
        lines.append("</details>")
    lines.append(end)
    return "\n".join(lines)


def render_source_cell(stats: Stats) -> str:
    parts = [f"牛客 {stats.nowcoder}", f"小红书 {stats.xiaohongshu}"]
    if stats.other_sources:
        parts.append(f"其他 {stats.other_sources}")
    return " · ".join(parts)


def _bar(count: int, max_count: int, width: int = BAR_WIDTH) -> str:
    if max_count <= 0 or count <= 0:
        return ""
    filled = max(1, round(count / max_count * width))
    return "█" * filled


def render_count_table(rows: list[tuple[str, int]], total: int, name_header: str) -> str:
    if not rows:
        return ""
    max_count = max(count for _, count in rows)
    lines = [
        f"| 排名 | {name_header} | 篇数 | 占比 | 分布 |",
        "| ---: | --- | ---: | ---: | --- |",
    ]
    for i, (name, count) in enumerate(rows, 1):
        share = f"{count / total * 100:.1f}%" if total else "—"
        lines.append(f"| {i} | {name} | {count} | {share} | {_bar(count, max_count)} |")
    return "\n".join(lines)


def render_month_table(rows: tuple[tuple[str, int], ...], total: int) -> str:
    if not rows:
        return ""
    max_count = max(count for _, count in rows)
    lines = [
        "| 月份 | 篇数 | 占比 | 分布 |",
        "| --- | ---: | ---: | --- |",
    ]
    for month, count in rows:
        share = f"{count / total * 100:.1f}%" if total else "—"
        lines.append(f"| {month} | {count} | {share} | {_bar(count, max_count)} |")
    return "\n".join(lines)


def shields_static(label: str, message: str, color: str, style: str = "for-the-badge") -> str:
    return (
        "https://img.shields.io/static/v1?"
        f"label={quote(label)}&message={quote(message)}&color={color}&style={style}"
    )


def render_badges(stats: Stats) -> str:
    source_msg = f"牛客 {stats.nowcoder} · 小红书 {stats.xiaohongshu}"
    if stats.other_sources:
        source_msg += f" · 其他 {stats.other_sources}"
    items = [
        (f"收录 {stats.total} 篇", shields_static("收录", f"{stats.total} 篇", "7C9CFF")),
        (f"Agent {stats.agent}", shields_static("Agent", str(stats.agent), "3EE0C5")),
        (f"后端 {stats.backend}", shields_static("后端", str(stats.backend), "8BA4C8")),
        (f"来源 {source_msg}", shields_static("来源", source_msg, "5B7CFA")),
        (f"更新 {stats.generated_on}", shields_static("更新", stats.generated_on, "3D4F6F")),
    ]
    imgs = "\n".join(f'<img src="{url}" alt="{alt}">' for alt, url in items)
    stars = (
        f'<a href="https://github.com/{REPO_SLUG}/stargazers">'
        f'<img src="https://img.shields.io/github/stars/{REPO_SLUG}?style=for-the-badge" alt="GitHub stars"></a>'
    )
    license_badge = (
        '<a href="#版权">'
        f'<img src="{shields_static("copyright", "原作者所有", "6B7280")}" alt="版权归原作者"></a>'
    )
    return f"{imgs}\n{stars}\n{license_badge}"


def render_role_tags(stats: Stats) -> str:
    if not stats.top_roles:
        return ""
    tags = " ".join(f"`{name}` {count}" for name, count in stats.top_roles)
    return (
        "从文件名里统计到的常见岗位（取公司名后的岗位字段，按出现次数；"
        f"不含轮次、招聘类型和未具名条目）：{tags}"
    )


def render_type_tags(stats: Stats) -> str:
    if not stats.type_counts:
        return ""
    tagged = sum(count for _, count in stats.type_counts)
    tags = " ".join(f"`{name}` {count}" for name, count in stats.type_counts)
    return f"index 里已填写招聘类型的 {tagged} 篇（其余未填，不补推）：{tags}"


FOLDER_SHORT = {
    "agent": "Agent",
    "backend": "后端",
}


def render_latest_block(entries: Iterable[Entry], n: int = LATEST_N) -> str:
    rows = latest_entries(entries, n)
    if not rows:
        return ""
    shown = len(rows)
    if shown < n:
        intro = f"按发帖日期从新到旧排列。当前共 {shown} 篇，全部列出。完整列表见下方[索引](#索引)。"
    else:
        intro = f"按发帖日期从新到旧，列出最近 {n} 篇。完整列表见下方[索引](#索引)。"
    lines = [
        "| 发帖日期 | 标题 | 分类 | 文件 | 原文 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for e in rows:
        folder = FOLDER_SHORT.get(e.folder, e.folder)
        lines.append(f"| {e.date} | {e.title} | {folder} | [文件]({e.path}) | [原文]({e.url}) |")
    return f"{intro}\n\n" + "\n".join(lines)


def render_star_history_embed(slug: str, alt: str = "Star History Chart") -> str:
    light = f"https://api.star-history.com/svg?repos={slug}&type=Date&v={STAR_HISTORY_CACHE}"
    dark = f"https://api.star-history.com/svg?repos={slug}&type=Date&theme=dark&v={STAR_HISTORY_CACHE}"
    page = f"https://star-history.com/#{slug}&Date"
    return (
        f'<a href="{page}">\n'
        f'  <picture>\n'
        f'    <source media="(prefers-color-scheme: dark)" srcset="{dark}">\n'
        f'    <source media="(prefers-color-scheme: light)" srcset="{light}">\n'
        f'    <img alt="{alt}" src="{light}">\n'
        f'  </picture>\n'
        f'</a>'
    )


def render_readme(stats: Stats, catalogs: dict[str, list[CatalogRow]], entries: Iterable[Entry] | None = None) -> str:
    source_cell = render_source_cell(stats)
    span = format_date_range(stats.date_start, stats.date_end)
    latest = list(entries) if entries is not None else []
    latest_block = render_latest_block(latest, LATEST_N)
    badges = render_badges(stats)
    company_table = render_count_table(list(stats.top_company_counts), stats.total, "公司")
    month_table = render_month_table(stats.monthly_counts, stats.total)
    role_line = render_role_tags(stats)
    type_line = render_type_tags(stats)
    company_block = f"\n{company_table}\n" if company_table else "\n"
    role_block = f"{role_line}\n\n" if role_line else ""
    type_block = f"{type_line}\n" if type_line else ""

    preamble = f"""<div align="center">

<img src="assets/header.png" alt="Agent / 后端面经合集" width="100%">

> 面向准备 Agent、大模型应用和后端秋招、实习的同学，把已经公开的面经按公司、岗位和日期整理在一起。
>
> 🔥 **持续更新：已收录至 {stats.date_end} 的最新面经**

{badges}

[如何使用](#如何使用) · [交流群](#交流群) · [亮点](#亮点) · [最新收录](#最新收录) · [仓库统计](#仓库统计) · [目录](#目录) · [Agent 索引](#agent--大模型应用开发) · [后端索引](#后端开发) · [Star History](#star-history) · [版权](#版权)

</div>

如果这份面经合集对你有帮助，欢迎点个 Star。也欢迎转发给正在准备的同学，让更多人看到。

## 如何使用

- 从下方[索引](#索引)按发帖日期浏览，或直接打开目录里的 Markdown 文件。最近 30 篇默认展开，更早的条目折叠在索引里。
- 每篇开头是基本信息（公司、岗位、轮次、来源链接），接着是速览，再是按原文顺序整理的面经正文。原文只整理格式，不改内容。
- 检索和去重可看 [`data/index.json`](data/index.json)。
- 纠错、补充或侵权删除请开 Issue。

## 交流群

欢迎加入微信群「Agent 面经共创小分队」，也欢迎大家进群讨论和交流。下方二维码有效期至 2026-12-03，过期后请换用新码。

<p align="center">
  <img src="assets/wechat-group-qr.jpg" alt="Agent 面经共创小分队 微信群二维码" width="280">
</p>

## 亮点

- 📚 **{stats.total} 篇**公开面经，一篇一个文件，按发帖日期排列
- 🧭 分成 **Agent / 大模型应用（{stats.agent}）** 和 **后端（{stats.backend}）** 两个目录
- 🔗 来源以 **牛客 {stats.nowcoder}**、**小红书 {stats.xiaohongshu}** 为主
- 🗓️ 发帖跨度 **{span}**，统计随收录更新
- 🗂️ 每篇含一行基本信息、速览，以及按原文顺序整理的正文
- ⚠️ 本仓库整理已公开的帖子，不声称对每篇都做了独立真伪核验

## 最新收录

{latest_block}

## 仓库统计

| 收录 | Agent / 大模型应用 | 后端 | 来源 | 发帖跨度 |
| --- | --- | --- | --- | --- |
| {stats.total} 篇 | {stats.agent} | {stats.backend} | {source_cell} | {span} |

统计与 [`data/index.json`](data/index.json) 及 `agent/`、`backend/` 目录文件一致，随收录更新。公司、岗位和月份分布都从文件名或索引字段计算，不含未具名条目，也不另外编造考点标签。

### 热门公司 Top 15

按文件名中的公司字段统计，不含「未具名公司」「小厂」等泛称。占比按全部 {stats.total} 篇计算。
{company_block}
### 按月收录

按面经的发帖年月统计（与索引里的 `publish_time` 一致）。

{month_table}

### 常见岗位

{role_block}{type_block}
## 目录

- [`agent/`](agent/)：Agent / 大模型应用开发（[索引](#agent--大模型应用开发)）
- [`backend/`](backend/)：后端开发（[索引](#后端开发)）
- [`data/index.json`](data/index.json)：索引与去重用

## 索引

{render_catalog_block("agent", catalogs["agent"])}

{render_catalog_block("backend", catalogs["backend"])}

## 更新说明

本仓库按发帖日期持续收录，已覆盖至索引中的最新日期（当前为 {stats.date_end}）。工作日会收集新面经并更新本仓库。欢迎 Issue 反馈纠错、补充或侵权删除。

新增条目请先写入对应目录和 `data/index.json`，再运行：

```bash
python3 scripts/generate_readme.py
```

脚本会按索引刷新页首统计和头图，并在不打乱既有顺序的前提下把新条目插入索引表。

## Star History

{render_star_history_embed(REPO_SLUG, "Star History Chart")}

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
    readme_path.write_text(render_readme(stats, catalogs, entries), encoding="utf-8")
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
