#!/usr/bin/env python3
"""Minimal regression checks for README generation."""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_readme as gen  # noqa: E402


def write_repo(tmp: Path, entries: list[dict], readme: str | None = None) -> Path:
    (tmp / "data").mkdir(parents=True)
    (tmp / "agent").mkdir()
    (tmp / "backend").mkdir()
    (tmp / "assets").mkdir()
    (tmp / "data" / "index.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    if readme is not None:
        (tmp / "README.md").write_text(readme, encoding="utf-8")
    return tmp


def sample_entries() -> list[dict]:
    return [
        {
            "path": "agent/2026-11-12-foo-Agent.md",
            "title": "Foo 面经",
            "url": "https://www.xiaohongshu.com/explore/aaa",
            "folder": "agent",
            "publish_time": "2026-11-12",
        },
        {
            "path": "agent/2026-11-10-bar-Agent.md",
            "title": "Bar 面经",
            "url": "https://www.nowcoder.com/feed/main/detail/bbb",
            "folder": "agent",
            "publish_time": "2026-11-10",
        },
        {
            "path": "backend/2026-11-11-baz-Java.md",
            "title": "Baz 面经",
            "url": "https://www.nowcoder.com/feed/main/detail/ccc",
            "folder": "backend",
            "publish_time": "2026-11-11",
        },
    ]


def row(date: str, title: str, path: str, url: str) -> str:
    return f"| {date} | {title} | [文件]({path}) | [原文]({url}) |"


class StatsTests(unittest.TestCase):
    def test_compute_stats_from_real_index(self):
        entries = gen.load_entries(ROOT / "data" / "index.json")
        stats = gen.compute_stats(entries)
        agent_files = list((ROOT / "agent").glob("*.md"))
        backend_files = list((ROOT / "backend").glob("*.md"))
        self.assertEqual(stats.total, len(entries))
        self.assertEqual(stats.agent, len(agent_files))
        self.assertEqual(stats.backend, len(backend_files))
        self.assertEqual(stats.total, stats.agent + stats.backend)
        self.assertEqual(stats.nowcoder + stats.xiaohongshu + stats.other_sources, stats.total)
        self.assertEqual(stats.date_start_month, "2025-11")
        self.assertEqual(stats.date_end_month, "2026-11")
        self.assertNotIn("未具名公司", stats.top_companies)
        self.assertNotIn("小厂", stats.top_companies)
        self.assertLessEqual(len(stats.top_companies), 15)
        self.assertEqual([name for name, _ in stats.top_company_counts], list(stats.top_companies))
        self.assertTrue(all(count > 0 for _, count in stats.top_company_counts))
        self.assertEqual(sum(count for _, count in stats.monthly_counts), stats.total)
        self.assertEqual([month for month, _ in stats.monthly_counts], sorted(month for month, _ in stats.monthly_counts))
        self.assertTrue(all(role not in gen.ROLE_SKIP for role, _ in stats.top_roles))
        self.assertRegex(stats.generated_on, r"^\d{4}-\d{2}-\d{2}$")


class MergeTests(unittest.TestCase):
    def test_preserves_existing_order_and_raw_lines(self):
        existing = [
            gen.CatalogRow("2026-11-12", "Foo 面经", "agent/2026-11-12-foo-Agent.md", "https://www.xiaohongshu.com/explore/aaa", raw=row("2026-11-12", "Foo 面经", "agent/2026-11-12-foo-Agent.md", "https://www.xiaohongshu.com/explore/aaa")),
            gen.CatalogRow("2026-11-10", "Bar 面经", "agent/2026-11-10-bar-Agent.md", "https://www.nowcoder.com/feed/main/detail/bbb", raw=row("2026-11-10", "Bar 面经", "agent/2026-11-10-bar-Agent.md", "https://www.nowcoder.com/feed/main/detail/bbb")),
        ]
        entries = [gen.Entry(**{**e, "typ": None}) for e in sample_entries() if e["folder"] == "agent"]
        # Entry constructor uses typ=
        entries = [
            gen.Entry(path=e["path"], title=e["title"], url=e["url"], folder=e["folder"], publish_time=e["publish_time"])
            for e in sample_entries()
            if e["folder"] == "agent"
        ]
        merged = gen.merge_catalog(existing, entries, "agent")
        self.assertEqual([r.path for r in merged], [existing[0].path, existing[1].path])
        self.assertEqual(merged[0].raw, existing[0].raw)
        self.assertEqual(merged[1].raw, existing[1].raw)

    def test_inserts_new_entries_by_date_without_reordering_old_ones(self):
        existing = [
            gen.CatalogRow("2026-11-12", "Foo 面经", "agent/2026-11-12-foo-Agent.md", "https://x", raw="OLD-FOO"),
            gen.CatalogRow("2026-11-08", "Old 面经", "agent/2026-11-08-old-Agent.md", "https://x", raw="OLD-08"),
        ]
        entries = [
            gen.Entry("agent/2026-11-12-foo-Agent.md", "Foo 面经", "https://x", "agent", "2026-11-12"),
            gen.Entry("agent/2026-11-08-old-Agent.md", "Old 面经", "https://x", "agent", "2026-11-08"),
            gen.Entry("agent/2026-11-13-new-Agent.md", "New late", "https://x", "agent", "2026-11-13"),
            gen.Entry("agent/2026-11-10-mid-b-Agent.md", "Mid B", "https://x", "agent", "2026-11-10"),
            gen.Entry("agent/2026-11-10-mid-a-Agent.md", "Mid A", "https://x", "agent", "2026-11-10"),
        ]
        merged = gen.merge_catalog(existing, entries, "agent")
        self.assertEqual(
            [r.path for r in merged],
            [
                "agent/2026-11-13-new-Agent.md",
                "agent/2026-11-12-foo-Agent.md",
                "agent/2026-11-10-mid-a-Agent.md",
                "agent/2026-11-10-mid-b-Agent.md",
                "agent/2026-11-08-old-Agent.md",
            ],
        )
        self.assertEqual(merged[1].raw, "OLD-FOO")
        self.assertEqual(merged[-1].raw, "OLD-08")



    def test_render_catalog_folds_rows_after_recent_window(self):
        rows = [
            gen.CatalogRow(f"2026-11-{(30-i):02d}", f"T{i}", f"agent/2026-11-{(30-i):02d}-c.md", f"https://x/{i}")
            for i in range(32)
        ]
        block = gen.render_catalog_block("agent", rows, recent_n=30)
        self.assertIn("<!-- catalog:agent:start -->", block)
        self.assertIn("<!-- catalog:agent:end -->", block)
        self.assertIn("<details>", block)
        self.assertIn("<summary>更早的 2 篇</summary>", block)
        self.assertIn("</details>", block)
        # Recent rows appear before the fold; older rows only after <details>.
        pre, post = block.split("<details>", 1)
        self.assertIn("T0", pre)
        self.assertIn("T29", pre)
        self.assertNotIn("T30", pre)
        self.assertNotIn("T31", pre)
        self.assertIn("T30", post)
        self.assertIn("T31", post)
        parsed = gen.parse_catalog_rows(block, "agent")
        self.assertEqual([r.path for r in parsed], [r.path for r in rows])


class GenerateRepoTests(unittest.TestCase):
    def test_generate_is_idempotent_and_keeps_current_catalog(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        catalogs = gen.extract_existing_catalogs(text)
        entries = gen.load_entries(ROOT / "data" / "index.json")
        agent_n = sum(1 for e in entries if e.folder == "agent")
        backend_n = sum(1 for e in entries if e.folder == "backend")
        self.assertEqual(len(catalogs["agent"]), agent_n)
        self.assertEqual(len(catalogs["backend"]), backend_n)
        self.assertEqual(agent_n, len(list((ROOT / "agent").glob("*.md"))))
        self.assertEqual(backend_n, len(list((ROOT / "backend").glob("*.md"))))

        # All index paths appear exactly once, with matching fields.
        by_path = {e.path: e for e in entries}
        seen = set()
        for folder, rows in catalogs.items():
            for row in rows:
                self.assertIn(row.path, by_path)
                entry = by_path[row.path]
                self.assertEqual(row.date, entry.date)
                self.assertEqual(row.title, entry.title)
                self.assertEqual(row.url, entry.url)
                self.assertEqual(entry.folder, folder)
                self.assertNotIn(row.path, seen)
                seen.add(row.path)
        self.assertEqual(seen, set(by_path))

        # File links resolve.
        for path in seen:
            self.assertTrue((ROOT / path).is_file(), path)

        # Anchors used in the preamble exist as headings.
        headings = [line[2:].strip() if line.startswith("# ") else line[3:].strip() if line.startswith("## ") else line[4:].strip() for line in text.splitlines() if line.startswith("#")]
        def slug(title: str) -> str:
            # GitHub: strip punctuation, then replace each whitespace with '-'.
            punct = set("'" + '"!#$%&()*+,./:;<=>?@[]^`{|}\\~')
            s = title.strip().lower()
            s = "".join(ch for ch in s if ch not in punct)
            s = s.replace(" ", "-")
            return s

        for href in re.findall(r"\]\(#([^)]+)\)", text.split("## 索引", 1)[0]):
            self.assertIn(href, {slug(h) for h in headings}, href)

        first = text
        first_png = (ROOT / "assets" / "header.png").read_bytes()
        gen.generate(ROOT)
        self.assertEqual((ROOT / "README.md").read_text(encoding="utf-8"), first)
        self.assertEqual((ROOT / "assets" / "header.png").read_bytes(), first_png)

    def test_generate_on_fixture_repo_writes_header_and_stats(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            entries = sample_entries()
            write_repo(
                tmp,
                entries,
                readme="# old\n\n### Agent / 大模型应用开发\n\n| 发帖日期 | 标题 | 文件 | 原文 |\n| --- | --- | --- | --- |\n"
                + row("2026-11-12", "Foo 面经", "agent/2026-11-12-foo-Agent.md", "https://www.xiaohongshu.com/explore/aaa")
                + "\n"
                + row("2026-11-10", "Bar 面经", "agent/2026-11-10-bar-Agent.md", "https://www.nowcoder.com/feed/main/detail/bbb")
                + "\n",
            )
            # backend table missing on purpose; generator should still add from index
            summary = gen.generate(tmp)
            self.assertEqual(summary["total"], 3)
            self.assertEqual(summary["agent"], 2)
            self.assertEqual(summary["backend"], 1)
            readme = (tmp / "README.md").read_text(encoding="utf-8")
            self.assertIn("3 篇", readme)
            self.assertIn("牛客 2", readme)
            self.assertIn("小红书 1", readme)
            self.assertIn("assets/header.png", readme)
            self.assertIn("## 如何使用", readme)
            self.assertIn("## 版权", readme)
            self.assertIn("## 亮点", readme)
            self.assertIn("## Star History", readme)
            self.assertIn("img.shields.io", readme)
            self.assertIn("star-history.com", readme)
            self.assertIn("面向准备 Agent、大模型应用和后端秋招、实习的同学", readme)
            self.assertNotIn("<style", readme.lower())
            self.assertTrue((tmp / "assets" / "header.png").is_file())
            self.assertGreater((tmp / "assets" / "header.png").stat().st_size, 1000)
            self.assertIn("<!-- catalog:agent:start -->", readme)
            self.assertIn("backend/2026-11-11-baz-Java.md", readme)
            # Small catalogs stay unfolded.
            agent_body = readme.split("<!-- catalog:agent:start -->", 1)[1].split("<!-- catalog:agent:end -->", 1)[0]
            self.assertNotIn("<details>", agent_body)
            # old rows kept verbatim
            self.assertIn(row("2026-11-12", "Foo 面经", "agent/2026-11-12-foo-Agent.md", "https://www.xiaohongshu.com/explore/aaa"), readme)


if __name__ == "__main__":
    unittest.main()
