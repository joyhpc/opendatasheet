#!/usr/bin/env python3
"""Parse Gowin GW5AT-15 Pinout PDF into structured JSON.

The UG1224 PDF has Pin List tables where each pin entry spans multiple lines.
Uses PyMuPDF text extraction with position-based grouping.

Output: Same schema as parse_gowin_pinout.py (multi-layer FPGA pin definition).
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    import fitz
except ImportError:
    print("pip install PyMuPDF")
    sys.exit(1)

PDF_PATH = Path(__file__).parent.parent / "data/raw/fpga/gowin/高云 FPGA/UG1224-1.2_GW5AT-15器件Pinout手册.pdf"
OUTPUT_DIR = Path(__file__).parent.parent / "data/extracted_v2/fpga/pinout"

# Page ranges for each section (1-indexed from TOC)
SECTIONS = {
    "Pin Definitions": (2, 6),
    "Bank": (7, 7),
    "Power": (8, 8),
    "Pin List MG132": (9, 13),
    "Pin List CS130": (14, 18),
    "Pin List CS130F": (19, 23),
    "TrueLVDS MG132": (24, 26),
    "TrueLVDS CS130": (27, 29),
    "TrueLVDS CS130F": (30, 32),
}


def extract_positioned_text(doc, page_num):
    """Extract text with X,Y positions from a page."""
    page = doc[page_num]
    blocks = page.get_text('dict')['blocks']
    spans = []
    for b in blocks:
        if 'lines' in b:
            for line in b['lines']:
                for span in line['spans']:
                    t = span['text'].strip()
                    if t:
                        spans.append({
                            'x': round(span['origin'][0], 1),
                            'y': round(span['origin'][1], 1),
                            'text': t,
                            'size': span['size'],
                        })
    return spans


def parse_pin_list_pages(doc, start_page, end_page):
    """Parse Pin List table from PDF pages.

    The table has columns: 管脚名称, 功能, BANK, ADC_INPUT, DQS, 配置功能, 差分Pair, LVDS, Pin#, IO上下拉状态
    Each pin entry may span 2-4 lines due to long pin names.
    """
    pins = []

    for pg in range(start_page - 1, end_page):  # Convert to 0-indexed
        spans = extract_positioned_text(doc, pg)
        if not spans:
            continue

        # Group spans by Y position (within 3px tolerance)
        rows = defaultdict(list)
        for s in spans:
            y_key = round(s['y'] / 3) * 3
            rows[y_key].append(s)

        # Sort rows by Y, and each row by X
        sorted_ys = sorted(rows.keys())
        for y in sorted_ys:
            rows[y].sort(key=lambda s: s['x'])

        # Identify column positions from header row
        # Header: 管脚名称 | 功能 | BANK | ADC_INPUT | DQS | 配置功能 | 差分Pair | LVDS | MG132/CS130 | 配置过程中的IO上下拉状态
        # We'll use X position ranges to classify columns

        # Process rows to extract pin entries
        # A pin entry starts with an IO name like IOB11A, IOL33A, etc.
        # or power/config pins like VCC, VSS, MODE0, etc.
        current_pin = None

        for y in sorted_ys:
            row = rows[y]
            row_text = ' '.join(s['text'] for s in row)

            # Skip headers and footers
            if any(k in row_text for k in ['管脚名称', '功能', 'BANK', 'GW5AT系列',
                                            'GW5AT-15器件', 'Pin List', '注！', '[1]']):
                if current_pin:
                    pins.append(current_pin)
                    current_pin = None
                continue

            # Check if this row starts a new pin entry
            first_text = row[0]['text'] if row else ''
            first_x = row[0]['x'] if row else 999

            # Pin names start at the leftmost column (x < 100) and match patterns
            is_new_pin = False
            if first_x < 100:
                if re.match(r'^IO[BTLR]\d', first_text):
                    is_new_pin = True
                elif re.match(r'^(VCC|VSS|VDDP|VDDQP|NC|MODE|DONE|READY|RECONFIG|JTAGSEL|TCK|TDI|TDO|TMS|MSPI|SSPI|Q0_|M0_|VDDH|VDDA|VDDD|VDDT|MIPI)', first_text):
                    is_new_pin = True

            if is_new_pin:
                # Save previous pin
                if current_pin:
                    pins.append(current_pin)

                # Start new pin
                current_pin = {
                    'name': first_text,
                    'function': '',
                    'bank': '',
                    'dqs': '',
                    'config_function': '',
                    'diff_pair': '',
                    'lvds': '',
                    'pin_number': '',
                    'pull_state': '',
                }

                # Parse remaining columns by X position
                # Actual column X positions from PDF:
                # 管脚名称:~53, 功能:~204, BANK:~249, ADC_INPUT:~289,
                # DQS:~355, 配置功能:~398, 差分Pair:~529, LVDS:~622,
                # Pin#:~663, Pull state:~717
                for s in row[1:]:
                    x = s['x']
                    t = s['text']

                    if x < 190:  # Still part of pin name (multi-line)
                        current_pin['name'] += t
                    elif x < 240:  # 功能 column (~204)
                        current_pin['function'] = t
                    elif x < 280:  # BANK column (~249)
                        if t.isdigit():
                            current_pin['bank'] = t
                    elif x < 350:  # ADC_INPUT (~289)
                        if 'bus' in t:
                            current_pin['dqs'] = t
                    elif x < 390:  # DQS (~355)
                        if 'DQ' in t:
                            current_pin['dqs'] = t
                    elif x < 520:  # 配置功能 (~398)
                        current_pin['config_function'] = t
                    elif x < 610:  # 差分Pair (~529)
                        if 'True_of' in t or 'Comp_of' in t:
                            current_pin['diff_pair'] = t
                        elif t == 'none':
                            current_pin['diff_pair'] = 'none'
                    elif x < 655:  # LVDS (~622)
                        if t in ('True', 'Comp', 'none'):
                            current_pin['lvds'] = t
                    elif x < 710:  # Pin number (~663)
                        if re.match(r'^[A-R]\d{1,2}$', t):
                            current_pin['pin_number'] = t
                    else:  # Pull state (~717)
                        if 'pull' in t or 'none' in t:
                            current_pin['pull_state'] = t

            elif current_pin:
                # Continuation of current pin entry
                for s in row:
                    x = s['x']
                    t = s['text']

                    if x < 190:
                        # Continuation of pin name
                        if not current_pin['name'].endswith(t):
                            current_pin['name'] += '/' + t if not current_pin['name'].endswith('/') else t
                    elif x < 240:
                        if not current_pin['function']:
                            current_pin['function'] = t
                    elif x < 280:
                        if t.isdigit() and not current_pin['bank']:
                            current_pin['bank'] = t
                    elif x < 390:
                        if ('DQ' in t or 'bus' in t) and not current_pin['dqs']:
                            current_pin['dqs'] = t
                    elif x < 520:
                        if not current_pin['config_function']:
                            current_pin['config_function'] = t
                        else:
                            current_pin['config_function'] += '/' + t
                    elif x < 610:
                        if ('True_of' in t or 'Comp_of' in t) and not current_pin['diff_pair']:
                            current_pin['diff_pair'] = t
                    elif x < 655:
                        if t in ('True', 'Comp', 'none') and not current_pin['lvds']:
                            current_pin['lvds'] = t
                    elif x < 710:
                        if re.match(r'^[A-R]\d{1,2}$', t) and not current_pin['pin_number']:
                            current_pin['pin_number'] = t
                    else:
                        if ('pull' in t or 'none' in t) and not current_pin['pull_state']:
                            current_pin['pull_state'] = t

    # Don't forget the last pin
    if current_pin:
        pins.append(current_pin)

    return pins


def parse_power_page(doc, page_num):
    """Parse Power supply info from the Power page."""
    spans = extract_positioned_text(doc, page_num - 1)
    power_rails = {}

    rows = defaultdict(list)
    for s in spans:
        y_key = round(s['y'] / 3) * 3
        rows[y_key].append(s)

    for y in sorted(rows.keys()):
        row = rows[y]
        row.sort(key=lambda s: s['x'])
        row_text = ' '.join(s['text'] for s in row)

        # Look for power rail definitions
        for s in row:
            t = s['text']
            if re.match(r'^(VCC|VDD|VQPS|M0_)', t):
                rail_name = t
                # Find voltage values in the same row
                voltages = []
                for s2 in row:
                    v = re.search(r'(\d+\.?\d*)\s*V', s2['text'])
                    if v:
                        voltages.append(float(v.group(1)))
                desc = ' '.join(s2['text'] for s2 in row if s2['x'] > s['x'] and not re.match(r'^\d', s2['text']))
                power_rails[rail_name] = {
                    'description': desc.strip(),
                    'min_voltage': voltages[0] if len(voltages) >= 1 else None,
                    'max_voltage': voltages[1] if len(voltages) >= 2 else voltages[0] if voltages else None,
                }
                break

    return power_rails


def parse_lvds_pages(doc, start_page, end_page):
    """Parse TrueLVDS pair definitions."""
    pairs = []

    for pg in range(start_page - 1, end_page):
        spans = extract_positioned_text(doc, pg)
        rows = defaultdict(list)
        for s in spans:
            y_key = round(s['y'] / 3) * 3
            rows[y_key].append(s)

        for y in sorted(rows.keys()):
            row = rows[y]
            row.sort(key=lambda s: s['x'])
            row_text = ' '.join(s['text'] for s in row)

            # LVDS pairs: True pin name + Comp pin name + pin numbers
            if 'True_of' in row_text or 'IOB' in row_text or 'IOL' in row_text or 'IOR' in row_text or 'IOT' in row_text:
                pin_names = [s['text'] for s in row if re.match(r'^IO[BTLR]\d', s['text'])]
                pin_nums = [s['text'] for s in row if re.match(r'^[A-R]\d{1,2}$', s['text'])]
                if len(pin_names) >= 2 and len(pin_nums) >= 2:
                    pairs.append({
                        'true_name': pin_names[0],
                        'comp_name': pin_names[1],
                        'true_pin': pin_nums[0],
                        'comp_pin': pin_nums[1],
                    })

    return pairs


def build_output(device, package, pins, power_rails, lvds_pairs):
    """Build the standard FPGA pinout JSON output."""
    # Classify pins
    by_function = defaultdict(int)
    banks = defaultdict(lambda: {'pins': [], 'io_count': 0})

    pin_list = []
    lookup_by_pin = {}
    lookup_by_name = {}

    for p in pins:
        func = p['function']
        name = p['name']
        pin_num = p['pin_number']
        bank = p['bank']

        # Classify
        if 'VSS' in name or 'GND' in name:
            category = 'GROUND'
        elif 'VCC' in name or 'VDD' in name or 'VQPS' in name:
            category = 'POWER'
        elif func == 'I/O':
            category = 'IO'
        elif 'Q0_' in name:
            if 'RX' in name:
                category = 'SERDES_RX'
            elif 'TX' in name:
                category = 'SERDES_TX'
            elif 'REFCLK' in name:
                category = 'SERDES_REFCLK'
            else:
                category = 'SERDES'
        elif 'MIPI' in name or 'M0_' in name:
            category = 'MIPI'
        elif 'NC' in name:
            category = 'NC'
        else:
            category = 'OTHER'

        by_function[category] += 1

        pin_entry = {
            'pin': pin_num,
            'name': name,
            'function': func,
            'category': category,
            'bank': bank,
            'dqs_group': p.get('dqs', ''),
            'config_function': p.get('config_function', ''),
            'diff_pair': p.get('diff_pair', ''),
            'lvds': p.get('lvds', ''),
            'pull_state': p.get('pull_state', ''),
        }
        pin_list.append(pin_entry)

        if pin_num:
            lookup_by_pin[pin_num] = name
            lookup_by_name[name] = pin_num

        if bank and func == 'I/O':
            banks[bank]['pins'].append(pin_num)
            banks[bank]['io_count'] += 1

    # Build diff pairs from LVDS data
    diff_pairs = []
    for pair in lvds_pairs:
        diff_pairs.append({
            'type': 'IO',
            'true_name': pair['true_name'],
            'comp_name': pair['comp_name'],
            'true_pin': pair['true_pin'],
            'comp_pin': pair['comp_pin'],
        })

    # DRC rules
    drc_rules = {
        'power_integrity': {'description': 'All power pins must be connected to correct voltage rail', 'severity': 'critical'},
        'ground_integrity': {'description': 'All VSS pins must be connected to ground', 'severity': 'critical'},
        'config_pins': {'description': 'MODE0/1/2, DONE, READY, RECONFIG_N must be properly connected', 'severity': 'critical'},
        'unused_io': {'description': 'Unused IO pins should be left unconnected or tied to ground via resistor', 'severity': 'warning'},
        'vcco_consistency': {'description': 'All VCCIO pins in same bank must connect to same voltage', 'severity': 'critical'},
        'diff_pair_integrity': {'description': 'Both pins of a differential pair must be used together', 'severity': 'warning'},
    }

    result = {
        '_schema_version': '2.0',
        '_purpose': 'FPGA pin definition for LLM-driven schematic DRC',
        '_vendor': 'Gowin',
        'device': device,
        'package': package,
        'source_file': 'UG1224-1.2_GW5AT-15器件Pinout手册.pdf',
        'total_pins': len(pin_list),
        'summary': {
            'by_function': dict(by_function),
            'diff_pairs': {
                'IO': len([p for p in diff_pairs if p['type'] == 'IO']),
            },
        },
        'power_rails': power_rails,
        'banks': {k: v for k, v in banks.items()},
        'diff_pairs': diff_pairs,
        'drc_rules': drc_rules,
        'pins': pin_list,
        'lookup': {
            'by_pin': lookup_by_pin,
            'by_name': lookup_by_name,
        },
    }

    return result


def parse_gowin_pdf_pinout(filepath):
    """Parse supported Gowin PDF pinout manuals.

    Returns a list of ``(package, data)`` tuples so ``scripts/parse_pinout.py``
    can keep a stable interface across single- and multi-package manuals.
    """
    filepath = Path(filepath)
    doc = fitz.open(str(filepath))
    try:
        stem = filepath.stem

        if "GW5AT-15" in stem or "UG1224" in stem:
            power_rails = parse_power_page(doc, 8)
            package_specs = [
                ("MG132", (9, 13), (24, 26)),
                ("CS130", (14, 18), (27, 29)),
                ("CS130F", (19, 23), (30, 32)),
            ]
            device = "GW5AT-15"
        else:
            raise ValueError(
                f"Unsupported Gowin PDF pinout manual: {filepath.name}; "
                "use the XLSX pinout manuals for GW1N/GW2A families or add a family-specific PDF parser first."
            )

        results = []
        for pkg_name, pin_pages, lvds_pages in package_specs:
            pins = parse_pin_list_pages(doc, pin_pages[0], pin_pages[1])
            lvds_pairs = parse_lvds_pages(doc, lvds_pages[0], lvds_pages[1])
            result = build_output(device, pkg_name, pins, power_rails, lvds_pairs)
            result["source_file"] = filepath.name
            results.append((pkg_name, result))
        return results
    finally:
        doc.close()


def main():
    doc = fitz.open(str(PDF_PATH))
    print(f"Parsing {PDF_PATH.name} ({doc.page_count} pages)")

    # Parse power info
    power_rails = parse_power_page(doc, 8)
    print(f"  Power rails: {len(power_rails)}")

    device = 'GW5AT-15'

    # Parse each package
    packages = [
        ('MG132', (9, 13), (24, 26)),
        ('CS130', (14, 18), (27, 29)),
        ('CS130F', (19, 23), (30, 32)),
    ]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for pkg_name, pin_pages, lvds_pages in packages:
        print(f"\n  === {pkg_name} ===")
        pins = parse_pin_list_pages(doc, pin_pages[0], pin_pages[1])
        print(f"  Raw pins extracted: {len(pins)}")

        lvds_pairs = parse_lvds_pages(doc, lvds_pages[0], lvds_pages[1])
        print(f"  LVDS pairs: {len(lvds_pairs)}")

        result = build_output(device, pkg_name, pins, power_rails, lvds_pairs)

        out_path = OUTPUT_DIR / f"gowin_gw5at-15_{pkg_name.lower()}.json"
        with open(out_path, 'w') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"  Total pins: {result['total_pins']}")
        print(f"  By function: {result['summary']['by_function']}")
        print(f"  → {out_path}")

    doc.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
