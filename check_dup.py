"""
分析 mktsource.fetch_news() 抓取到的所有新闻的重复度 / 重合度。
如需更准确的相似度，可以之后改成 sklearn TF-IDF。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import difflib
import math
import re
from collections import defaultdict, Counter

from mktsource import fetch_news  # 直接复用你已有的函数


# -----------------------------
# 配置参数
# -----------------------------

# 判定“完全重复 / 基本同一条新闻”的相似度阈值
DUP_THRESHOLD = 0.80

# 判定“主题类似（不同版本）”的相似度阈值
SIMILAR_THRESHOLD = 0.60

# 为了节省计算量，限制总 pair 数（可按需调大）
MAX_PAIR_COMPARISONS = 300_000


# -----------------------------
# 数据结构
# -----------------------------

@dataclass
class NewsItem:
    idx: int
    raw_line: str
    source: str
    section: str
    title: str
    summary: str
    text_for_similarity: str  # 归一化后的文本


@dataclass
class SimilarityHit:
    i: int
    j: int
    score: float
    type: str  # "dup" or "similar"


# -----------------------------
# 工具函数
# -----------------------------

FIELD_PATTERN = re.compile(r"\s*\|\s*")


def normalize_text(text: str) -> str:
    """用于相似度计算的简单文本归一化."""
    text = text.lower()
    text = re.sub(r"http[s]?://\S+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_line_to_item(line: str, idx: int) -> NewsItem:
    """
    把 mktsource.fetch_news() 返回的每一行解析成 NewsItem。
    行格式类似：
    "Source: xxx | Section: yyy | Title: zzz | Summary: ..."
    """
    parts = FIELD_PATTERN.split(line)
    fields = {}
    for part in parts:
        if ": " in part:
            key, value = part.split(": ", 1)
            fields[key.strip().lower()] = value.strip()

    source = fields.get("source", "Unknown")
    section = fields.get("section", "Unknown")
    title = fields.get("title", "")
    summary = fields.get("summary", "") or fields.get("description", "") or ""

    combined = f"{title}. {summary}".strip()
    norm_text = normalize_text(combined)

    return NewsItem(
        idx=idx,
        raw_line=line,
        source=source,
        section=section,
        title=title,
        summary=summary,
        text_for_similarity=norm_text or normalize_text(title),
    )


def compute_similarity(a: str, b: str) -> float:
    """用 difflib 计算两个字符串的相似度 [0,1]."""
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


# -----------------------------
# 主分析逻辑
# -----------------------------

def analyze_duplicates(items: list[NewsItem]) -> tuple[
    list[SimilarityHit],
    dict[str, dict],
    dict[str, dict],
    dict[tuple[str, str], int]
]:
    """
    返回：
    - hits: 所有相似度 >= SIMILAR_THRESHOLD 的 pair
    - source_stats: 每个 source 的统计
    - section_stats: 每个 section 的统计
    - source_overlap: (source_a, source_b) -> 重复条数
    """
    n = len(items)
    print(f"Total news items: {n}")

    hits: list[SimilarityHit] = []
    source_stats = {
        s: {"total": 0, "dup": 0, "similar": 0}
        for s in {item.source for item in items}
    }
    section_stats = {
        s: {"total": 0, "dup": 0, "similar": 0}
        for s in {item.section for item in items}
    }

    # 每条新闻是否被标记为“重复” / “相似”
    is_dup = [False] * n
    is_similar = [False] * n

    # source 之间的交叉重合统计
    source_overlap: dict[tuple[str, str], int] = defaultdict(int)

    # 先统计总数
    for it in items:
        source_stats[it.source]["total"] += 1
        section_stats[it.section]["total"] += 1

    pair_count = 0
    for i in range(n):
        for j in range(i):
            pair_count += 1
            if pair_count > MAX_PAIR_COMPARISONS:
                print(
                    f"WARNING: reached MAX_PAIR_COMPARISONS={MAX_PAIR_COMPARISONS}, "
                    f"stop further pairwise comparison to节省时间。"
                )
                break

            a = items[i]
            b = items[j]

            # 快速剪枝：长度太短 or 文本完全一样可特殊处理
            if a.text_for_similarity == b.text_for_similarity:
                score = 1.0
            else:
                score = compute_similarity(a.text_for_similarity, b.text_for_similarity)

            if score >= SIMILAR_THRESHOLD:
                hit_type = "dup" if score >= DUP_THRESHOLD else "similar"
                hits.append(SimilarityHit(i=i, j=j, score=score, type=hit_type))

                # 标记统计（按“后来者 i”为重复）
                if hit_type == "dup":
                    is_dup[i] = True
                    source_stats[a.source]["dup"] += 1
                    section_stats[a.section]["dup"] += 1
                else:
                    is_similar[i] = True
                    source_stats[a.source]["similar"] += 1
                    section_stats[a.section]["similar"] += 1

                # 统计 source 间重合（无向边：排序一下）
                sa, sb = sorted([a.source, b.source])
                source_overlap[(sa, sb)] += 1

        if pair_count > MAX_PAIR_COMPARISONS:
            break

    # 计算重复率
    for s, st in source_stats.items():
        total = st["total"] or 1
        st["dup_rate"] = st["dup"] / total
        st["similar_rate"] = (st["dup"] + st["similar"]) / total

    for s, st in section_stats.items():
        total = st["total"] or 1
        st["dup_rate"] = st["dup"] / total
        st["similar_rate"] = (st["dup"] + st["similar"]) / total

    return hits, source_stats, section_stats, source_overlap


# -----------------------------
# 打印报告
# -----------------------------

def print_stats(source_stats, section_stats, source_overlap):
    print("\n=== Per Source Stats ===")
    for src, st in sorted(
        source_stats.items(), key=lambda kv: kv[1]["dup_rate"], reverse=True
    ):
        print(
            f"- {src:20s} | total: {st['total']:4d} | "
            f"dup: {st['dup']:3d} ({st['dup_rate']:.1%}) | "
            f"similar+dup: {st['dup']+st['similar']:3d} ({st['similar_rate']:.1%})"
        )

    print("\n=== Per Section Stats ===")
    for sec, st in sorted(
        section_stats.items(), key=lambda kv: kv[1]["dup_rate"], reverse=True
    ):
        print(
            f"- {sec:25s} | total: {st['total']:4d} | "
            f"dup: {st['dup']:3d} ({st['dup_rate']:.1%}) | "
            f"similar+dup: {st['dup']+st['similar']:3d} ({st['similar_rate']:.1%})"
        )

    print("\n=== Source Overlap (top 20 pairs by count) ===")
    sorted_overlap = sorted(
        source_overlap.items(), key=lambda kv: kv[1], reverse=True
    )[:20]
    for (sa, sb), cnt in sorted_overlap:
        print(f"- {sa}  <->  {sb} : {cnt} similar/dup items")


def print_example_pairs(hits, items, max_examples: int = 10):
    """
    打印一些典型重复 pair，方便人工 eyeball 检查。
    """
    if not hits:
        print("\nNo similar pairs found above threshold.")
        return

    print(f"\n=== Example Duplicate / Similar Pairs (top {max_examples}) ===")
    # 先按 score 排序
    hits_sorted = sorted(hits, key=lambda h: h.score, reverse=True)[:max_examples]
    for h in hits_sorted:
        a = items[h.i]
        b = items[h.j]
        print("\n------------------------")
        print(f"[{h.type.upper()}] score={h.score:.3f}")
        print(f"A: ({a.source} | {a.section}) Title: {a.title}")
        print(f"B: ({b.source} | {b.section}) Title: {b.title}")


# -----------------------------
# main
# -----------------------------

def main():
    raw = fetch_news()
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    items = [parse_line_to_item(line, idx) for idx, line in enumerate(lines)]

    hits, source_stats, section_stats, source_overlap = analyze_duplicates(items)

    print_stats(source_stats, section_stats, source_overlap)
    print_example_pairs(hits, items, max_examples=15)


if __name__ == "__main__":
    print(f"[{datetime.utcnow().isoformat()}] Running duplicate analysis...")
    main()