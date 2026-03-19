#!/usr/bin/env python3
"""Parse Anlogic PH1A package-level capability data from official sources.

This parser does not fabricate per-pin/package-pinout data. The current raw
bundle contains package-capability manuals and the official product table, but
it does not yet include a package pin workbook comparable to the Intel/AMD
pinout sources already used in this repository.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from html import unescape
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "fpga" / "anlogic_ph1a"
OUTPUT_DIR = ROOT / "data" / "extracted_v2" / "fpga" / "anlogic_ph1a"

PRODUCT_PAGES = {
    "zh-CN": "https://www.anlogic.com/product/fpga/phoenix/ph1a",
    "en": "https://www.anlogic.com/en/product/fpga/phoenix/ph1a",
    "jp": "https://www.anlogic.com/jp/product/fpga/phoenix/ph1a",
}

PRIMARY_LOCALE = "zh-CN"

HEADER_ALIASES = {
    "Device": "Device",
    "LUTs": "LUTs",
    "DFFs": "DFFs",
    "DistributeRAM": "DistributeRAM",
    "eRAM-20K": "eRAM-20K",
    "eRAM-Total": "eRAM-Total",
    "DSP": "DSP",
    "PLL": "PLL",
    "Serdes-Channels": "Serdes-Channels",
    "Serdes-Rate": "Serdes-Rate",
    "DDR-Rate": "DDR-Rate",
    "DDR-Width": "DDR-Width",
    "MIPI-IO": "MIPI-IO",
    "USER IO": "USER IO",
    "封装类型": "封装类型",
    "Package Type": "封装类型",
    "Package Methods": "封装类型",
    "封装尺寸": "封装尺寸",
    "Package Size": "封装尺寸",
    "球间距": "球间距",
    "Pitch": "球间距",
    "Sphere Pitch": "球间距",
}

SOURCE_FILES = {
    "configuration_user_manual": "UG905_安路科技PH1A系列FPGA 配置用户手册.pdf",
    "pll_user_manual": "UG906_安路科技PH1A系列FPGA PLL用户手册.pdf",
    "io_user_manual": "UG911_安路科技PH1A系列FPGA IO用户手册.pdf",
    "clock_user_manual": "UG912_安路科技PH1A系列FPGA 时钟资源用户手册.pdf",
    "serdes_user_manual": "UG909_安路科技PH1A系列FPGA SERDES用户手册.pdf",
    "pcie_user_manual": "UG913_安路科技PH1A系列FPGA PCIE用户手册.pdf",
    "ddr_user_manual": "UG915_安路科技PH1A系列FPGA DDR3_4高速接口用户手册.pdf",
    "hardware_design_guide": "UG907_安路科技PH1A系列FPGA 硬件设计指南.pdf",
    "sso_rules_report": "TR901_安路科技PH1A系列 FPGA SSO限制规则说明.pdf",
}

SERDES_PROTOCOLS = {
    "PCI Express": {"variants": ["Gen1", "Gen2", "Gen3"], "lane_widths": [1, 2, 4]},
    "1000BASE-KX": {"supported": True},
    "SGMII": {"supported": True},
    "QSGMII": {"supported": True},
    "XAUI": {"supported": True},
    "RXAUI": {"supported": True},
    "10GBASE-KX4": {"supported": True},
    "10GBASE-KR": {"supported": True},
    "CEI": {"line_rates_gbps": [6.0, 11.0]},
    "CPRI": {"line_rates_gbps": [2.4576, 4.9152, 6.144, 9.8304]},
    "JESD204B": {"line_rates_gbps": [1.25, 2.5, 5.0, 6.25, 12.5]},
    "SRIO": {"line_rates_gbps": [1.25, 2.5, 3.125, 5.0, 6.25]},
}

PCIE_PACKAGE_RULES = {
    "PH1A400SFG900": {
        "present": True,
        "max_link_width": 4,
        "generations": ["Gen1", "Gen2", "Gen3"],
        "hardcore": True,
        "phy_banks": [82, 83],
        "evidence_level": "package_verified",
    },
    "PH1A400SFG676": {
        "present": True,
        "max_link_width": 4,
        "generations": ["Gen1", "Gen2", "Gen3"],
        "hardcore": True,
        "phy_banks": [82, 83],
        "evidence_level": "package_verified",
    },
    "PH1A90SBG484": {
        "present": True,
        "max_link_width": 4,
        "generations": ["Gen1", "Gen2", "Gen3"],
        "hardcore": True,
        "phy_banks": [82, 83],
        "evidence_level": "package_verified",
    },
    "PH1A90SEG324": {
        "present": True,
        "max_link_width": 4,
        "generations": ["Gen1", "Gen2", "Gen3"],
        "hardcore": True,
        "phy_banks": [82, 83],
        "evidence_level": "package_verified",
    },
    "PH1A180SFG676": {
        "present": True,
        "max_link_width": 4,
        "generations": ["Gen1", "Gen2", "Gen3"],
        "hardcore": True,
        "phy_banks": [80, 81],
        "evidence_level": "package_verified",
    },
    "PH1A60GEG324": {
        "present": False,
        "max_link_width": 0,
        "generations": [],
        "hardcore": False,
        "phy_banks": [],
        "evidence_level": "package_verified",
    },
}

MIPI_DOC_RULES = {
    "PH1A400SFG900": {"present": False, "directions": [], "evidence_level": "package_verified"},
    "PH1A400SFG676": {"present": False, "directions": [], "evidence_level": "package_verified"},
    "PH1A180SFG676": {"present": True, "directions": ["rx"], "evidence_level": "package_verified"},
    "PH1A90SBG484": {"present": True, "directions": ["rx"], "evidence_level": "package_verified"},
    "PH1A90SEG324": {"present": False, "directions": [], "evidence_level": "package_verified"},
    "PH1A60GEG324": {"present": False, "directions": [], "evidence_level": "package_verified"},
}

CLOCK_DEVICE_PROFILES = {
    "PH1A400": {"clock_regions_per_half": 7, "right_half_serdes_clock_regions": 4},
    "PH1A180": {"clock_regions_per_half": 7, "right_half_serdes_clock_regions": 4},
    "PH1A90": {"clock_regions_per_half": 4, "right_half_serdes_clock_regions": 2},
    "PH1A60": {"clock_regions_per_half": 3, "right_half_serdes_clock_regions": 0},
}

SSO_BANK_PAIR_BUDGETS = {
    "PH1A400SFG900": {
        "11": {"user_ios": 50, "vccio_gnd_pairs": 7},
        "12": {"user_ios": 50, "vccio_gnd_pairs": 7},
        "13": {"user_ios": 50, "vccio_gnd_pairs": 7},
        "14": {"user_ios": 50, "vccio_gnd_pairs": 7},
        "15": {"user_ios": 50, "vccio_gnd_pairs": 7},
        "16": {"user_ios": 50, "vccio_gnd_pairs": 7},
        "17": {"user_ios": 50, "vccio_gnd_pairs": 7},
        "31": {"user_ios": 50, "vccio_gnd_pairs": 18},
        "32": {"user_ios": 50, "vccio_gnd_pairs": 18},
        "33": {"user_ios": 50, "vccio_gnd_pairs": 18},
    },
    "PH1A400SFG676": {
        "11": {"user_ios": 50, "vccio_gnd_pairs": 7},
        "12": {"user_ios": 50, "vccio_gnd_pairs": 7},
        "13": {"user_ios": 50, "vccio_gnd_pairs": 7},
        "14": {"user_ios": 50, "vccio_gnd_pairs": 7},
        "15": {"user_ios": 50, "vccio_gnd_pairs": 7},
        "16": {"user_ios": 50, "vccio_gnd_pairs": 7},
        "17": {"user_ios": 50, "vccio_gnd_pairs": 7},
        "31": {"user_ios": 50, "vccio_gnd_pairs": 18},
        "32": {"user_ios": 50, "vccio_gnd_pairs": 18},
        "33": {"user_ios": 50, "vccio_gnd_pairs": 18},
    },
    "PH1A60GEG324": {
        "11": {"user_ios": 50, "vccio_gnd_pairs": 8},
        "12": {"user_ios": 50, "vccio_gnd_pairs": 6},
        "13": {"user_ios": 50, "vccio_gnd_pairs": 6},
        "31": {"user_ios": 50, "vccio_gnd_pairs": 8},
        "32": {"user_ios": 50, "vccio_gnd_pairs": 6},
        "33": {"user_ios": 50, "vccio_gnd_pairs": 6},
    },
    "PH1A90SBG484": {
        "11": {"user_ios": 34, "vccio_gnd_pairs": 4},
        "12": {"user_ios": 50, "vccio_gnd_pairs": 6},
        "13": {"user_ios": 50, "vccio_gnd_pairs": 6},
        "14": {"user_ios": 35, "vccio_gnd_pairs": 4},
        "31": {"user_ios": 40, "vccio_gnd_pairs": 6},
        "32": {"user_ios": 50, "vccio_gnd_pairs": 6},
    },
    "PH1A90SEG324": {
        "12": {"user_ios": 50, "vccio_gnd_pairs": 6},
        "13": {"user_ios": 47, "vccio_gnd_pairs": 5},
        "32": {"user_ios": 50, "vccio_gnd_pairs": 6},
    },
    "PH1A180SFG676": {
        "11": {"user_ios": 25, "vccio_gnd_pairs": 3},
        "12": {"user_ios": 50, "vccio_gnd_pairs": 6},
        "13": {"user_ios": 50, "vccio_gnd_pairs": 6},
        "14": {"user_ios": 50, "vccio_gnd_pairs": 6},
        "15": {"user_ios": 50, "vccio_gnd_pairs": 7},
        "31": {"user_ios": 50, "vccio_gnd_pairs": 6},
        "32": {"user_ios": 50, "vccio_gnd_pairs": 6},
        "33": {"user_ios": 50, "vccio_gnd_pairs": 6},
    },
}

SSO_VCCIO_STANDARDS = {
    "HRIO": {"3.3V": "LVCMOS33", "2.5V": "LVCMOS25", "1.8V": "LVCMOS18", "1.5V": "LVCMOS15"},
    "HPIO": {"1.8V": "LVCMOS18", "1.5V": "LVCMOS15", "1.2V": "LVCMOS12"},
}

SSO_LIMIT_VALUES = {
    "PH1A400": {
        "HRIO": {
            "3.3V": {4: 15, 8: 15, 12: 8, 16: 4},
            "2.5V": {4: 15, 8: 15, 12: 10, 16: 5},
            "1.8V": {4: 15, 8: 15, 12: 12, 16: 6},
            "1.5V": {4: 15, 8: 15, 12: 12, 16: 11},
        },
        "HPIO": {
            "1.8V": {4: 17, 8: 17, 12: 17},
            "1.5V": {4: 17, 8: 17, 12: 17},
            "1.2V": {4: 17, 8: 17, 12: 17},
        },
    },
    "PH1A60": {
        "HRIO": {
            "3.3V": {4: 15, 8: 15, 12: 8, 16: 4},
            "2.5V": {4: 15, 8: 15, 12: 10, 16: 5},
            "1.8V": {4: 15, 8: 15, 12: 12, 16: 6},
            "1.5V": {4: 15, 8: 15, 12: 12, 16: 11},
        },
        "HPIO": {},
    },
    "PH1A90": {
        "HRIO": {
            "3.3V": {4: 12, 8: 12, 12: 5, 16: 4},
            "2.5V": {4: 12, 8: 12, 12: 6, 16: 5},
            "1.8V": {4: 12, 8: 12, 12: 6, 16: 5},
            "1.5V": {4: 12, 8: 12, 12: 6, 16: 5},
        },
        "HPIO": {
            "1.8V": {4: 17, 8: 17, 12: 17},
            "1.5V": {4: 17, 8: 17, 12: 17},
            "1.2V": {4: 17, 8: 17, 12: 17},
        },
    },
    "PH1A180": {
        "HRIO": {
            "3.3V": {4: 15, 8: 15, 12: 8, 16: 4},
            "2.5V": {4: 15, 8: 15, 12: 10, 16: 5},
            "1.8V": {4: 15, 8: 15, 12: 12, 16: 6},
            "1.5V": {4: 15, 8: 15, 12: 12, 16: 11},
        },
        "HPIO": {
            "1.8V": {4: 15, 8: 15, 12: 15},
            "1.5V": {4: 15, 8: 15, 12: 15},
            "1.2V": {4: 15, 8: 15, 12: 15},
        },
    },
}

CONFIGURATION_MODE_MATRIX = [
    {
        "mode": "master_spi",
        "mode_pins": "001",
        "data_widths": [1, 2, 4],
        "cclk_direction": "output",
    },
    {
        "mode": "slave_parallel",
        "mode_pins": "110",
        "data_widths": [8, 16, 32],
        "cclk_direction": "input",
    },
    {
        "mode": "slave_serial",
        "mode_pins": "111",
        "data_widths": [1],
        "cclk_direction": "input",
    },
    {
        "mode": "jtag",
        "mode_pins": None,
        "data_widths": [],
        "cclk_direction": None,
    },
]


def _strip_tags(text: str) -> str:
    value = re.sub(r"<[^>]+>", " ", text)
    value = unescape(value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _safe_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _sort_key(device: str) -> tuple[int, str]:
    match = re.match(r"PH1A(\d+)", device)
    size = int(match.group(1)) if match else 0
    return (size, device)


def _read_pdf_text(path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", str(path), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _fetch_html(url: str) -> str:
    result = subprocess.run(
        [
            "curl",
            "-L",
            "--max-time",
            "20",
            "-A",
            "Mozilla/5.0",
            url,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _table_html(page_html: str) -> str:
    match = re.search(r'<table class="t_b3k2table".*?</table>', page_html, re.S)
    if not match:
        raise ValueError("could not locate PH1A product table in official page")
    return match.group(0)


def _parse_table(table_html: str) -> list[dict[str, str]]:
    header_match = re.search(r"<thead>(.*?)</thead>", table_html, re.S)
    body_match = re.search(r"<tbody[^>]*>(.*?)</tbody>", table_html, re.S)
    if not header_match or not body_match:
        raise ValueError("product table missing thead/tbody")

    raw_headers = [
        _strip_tags(cell)
        for cell in re.findall(r"<th[^>]*>(.*?)</th>", header_match.group(1), re.S)
    ]
    headers = [HEADER_ALIASES.get(header, header) for header in raw_headers]
    rows: list[dict[str, str]] = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", body_match.group(1), re.S):
        cells = [_strip_tags(cell) for cell in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)]
        if not cells:
            continue
        if len(cells) != len(headers):
            raise ValueError(f"unexpected PH1A row width: expected {len(headers)}, got {len(cells)}")
        rows.append(dict(zip(headers, cells)))
    return rows


def _parse_optional_number(value: str) -> int | None:
    normalized = value.strip()
    if normalized in {"", "-", "\\", "/"}:
        return None
    normalized = normalized.replace(",", "")
    match = re.search(r"(\d+)", normalized)
    return int(match.group(1)) if match else None


def _parse_optional_float(value: str) -> float | None:
    normalized = value.strip()
    if normalized in {"", "-", "\\", "/"}:
        return None
    normalized = normalized.replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)", normalized)
    return float(match.group(1)) if match else None


def _parse_package_size_mm(value: str) -> dict[str, float] | None:
    normalized = value.strip()
    if normalized in {"", "-", "\\", "/"}:
        return None
    match = re.match(r"(\d+(?:\.\d+)?)\*(\d+(?:\.\d+)?)", normalized)
    if not match:
        return None
    return {"x_mm": float(match.group(1)), "y_mm": float(match.group(2))}


def _parse_width_bits(value: str) -> int | None:
    normalized = value.strip()
    if normalized in {"", "-", "\\", "/"}:
        return None
    match = re.search(r"x(\d+)", normalized, re.I)
    return int(match.group(1)) if match else None


def _split_device_name(product_name: str) -> tuple[str, str, str | None]:
    cleaned = product_name.strip()
    match = re.match(r"^(PH1A\d+)([A-Z]{3}\d+)(?:/([A-Z]))?$", cleaned)
    if not match:
        raise ValueError(f"unexpected PH1A device naming: {product_name!r}")
    base_device = match.group(1)
    package = match.group(2)
    ordering_suffix = match.group(3)
    return f"{base_device}{package}", base_device, ordering_suffix


def _normalize_web_rows(rows: list[dict[str, str]], locale: str) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for row in rows:
        product_name = row["Device"]
        device, base_device, ordering_suffix = _split_device_name(product_name)
        normalized[device] = {
            "locale": locale,
            "product_name": product_name,
            "device": device,
            "base_device": base_device,
            "package": device[len(base_device):],
            "ordering_suffix": ordering_suffix,
            "resources": {
                "luts": _parse_optional_number(row["LUTs"]),
                "dffs": _parse_optional_number(row["DFFs"]),
                "distributed_ram_kbits": _parse_optional_number(row["DistributeRAM"]),
                "eram_20k_blocks": _parse_optional_number(row["eRAM-20K"]),
                "eram_total_kbits": _parse_optional_number(row["eRAM-Total"]),
                "dsp_blocks": _parse_optional_number(row["DSP"]),
                "pll_blocks": _parse_optional_number(row["PLL"]),
            },
            "package_summary": {
                "serdes_channels": _parse_optional_number(row["Serdes-Channels"]),
                "serdes_rate_gbps": _parse_optional_float(row["Serdes-Rate"]),
                "ddr_rate_mbps": _parse_optional_number(row["DDR-Rate"]),
                "ddr_width_bits": _parse_width_bits(row["DDR-Width"]),
                "mipi_io_count": _parse_optional_number(row["MIPI-IO"]),
                "user_io_count": _parse_optional_number(row["USER IO"]),
                "package_body": row["封装类型"] or None,
                "package_size_mm": _parse_package_size_mm(row["封装尺寸"]),
                "ball_pitch_mm": _parse_optional_float(row["球间距"]),
            },
            "raw_table_row": row,
        }
    return normalized


def _parse_bank_distribution(io_text: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    pattern = re.compile(
        r"(PH1A\d+[A-Z]{3}\d+)\s+芯片的 HR I/O bank 主要分布在 bank([0-9,\s]+)[。；，]\s*"
        r"(?:HP I/O bank 主要\s*分布在\s*bank\s*([0-9,\s]+)[；。]?\s*)?"
        r"(.*?)(?=(?:PH1A\d+[A-Z]{3}\d+\s+芯片的 HR I/O bank)|HR I/O|$)",
        re.S,
    )
    for match in pattern.finditer(io_text):
        device = match.group(1)
        hr = [int(item) for item in re.findall(r"\d+", match.group(2))]
        hp = [int(item) for item in re.findall(r"\d+", match.group(3) or "")]
        note_text = _strip_tags(match.group(4) or "")
        notes = [sentence.strip("；。 ") for sentence in re.split(r"[；。]", note_text) if sentence.strip()]
        result[device] = {
            "hr_banks": hr,
            "hp_banks": hp,
            "notes": notes,
            "source": "UG911",
        }
    return result


def _extract_doc_version(text: str, doc_id: str) -> str | None:
    match = re.search(rf"{re.escape(doc_id)}[（(]v([0-9.]+)[)）]", text, re.I)
    return match.group(1) if match else None


def _build_locale_conflicts(locale_rows: dict[str, dict[str, dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    devices = sorted({device for rows in locale_rows.values() for device in rows})
    tracked_fields = [
        ("package_summary", "serdes_channels"),
        ("package_summary", "serdes_rate_gbps"),
        ("package_summary", "ddr_rate_mbps"),
        ("package_summary", "ddr_width_bits"),
        ("package_summary", "mipi_io_count"),
        ("package_summary", "user_io_count"),
        ("package_summary", "package_body"),
    ]
    conflicts: dict[str, list[dict[str, Any]]] = {}
    for device in devices:
        device_conflicts: list[dict[str, Any]] = []
        for container_key, value_key in tracked_fields:
            observations = {
                locale: rows[device][container_key][value_key]
                for locale, rows in locale_rows.items()
                if device in rows
            }
            distinct = {json.dumps(value, sort_keys=True, ensure_ascii=False) for value in observations.values()}
            if len(distinct) > 1:
                device_conflicts.append({
                    "field": value_key,
                    "observations": observations,
                })
        if device_conflicts:
            conflicts[device] = device_conflicts
    return conflicts


def _source_traceability(doc_texts: dict[str, str]) -> dict[str, Any]:
    traces: dict[str, Any] = {
        "official_product_pages": {
            "primary_locale": PRIMARY_LOCALE,
            "sources": [
                {"locale": locale, "source_url": url}
                for locale, url in PRODUCT_PAGES.items()
            ],
        }
    }
    for key, filename in SOURCE_FILES.items():
        doc_path = RAW_DIR / filename
        doc_text = doc_texts[key]
        doc_id_match = re.match(r"([A-Z]+_?\d+)", filename)
        doc_id = doc_id_match.group(1) if doc_id_match else filename
        traces[key] = {
            "source_file": filename,
            "source_path": str(doc_path.relative_to(ROOT)),
            "source_version": _extract_doc_version(doc_text, doc_id),
        }
    return traces


def _package_io_block(device: str, web_entry: dict[str, Any], bank_info: dict[str, dict[str, Any]]) -> dict[str, Any]:
    block = {
        "hr_banks": None,
        "hp_banks": None,
        "notes": [],
        "evidence_level": "unknown",
        "source": None,
    }
    if device in bank_info:
        block.update({
            "hr_banks": bank_info[device]["hr_banks"],
            "hp_banks": bank_info[device]["hp_banks"],
            "notes": bank_info[device]["notes"],
            "evidence_level": "package_verified",
            "source": "UG911",
        })
    elif web_entry["package_summary"]["user_io_count"] is not None:
        block.update({
            "notes": [
                "Official product page provides user IO count, but the current local raw bundle does not contain a package-bank map for this package."
            ],
            "evidence_level": "web_only",
            "source": "official_product_page",
        })
    return block


def _base_device_family(device: str) -> str:
    match = re.match(r"^(PH1A\d+)", device)
    if not match:
        raise ValueError(f"unexpected PH1A device naming: {device!r}")
    return match.group(1)


def _clock_distribution_block(device: str) -> dict[str, Any]:
    family = _base_device_family(device)
    profile = CLOCK_DEVICE_PROFILES[family]
    sources = ["dedicated_clock_pins", "pll_outputs", "internal_logic_via_bufg"]
    notes = [
        "Dedicated clock pins support differential and single-ended inputs; single-ended clocks only enter the global clock network through the P-side pin.",
        "Internal logic can drive BUFG, but clock quality is not controlled and should be reviewed before sign-off.",
    ]
    if profile["right_half_serdes_clock_regions"] > 0:
        sources.insert(2, "serdes_clock_outputs")
        notes.append("Right-half upper clock regions include SerDes clocking resources and can source high-speed interface clocks.")
    else:
        notes.append("PH1A60 does not include SerDes clock regions.")
    return {
        "class": "clocking_topology",
        "present": True,
        "global_clock_lines": 32,
        "clock_region_height_plb": 40,
        "clock_regions_per_half": profile["clock_regions_per_half"],
        "right_half_serdes_clock_regions": profile["right_half_serdes_clock_regions"],
        "pll_per_clock_region": 2,
        "mlclk_per_clock_region": 2,
        "lclk_per_clock_region": 4,
        "hr_ioclk_per_clock_region": 2,
        "hp_ioclk_per_clock_region": 4,
        "lclk_supported_dividers": [1, 2, 3, 4, 5, 6, 7, 8, 3.5],
        "global_clock_input_sources": sources,
        "dedicated_clock_input": {
            "differential_supported": True,
            "single_ended_supported": True,
            "single_ended_global_clock_entry_pin": "P",
        },
        "evidence_level": "family_manual",
        "source": "UG912",
        "notes": notes,
    }


def _configuration_modes_block() -> dict[str, Any]:
    return {
        "class": "boot_and_configuration",
        "present": True,
        "supported_modes": CONFIGURATION_MODE_MATRIX,
        "dedicated_pin_requirements": {
            "HSWAPEN": {
                "kind": "strap",
                "logic_0_behavior": "user_io_weak_pullup_during_configuration",
                "logic_1_behavior": "user_io_high_impedance_during_configuration",
            },
            "TRSTN": {
                "kind": "strap",
                "logic_0_behavior": "jtag_connected_to_configuration_controller",
                "logic_1_behavior": "jtag_connected_to_serdes_jtag_chain",
            },
            "TCK": {
                "kind": "dedicated_jtag",
                "recommended_pullup_ohms": 4700,
            },
            "TMS": {
                "kind": "dedicated_jtag",
                "recommended_pullup_ohms": 4700,
            },
            "PROGRAMN": {
                "kind": "dedicated_configuration_reset",
                "polarity": "active_low",
                "recommended_pullup_ohms": 4700,
                "pullup_rail": "VCCIO_0",
            },
            "INITN": {
                "kind": "bidirectional_open_drain_status",
                "polarity": "active_high",
                "recommended_pullup_ohms": 4700,
                "pullup_rail": "VCCIO",
            },
            "DONE": {
                "kind": "bidirectional_open_drain_status",
                "polarity": "active_high",
                "recommended_pullup_ohms": 4700,
                "pullup_rail": "VCCIO",
            },
        },
        "initialization_flow": {
            "default_clock_hz": 2_000_000,
            "clock_source": "on_chip_oscillator_divided_from_133mhz_by_64",
            "steps": [
                {"name": "cfg_por", "delay_cycles": 2**14},
                {"name": "mdelay", "delay_cycles": 2**16},
                {"name": "load_spi_id", "master_spi_only": True},
                {"name": "load_feature", "master_spi_only": True},
                {"name": "auto_clear"},
                {"name": "load_efuse", "efuse_payload_bits": 2048},
                {"name": "init_ok"},
            ],
            "programn_can_trigger_hot_reset": True,
            "bitstream_load_starts_after_initn_high": True,
        },
        "bitstream_load_flow": [
            {"name": "parallel_width_pattern", "slave_parallel_only": True},
            {"name": "syncwords", "jtag_skips": True},
            {"name": "idcode_check"},
            {"name": "load_bitstream"},
            {"name": "startup"},
        ],
        "startup_wakeup": {
            "domain": "independent_wakeup_clk",
            "signal_order": ["DONE", "GOE", "GSRN", "GWE", "WAKEUP"],
            "wakeup_always_last": True,
        },
        "resiliency_features": {
            "dual_boot": True,
            "multi_boot": True,
            "dna_bits": 64,
        },
        "security_features": {
            "security_bit_can_disable_jtag_pcm_readback": True,
            "readback_requires_ecc_stop_o_high_when_ecc_enabled": True,
        },
        "jtag_behavior": {
            "can_interrupt_other_configuration_modes": True,
            "supports_daisy_chain": True,
        },
        "notes": [
            "When INITN is held low externally, initialization is delayed and bitstream loading does not start.",
            "When PH1_LOGIC_MBOOT is instantiated, MULTI BOOT images should be burned with the dedicated MULTI BOOT download flow rather than plain JTAG image placement.",
        ],
        "evidence_level": "family_manual",
        "source": "UG905",
    }


def _pll_resources_block(device: str, web_entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "class": "pll_resources",
        "present": True,
        "package_pll_blocks": web_entry["resources"]["pll_blocks"],
        "per_pll_capabilities": {
            "clock_outputs": 7,
            "inverted_clock_outputs_supported": True,
            "fractional_output_paths": 7,
            "dynamic_phase_adjustment": {
                "fine_adjust_supported": True,
                "fine_step": "1/8_vco_period",
                "coarse_adjust_supported": True,
                "coarse_step": "1_vco_period",
            },
            "dynamic_reconfiguration": True,
            "spread_spectrum_clocking": True,
            "duty_cycle_adjustment": True,
            "lock_output": True,
            "cascade_supported": True,
        },
        "divider_ranges": {
            "reference_divider_n": {"min": 1, "max": 128},
            "feedback_divider_m": {"min": 1, "max": 128},
            "output_dividers_c0_to_c6": {"min": 1, "max": 128},
        },
        "bandwidth_modes": ["HIGH", "LOW", "MEDIUM"],
        "feedback_modes": [
            "source_synchronous",
            "no_compensation",
            "normal",
            "zero_delay_buffer",
        ],
        "zero_delay_buffer_constraints": {
            "feedback_path_requires_bidirectional_single_ended_io": True,
            "prefer_global_clock_pin": True,
            "avoid_pcb_trace_on_feedback_path": True,
            "refclk_below_50mhz_min_output_drive_mA": 8,
            "refclk_50_to_100mhz_min_output_drive_mA": 16,
            "input_and_output_same_bank_required_below_100mhz": True,
            "m_equals_n_required": True,
        },
        "notes": [
            "No-compensation mode uses internal self-feedback and prioritizes jitter performance over network-delay compensation.",
            "Zero-delay-buffer mode aligns the output clock pin phase to the PLL reference clock pin phase and should be treated as a board-level timing ownership decision.",
        ],
        "evidence_level": "family_manual",
        "source": "UG906",
    }


def _serdes_reference_clock_block(web_entry: dict[str, Any]) -> dict[str, Any]:
    present = bool(web_entry["package_summary"]["serdes_channels"])
    notes = [
        "SERDES reference clock P/N pins do not include internal termination; place the termination network externally.",
        "For PCIe, the 100 nF AC-coupling capacitor belongs on the transmitter side.",
    ]
    if not present:
        notes.append("This package does not expose SERDES channels in the official product table, so the refclk network guidance is not package-applicable.")
    return {
        "class": "serdes_reference_clocking",
        "present": present,
        "internal_differential_termination": False,
        "external_differential_termination_ohms": 100,
        "source_interfaces": ["LVDS", "LVPECL25", "LVPECL33"],
        "lvpecl_source_side_to_gnd_ohms": {
            "LVPECL25": 82,
            "LVPECL33": 150,
        },
        "evidence_level": "family_manual",
        "source": "UG907",
        "notes": notes,
    }


def _serdes_power_integrity_block(web_entry: dict[str, Any]) -> dict[str, Any]:
    present = bool(web_entry["package_summary"]["serdes_channels"])
    notes = [
        "Place the SERDES supply regulator close to the SERDES ground reference plane to minimize loop impedance.",
        "Shield SERDES supplies from board noise sources and place several small bypass capacitors close to the FPGA power pins, with larger capacitors farther away.",
        "Use ferrite-bead isolation between SERDES supply domains to reduce mutual interference.",
    ]
    if not present:
        notes.append("This package does not expose SERDES channels in the official product table, so SERDES supply guidance is not package-applicable.")
    return {
        "class": "power_integrity",
        "present": present,
        "rail_recommendations": {
            "VPHYVCCA": {
                "preferred_supply": "ldo_or_low_noise_dcdc",
                "max_ripple_mV": 30,
                "allow_dcdc_preregulation_before_ldo": True,
            },
            "VPHYVCCT": {
                "preferred_supply": "ldo_or_low_noise_dcdc",
                "max_ripple_mV": 30,
                "allow_dcdc_preregulation_before_ldo": True,
            },
        },
        "evidence_level": "family_manual",
        "source": "UG907",
        "notes": notes,
    }


def _sso_limit_tables(device: str) -> dict[str, Any]:
    family = _base_device_family(device)
    family_limits = SSO_LIMIT_VALUES[family]
    result: dict[str, Any] = {}
    for bank_type, voltage_map in family_limits.items():
        if not voltage_map:
            continue
        result[bank_type] = {}
        for vccio, drive_map in voltage_map.items():
            result[bank_type][vccio] = {
                "standard": SSO_VCCIO_STANDARDS[bank_type][vccio],
                "drive_strength_mA": {
                    str(drive): {"fast": limit, "med": limit, "slow": limit}
                    for drive, limit in drive_map.items()
                },
            }
    return result


def _sso_bank_pair_budgets(device: str, package_io_banks: dict[str, Any]) -> tuple[dict[str, Any], str]:
    budgets = SSO_BANK_PAIR_BUDGETS.get(device)
    if budgets:
        hr_banks = {str(bank) for bank in (package_io_banks.get("hr_banks") or [])}
        hp_banks = {str(bank) for bank in (package_io_banks.get("hp_banks") or [])}
        result = {}
        for bank, budget in budgets.items():
            entry = {
                "bank": bank,
                "user_ios": budget["user_ios"],
                "vccio_gnd_pairs": budget["vccio_gnd_pairs"],
            }
            if bank in hr_banks:
                entry["bank_type"] = "HRIO"
            elif bank in hp_banks:
                entry["bank_type"] = "HPIO"
            result[bank] = entry
        return result, "package_verified"

    if device == "PH1A90SEG325":
        return {}, "package_alias_inference"
    return {}, "family_manual_only"


def _io_sso_block(device: str, package_io_banks: dict[str, Any]) -> dict[str, Any]:
    bank_pair_budgets, evidence_level = _sso_bank_pair_budgets(device, package_io_banks)
    notes = [
        "SSO calculation applies only to single-ended output signals.",
        "For mixed drive or slew settings in one bank, sum the per-output weights 1/limit_per_pair and keep the total no greater than the bank VCCIO/GND pair count.",
    ]
    if device == "PH1A90SEG325":
        notes.append("TR901 publishes PH1A90 SBG484 and SEG324 bank budgets, but does not name SEG325 explicitly; reuse the PH1A90 per-pair limits only, and re-confirm bank-level budgets before schematic freeze.")
    return {
        "class": "io_signal_integrity",
        "present": True,
        "applies_to": "single_ended_outputs_only",
        "bank_pair_budgets": bank_pair_budgets,
        "limit_tables": _sso_limit_tables(device),
        "weighted_sum_rule": {
            "formula": "sum(io_count / limit_per_pair) <= vccio_gnd_pairs",
            "mixed_setting_weighting": "Each output contributes 1 / limit_per_pair for its own VCCIO, standard, drive strength, and slew setting.",
        },
        "mitigations": [
            "Use bank power isolation, careful PCB design, and adequate decoupling on VCCIO rails.",
            "Add pull-up protection on noise-sensitive signals such as PROGRAMN.",
            "Reduce simultaneous startup switching by delaying output enable after configuration.",
        ],
        "evidence_level": evidence_level,
        "source": "TR901",
        "notes": notes,
    }


def _memory_interface_block(device: str, web_entry: dict[str, Any]) -> dict[str, Any]:
    ddr_rate = web_entry["package_summary"]["ddr_rate_mbps"]
    ddr_width = web_entry["package_summary"]["ddr_width_bits"]
    if ddr_rate is None or ddr_width is None:
        return {
            "present": False,
            "hard_ppc": False,
            "supported_standards": [],
            "max_rate_mbps": None,
            "max_data_width_bits": None,
            "evidence_level": "package_verified",
            "source": "official_product_page",
        }

    evidence_level = "package_verified" if device.startswith("PH1A400") else "product_page_plus_family_manual"
    notes = []
    if device.startswith("PH1A400"):
        notes.append("UG907 validates DDR3/DDR4 placement on HPIO banks 31/32/33 and up to 72-bit width.")
    else:
        notes.append("UG915 confirms DDR3/DDR4 support for PH1A90/PH1A180/PH1A400 families; exact package-bank ownership should still be frozen in TD IO planning.")

    return {
        "present": True,
        "hard_ppc": device != "PH1A60GEG324",
        "supported_standards": ["DDR3", "DDR3L", "DDR4"],
        "max_rate_mbps": ddr_rate,
        "max_data_width_bits": ddr_width,
        "evidence_level": evidence_level,
        "source": "official_product_page+UG915",
        "notes": notes,
    }


def _mipi_phy_block(device: str, web_entry: dict[str, Any]) -> dict[str, Any]:
    web_count = web_entry["package_summary"]["mipi_io_count"]
    doc_rule = MIPI_DOC_RULES.get(device)
    present = web_count is not None and web_count > 0
    directions = ["rx"] if present else []
    notes: list[str] = []
    evidence_level = "web_only" if present else "official_product_page"
    source = "official_product_page"

    if doc_rule:
        present = doc_rule["present"]
        directions = doc_rule["directions"]
        evidence_level = doc_rule["evidence_level"]
        source = "UG907"
    elif present:
        notes.append("Current Chinese product page lists MIPI IO on this package, but the local raw hardware guide does not yet cover this package name.")

    if device == "PH1A90SBG484" and present:
        notes.append("UG921 explicitly documents 2 MIPI DPHY-RX groups, each up to 1 clock lane + 4 data lanes.")

    return {
        "present": present,
        "directions": directions,
        "mipi_io_count": web_count,
        "group_count": 2 if device == "PH1A90SBG484" and present else None,
        "max_data_lanes_per_group": 4 if device == "PH1A90SBG484" and present else None,
        "evidence_level": evidence_level,
        "source": source,
        "notes": notes,
    }


def _high_speed_serial_block(device: str, web_entry: dict[str, Any]) -> dict[str, Any]:
    channels = web_entry["package_summary"]["serdes_channels"]
    rate = web_entry["package_summary"]["serdes_rate_gbps"]
    if not channels:
        return {
            "present": False,
            "channel_pairs": 0,
            "serdes_dual_count": 0,
            "package_rate_ceiling_gbps": None,
            "supported_protocols": [],
            "protocol_matrix": {},
            "evidence_level": "package_verified",
            "source": "official_product_page+UG909",
            "notes": [],
        }

    notes = []
    if device == "PH1A400SFG900":
        notes.append("UG909 adds a package-specific note: only Bank 80 and Bank 84 expose dedicated recovered-clock output pins.")
    if device.startswith("PH1A90") or device.startswith("PH1A180"):
        notes.append("UG909 documents bidirectional adjacent-DUAL refclk sharing on PH1A90/PH1A180.")
    if device.startswith("PH1A400"):
        notes.append("UG909 documents single-direction adjacent-DUAL refclk sharing on PH1A400.")

    return {
        "present": True,
        "channel_pairs": channels,
        "serdes_dual_count": channels // 2,
        "package_rate_ceiling_gbps": rate,
        "supported_protocols": sorted(SERDES_PROTOCOLS),
        "protocol_matrix": SERDES_PROTOCOLS,
        "evidence_level": "package_verified",
        "source": "official_product_page+UG909",
        "notes": notes,
    }


def _pcie_block(device: str, has_conflict: bool) -> dict[str, Any]:
    if device in PCIE_PACKAGE_RULES:
        block = dict(PCIE_PACKAGE_RULES[device])
        block["source"] = "UG913"
        block["notes"] = []
        return block

    block = {
        "present": None,
        "max_link_width": None,
        "generations": [],
        "hardcore": None,
        "phy_banks": [],
        "evidence_level": "web_gap",
        "source": "official_product_page",
        "notes": [
            "Current local PCIe manual covers PH1A90SEG324 but not this package name; do not freeze PCIe ownership without package-specific confirmation."
        ],
    }
    if has_conflict:
        block["notes"].append("Official locale pages disagree on some package-level parameters for this device.")
    return block


def _family_summary(devices: list[dict[str, Any]], locale_conflicts: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    packages_with_serdes = [entry["device"] for entry in devices if entry["capability_blocks"]["high_speed_serial"]["present"]]
    packages_with_ddr = [entry["device"] for entry in devices if entry["capability_blocks"]["memory_interface"]["present"]]
    packages_with_mipi = [entry["device"] for entry in devices if entry["capability_blocks"]["mipi_phy"]["present"]]
    packages_with_pcie = [entry["device"] for entry in devices if entry["capability_blocks"]["pcie"]["present"] is True]
    return {
        "device_count": len(devices),
        "serdes_capable_packages": packages_with_serdes,
        "ddr_capable_packages": packages_with_ddr,
        "mipi_capable_packages": packages_with_mipi,
        "pcie_capable_packages": packages_with_pcie,
        "locale_conflict_devices": sorted(locale_conflicts),
    }


def build_dataset() -> dict[str, Any]:
    doc_texts = {key: _read_pdf_text(RAW_DIR / filename) for key, filename in SOURCE_FILES.items()}
    bank_info = _parse_bank_distribution(doc_texts["io_user_manual"])

    locale_rows: dict[str, dict[str, dict[str, Any]]] = {}
    locale_fetch_errors: list[dict[str, str]] = []
    for locale, url in PRODUCT_PAGES.items():
        try:
            locale_rows[locale] = _normalize_web_rows(_parse_table(_table_html(_fetch_html(url))), locale)
        except Exception as exc:
            if locale == PRIMARY_LOCALE:
                raise
            locale_fetch_errors.append({"locale": locale, "error": str(exc)})

    primary_rows = locale_rows[PRIMARY_LOCALE]
    locale_conflicts = _build_locale_conflicts(locale_rows)
    traceability = _source_traceability(doc_texts)
    if locale_fetch_errors:
        traceability["official_product_pages"]["fetch_warnings"] = locale_fetch_errors

    device_entries: list[dict[str, Any]] = []
    for device in sorted(primary_rows, key=_sort_key):
        web_entry = primary_rows[device]
        conflicts = locale_conflicts.get(device, [])
        package_summary = web_entry["package_summary"]
        package_io_banks = _package_io_block(device, web_entry, bank_info)
        device_record = {
            "_schema_version": "1.0",
            "_type": "fpga_package_capability",
            "_vendor": "Anlogic",
            "_family": "SALPHOENIX 1A",
            "_series": "PH1A",
            "_base_device": web_entry["base_device"],
            "device": device,
            "package": web_entry["package"],
            "ordering_suffix": web_entry["ordering_suffix"],
            "device_identity": {
                "vendor": "Anlogic",
                "family": "SALPHOENIX 1A",
                "series": "PH1A",
                "base_device": web_entry["base_device"],
                "device": device,
                "package": web_entry["package"],
            },
            "package_info": {
                "package_code": web_entry["package"],
                "package_body": package_summary["package_body"],
                "package_size_mm": package_summary["package_size_mm"],
                "ball_pitch_mm": package_summary["ball_pitch_mm"],
            },
            "resources": web_entry["resources"],
            "package_summary": package_summary,
            "package_io_banks": package_io_banks,
            "capability_blocks": {
                "configuration_modes": _configuration_modes_block(),
                "clock_distribution": _clock_distribution_block(device),
                "pll_resources": _pll_resources_block(device, web_entry),
                "io_sso": _io_sso_block(device, package_io_banks),
                "serdes_reference_clocking": _serdes_reference_clock_block(web_entry),
                "serdes_power_integrity": _serdes_power_integrity_block(web_entry),
                "memory_interface": _memory_interface_block(device, web_entry),
                "mipi_phy": _mipi_phy_block(device, web_entry),
                "high_speed_serial": _high_speed_serial_block(device, web_entry),
                "pcie": _pcie_block(device, bool(conflicts)),
            },
            "source_conflicts": conflicts,
            "source_traceability": {
                "official_product_page": {
                    "primary_locale": PRIMARY_LOCALE,
                    "locales_observed": sorted(locale_rows),
                    "source_url": PRODUCT_PAGES[PRIMARY_LOCALE],
                    "product_name": web_entry["product_name"],
                },
                "configuration": traceability["configuration_user_manual"],
                "pll": traceability["pll_user_manual"],
                "package_bank_distribution": traceability["io_user_manual"],
                "clock_resources": traceability["clock_user_manual"],
                "serdes": traceability["serdes_user_manual"],
                "pcie": traceability["pcie_user_manual"],
                "ddr": traceability["ddr_user_manual"],
                "sso_rules": traceability["sso_rules_report"],
                "mipi_and_hardware": traceability["hardware_design_guide"],
            },
        }
        device_entries.append(device_record)

    dataset = {
        "_schema_version": "1.0",
        "_type": "fpga_family_package_matrix",
        "_vendor": "Anlogic",
        "_family": "SALPHOENIX 1A",
        "_series": "PH1A",
        "family": "PH1A",
        "summary": _family_summary(device_entries, locale_conflicts),
        "source_traceability": traceability,
        "devices": device_entries,
    }
    return dataset


def write_outputs(dataset: dict[str, Any], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    family_path = output_dir / "family.json"
    family_path.write_text(json.dumps(dataset, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    written.append(family_path)

    for device_record in dataset["devices"]:
        out_path = output_dir / f"{_safe_slug(device_record['device'])}.json"
        out_path.write_text(json.dumps(device_record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(out_path)

    return written


def main() -> int:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUT_DIR
    dataset = build_dataset()
    written = write_outputs(dataset, output_dir)
    print(f"wrote {len(written)} files to {output_dir}")
    print(f"devices: {dataset['summary']['device_count']}")
    print("locale_conflicts:", ", ".join(dataset["summary"]["locale_conflict_devices"]) or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
