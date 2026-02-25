#!/usr/bin/env python3
"""Parse Gowin GW5AT-60 development board schematic PDF.

Extracts power topology, configuration circuits, and key design info
from the DK_START_GW5AT-LV60UG225 schematic PDF using text labels.

Output: Structured JSON for reference design documentation.
"""

import json
import re
from collections import defaultdict
from pathlib import Path

try:
    import fitz
except ImportError:
    print("pip install PyMuPDF")
    exit(1)

SCH_PDF = Path(__file__).parent.parent / "data/raw/fpga/gowin/高云 FPGA/DK_START_GW5AT-LV60UG225_V1.1_SCH.pdf"
OUTPUT = Path(__file__).parent.parent / "data/extracted_v2/fpga/gowin_gw5at60_devboard_ref.json"


def extract_page_texts(doc, pg_num):
    """Extract all text spans with position from a page."""
    page = doc[pg_num]
    blocks = page.get_text('dict')['blocks']
    texts = []
    for b in blocks:
        if 'lines' in b:
            for line in b['lines']:
                for span in line['spans']:
                    t = span['text'].strip()
                    if t and len(t) >= 1:
                        texts.append({
                            'x': span['origin'][0],
                            'y': span['origin'][1],
                            'text': t,
                            'size': span['size'],
                        })
    return texts


def extract_power_topology(doc):
    """Extract power supply topology from pages 3-5, 7."""
    power_rails = {}
    regulators = []
    decoupling = defaultdict(list)

    for pg in [2, 3, 4, 6]:  # 0-indexed: pages 3,4,5,7
        texts = extract_page_texts(doc, pg)
        all_text = ' '.join(t['text'] for t in texts)

        # Find regulator descriptions: "12V to 3.3V/6A"
        for m in re.finditer(r'(\d+\.?\d*V)\s+to\s+(\d+\.?\d*V)/(\d+\.?\d*A)', all_text):
            vin, vout, imax = m.groups()
            regulators.append({
                'input': vin,
                'output': vout,
                'max_current': imax,
                'page': pg + 1,
            })

        # Find voltage rail names
        for t in texts:
            txt = t['text']
            # Match rail names like VCC3P3, VCC1P8, V0P95-1, etc.
            if re.match(r'^(VCC\d|V\d|VDD|VDDA|VDDD|VDDHA|VDDX)', txt):
                rail = txt
                if rail not in power_rails:
                    power_rails[rail] = {'name': rail, 'pages': set()}
                power_rails[rail]['pages'].add(pg + 1)

        # Find IC part numbers
        for t in texts:
            txt = t['text']
            if re.match(r'^(TPS|LT|RT|AMS|SGM|MP|NCP|XL|ISL|IR|MIC)', txt):
                # Look for nearby voltage context
                regulators.append({
                    'part': txt,
                    'page': pg + 1,
                })

        # Find decoupling caps
        for t in texts:
            txt = t['text']
            if re.match(r'^C\d+$', txt):
                decoupling[pg + 1].append(txt)

    # Convert sets to lists for JSON
    for rail in power_rails.values():
        rail['pages'] = sorted(rail['pages'])

    return {
        'regulators': regulators,
        'power_rails': {k: v for k, v in power_rails.items()},
        'decoupling_caps_per_page': {str(k): len(v) for k, v in decoupling.items()},
    }


def extract_fpga_power_pins(doc):
    """Extract FPGA power pin assignments from page 7."""
    texts = extract_page_texts(doc, 6)  # Page 7

    # Group by Y position to reconstruct rows
    rows = defaultdict(list)
    for t in texts:
        y_key = round(t['y'] / 5) * 5
        rows[y_key].append(t)

    # Sort each row by X
    for y in rows:
        rows[y].sort(key=lambda t: t['x'])

    pin_assignments = []
    current_voltage = None

    for y in sorted(rows.keys()):
        row_texts = [t['text'] for t in rows[y]]
        row_str = ' '.join(row_texts)

        # Detect voltage labels
        for t in rows[y]:
            if re.match(r'^\d+\.?\d*V$', t['text']):
                current_voltage = t['text']

        # Detect pin assignments: pin_number + function
        for t in rows[y]:
            # Pin numbers like A1, B12, G8, etc.
            if re.match(r'^[A-R]\d{1,2}$', t['text']):
                pin = t['text']
                # Find the function name nearby (next text in row)
                idx = rows[y].index(t)
                func = None
                for j in range(idx + 1, min(idx + 3, len(rows[y]))):
                    candidate = rows[y][j]['text']
                    if re.match(r'^(VCC|VCCIO|VCCX|Q0_|M0_|MIPI|VSS|VDDH|VQPS)', candidate):
                        func = candidate
                        break
                if func:
                    pin_assignments.append({
                        'pin': pin,
                        'function': func,
                        'voltage': current_voltage,
                    })

    return pin_assignments


def extract_fpga_config(doc):
    """Extract FPGA configuration circuit from page 6."""
    texts = extract_page_texts(doc, 5)  # Page 6
    all_text = ' '.join(t['text'] for t in texts if t['size'] > 4)

    config_signals = []
    for t in texts:
        txt = t['text']
        # Configuration signals
        if any(k in txt for k in ['MSPI', 'F_MODE', 'F_DONE', 'F_READY', 'F_RECONFIG',
                                    'F_TCK', 'F_TDI', 'F_TDO', 'F_TMS', 'F_KEY',
                                    'F_CLK', 'F_GPIO']):
            config_signals.append(txt)

    # Flash info
    flash_info = []
    for t in texts:
        if 'Flash' in t['text'] or 'CLK' in t['text']:
            flash_info.append(t['text'])

    return {
        'config_signals': sorted(set(config_signals)),
        'flash_related': sorted(set(flash_info)),
    }


def extract_interfaces(doc):
    """Extract interface circuits from pages 8-11."""
    interfaces = {}

    # Page 8: DDR3
    texts = extract_page_texts(doc, 7)
    ddr_parts = []
    for t in texts:
        if 'DDR3' in t['text'] or 'W632' in t['text']:
            ddr_parts.append(t['text'])
    interfaces['DDR3'] = {
        'page': 8,
        'components': sorted(set(ddr_parts)),
        'power_rails': ['VCC1P5', 'DDRVTT', 'VTTREF'],
    }

    # Page 9: DisplayPort
    texts = extract_page_texts(doc, 8)
    dp_signals = []
    dp_parts = []
    for t in texts:
        if 'DP_' in t['text']:
            dp_signals.append(t['text'])
        if re.match(r'^(FDL|TPES|RClamp|U\d+)', t['text']):
            dp_parts.append(t['text'])
    interfaces['DisplayPort'] = {
        'page': 9,
        'signals': sorted(set(dp_signals)),
        'components': sorted(set(dp_parts)),
        'connector': 'Type-C',
    }

    # Page 10: MIPI + GPIO
    texts = extract_page_texts(doc, 9)
    mipi_signals = []
    for t in texts:
        if any(k in t['text'] for k in ['CPHY', 'DPHY', 'MIPI']):
            mipi_signals.append(t['text'])
    interfaces['MIPI'] = {
        'page': 10,
        'signals': sorted(set(mipi_signals)),
    }

    # Page 11: JTAG
    texts = extract_page_texts(doc, 10)
    jtag_parts = []
    for t in texts:
        if any(k in t['text'] for k in ['FT232', 'TPD2E', 'JTAG', 'USB']):
            jtag_parts.append(t['text'])
    interfaces['JTAG'] = {
        'page': 11,
        'components': sorted(set(jtag_parts)),
        'usb_bridge': 'FT232HQ',
    }

    return interfaces


def extract_decoupling_strategy(doc):
    """Extract decoupling capacitor strategy from FPGA power page."""
    texts = extract_page_texts(doc, 6)  # Page 7

    # Group caps by rail
    cap_groups = defaultdict(list)
    current_rail = None

    # Sort by position
    texts.sort(key=lambda t: (round(t['y'] / 10) * 10, t['x']))

    for t in texts:
        txt = t['text']
        # Detect rail names
        if re.match(r'^(VCC|V\d|VDD)', txt) and t['size'] >= 5:
            current_rail = txt
        # Detect cap values
        if txt in ('100uF', '47uF', '10uF', '4.7uF', '1uF', '0.1uF', '100nF', '10nF', '22pF'):
            if current_rail:
                cap_groups[current_rail].append(txt)

    return dict(cap_groups)


def main():
    doc = fitz.open(str(SCH_PDF))
    print(f"Parsing {SCH_PDF.name} ({doc.page_count} pages)")

    # Page structure
    page_map = {
        1: "Cover Page / Table of Contents",
        2: "System Diagram",
        3: "Power - 12V Input + DC Jack",
        4: "Power - Buck Regulators (12V→3.3V/1.5V/1.2V/2.1V)",
        5: "Power - LDO/Secondary (0.95V cores, 1.8V SerDes, current sense)",
        6: "FPGA Config + Clock + Signal Routing",
        7: "FPGA Power Pins + Decoupling",
        8: "DDR3 Memory",
        9: "DisplayPort (Type-C)",
        10: "MIPI + GPIO + Bank IO",
        11: "JTAG (FT232HQ USB Bridge)",
    }

    # Extract all sections
    power = extract_power_topology(doc)
    fpga_pins = extract_fpga_power_pins(doc)
    config = extract_fpga_config(doc)
    interfaces = extract_interfaces(doc)
    decoupling = extract_decoupling_strategy(doc)

    result = {
        "_schema": "devboard-reference/1.0",
        "_board": "DK_START_GW5AT-LV60UG225 V1.1",
        "_fpga": "GW5AT-LV60UG225",
        "_date": "2024-06-17",
        "page_map": page_map,
        "power_topology": power,
        "fpga_power_pin_assignments": fpga_pins,
        "fpga_config": config,
        "interfaces": interfaces,
        "decoupling_strategy": decoupling,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=list)

    print(f"\nOutput: {OUTPUT}")
    print(f"  Power regulators: {len(power['regulators'])}")
    print(f"  Power rails: {len(power['power_rails'])}")
    print(f"  FPGA power pins: {len(fpga_pins)}")
    print(f"  Config signals: {len(config['config_signals'])}")
    print(f"  Interfaces: {list(interfaces.keys())}")
    print(f"  Decoupling groups: {len(decoupling)}")

    doc.close()


if __name__ == "__main__":
    main()
