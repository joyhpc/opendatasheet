#!/usr/bin/env python3
"""Validate the structure and key cross-links of core hardware review docs."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = REPO_ROOT / "docs" / "hardware-engineering"
HEADING_RE = re.compile(r"^##\s+(.*)$", re.MULTILINE)

STANDARD_CORE_HEADINGS = {
    "适用场景",
    "不适用场景",
    "典型失效症状",
    "先看什么",
    "必查顺序",
    "硬规则",
    "常见失误",
    "评审示例",
    "仓库入口",
    "官方参考",
}

POWER_UP_HEADINGS = {
    "适用场景",
    "不适用场景",
    "典型失效症状",
    "先看什么",
    "典型错误做法",
    "必查顺序",
    "硬规则",
    "常见失效症状与优先排查",
    "评审示例",
    "仓库入口",
    "官方参考",
}

CORE_DOC_REQUIREMENTS = {
    "power-tree-review-checklist.md": STANDARD_CORE_HEADINGS,
    "buck-converter-schematic-review.md": STANDARD_CORE_HEADINGS,
    "tvs-and-esd-placement.md": STANDARD_CORE_HEADINGS,
    "i2c-pullup-and-topology.md": STANDARD_CORE_HEADINGS,
    "usb2-protection-and-routing.md": STANDARD_CORE_HEADINGS,
    "ethernet-phy-bringup-checklist.md": STANDARD_CORE_HEADINGS,
    "fpga-power-rail-planning.md": STANDARD_CORE_HEADINGS,
    "fpga-bank-voltage-planning.md": STANDARD_CORE_HEADINGS,
    "ddr-layout-review-checklist.md": STANDARD_CORE_HEADINGS,
    "differential-pair-routing.md": STANDARD_CORE_HEADINGS,
    "mixed-signal-grounding.md": STANDARD_CORE_HEADINGS,
    "adc-reference-and-input-drive.md": STANDARD_CORE_HEADINGS,
    "thermal-via-and-copper-spreading.md": STANDARD_CORE_HEADINGS,
    "manufacturing-dfm-quick-check.md": STANDARD_CORE_HEADINGS,
    "power-up-debug-sequence.md": POWER_UP_HEADINGS,
}

SUPPORT_DOC_REQUIREMENTS = {
    "index.md": {"定位", "最先看这 5 篇", "核心主题", "使用建议"},
    "formal-review-execution-order.md": {
        "目的",
        "适用场景",
        "不适用场景",
        "评审总顺序",
        "推荐示例入口",
        "Phase 1: 系统供电与保护",
        "Phase 2: 板外接口与总线",
        "Phase 3: FPGA / DDR / 高速链路",
        "Phase 4: 模拟、采样与热",
        "Phase 5: 制造与工艺",
        "Phase 6: Bring-up 放行条件",
        "最小评审输出",
        "常见错误顺序",
        "建议用法",
    },
    "review-record-template.md": {
        "用途",
        "项目信息",
        "Phase 1: 系统供电与保护",
        "Phase 2: 板外接口与总线",
        "Phase 3: FPGA / DDR / 高速链路",
        "Phase 4: 模拟、采样与热",
        "Phase 5: 制造与工艺",
        "Phase 6: Bring-up 放行条件",
        "汇总",
    },
    "review-gate-matrix.md": {
        "目的",
        "使用方式",
        "Phase 1: 系统供电与保护",
        "Phase 2: 板外接口与总线",
        "Phase 3: FPGA / DDR / 高速链路",
        "Phase 4: 模拟、采样与热",
        "Phase 5: 制造与工艺",
        "Phase 6: Bring-up 放行条件",
        "使用纪律",
    },
}

REQUIRED_LINKS = {
    "index.md": {
        "best-practice-reference-matrix.md",
        "formal-review-execution-order.md",
        "review-record-template.md",
        "review-gate-matrix.md",
    }
    | set(CORE_DOC_REQUIREMENTS.keys()),
    "formal-review-execution-order.md": {
        "review-record-template.md",
        "review-gate-matrix.md",
    },
    "review-gate-matrix.md": set(CORE_DOC_REQUIREMENTS.keys())
    | {"formal-review-execution-order.md", "review-record-template.md"},
}


def extract_headings(path: Path) -> set[str]:
    return set(HEADING_RE.findall(path.read_text(encoding="utf-8")))


def check_required_headings(filename: str, required_headings: set[str]) -> list[str]:
    path = DOCS_ROOT / filename
    if not path.is_file():
        return [f"missing file: docs/hardware-engineering/{filename}"]
    headings = extract_headings(path)
    return [
        f"docs/hardware-engineering/{filename}: missing section '## {heading}'"
        for heading in sorted(required_headings - headings)
    ]


def check_required_links(filename: str, required_links: set[str]) -> list[str]:
    path = DOCS_ROOT / filename
    if not path.is_file():
        return [f"missing file: docs/hardware-engineering/{filename}"]
    text = path.read_text(encoding="utf-8")
    return [
        f"docs/hardware-engineering/{filename}: missing link target '{target}'"
        for target in sorted(required_links)
        if target not in text
    ]


def main() -> int:
    errors: list[str] = []

    for filename, required_headings in CORE_DOC_REQUIREMENTS.items():
        errors.extend(check_required_headings(filename, required_headings))

    for filename, required_headings in SUPPORT_DOC_REQUIREMENTS.items():
        errors.extend(check_required_headings(filename, required_headings))

    for filename, required_links in REQUIRED_LINKS.items():
        errors.extend(check_required_links(filename, required_links))

    if errors:
        print("Hardware doc structure check failed:\n")
        for error in errors:
            print(f"- {error}")
        print(f"\nFound {len(errors)} issue(s).")
        return 1

    checked_count = len(CORE_DOC_REQUIREMENTS) + len(SUPPORT_DOC_REQUIREMENTS)
    print(f"Hardware doc structure check passed: {checked_count} files validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
