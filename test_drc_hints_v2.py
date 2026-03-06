"""
Phase 1 试验：drc_hints 语义模糊匹配
在 3 个测试器件上验证方法可靠性
"""
import json
import re
from pathlib import Path

# === 模糊匹配引擎 ===

def _find_params(elec_params: list, sym_patterns: list = None, desc_patterns: list = None, first_only=True) -> list:
    """
    从 electrical_characteristics 列表中模糊匹配参数。
    sym_patterns: 匹配 symbol 字段的正则列表
    desc_patterns: 匹配 parameter (描述) 字段的正则列表
    返回匹配到的参数列表
    """
    results = []
    
    for p in elec_params:
        sym = p.get('symbol') or ''
        desc = p.get('parameter') or ''
        matched = False
        
        if sym_patterns:
            for pat in sym_patterns:
                if re.match(pat, sym, re.IGNORECASE):
                    matched = True
                    break
        
        if not matched and desc_patterns:
            for pat in desc_patterns:
                if re.search(pat, desc, re.IGNORECASE):
                    matched = True
                    break
        
        if matched:
            results.append(p)
            if first_only:
                return results
    
    return results


def _first(params: list) -> dict | None:
    return params[0] if params else None


def _to_hint(p: dict, keys=('min','typ','max','unit')) -> dict:
    """把一个参数转成 drc_hint 格式"""
    return {k: p.get(k) for k in keys if p.get(k) is not None}


# === 提取规则定义 ===

RULES = {
    'vin_abs_max': {
        'source': 'abs_max',
        'sym': [r'^V[_\(]?IN', r'^VCC', r'^VDD'],
        'desc': [r'input.*volt', r'supply.*volt', r'voltage\s+at\s+pin.*VIN'],
        'extract': lambda p: {'value': p.get('max'), 'unit': p.get('unit', 'V')},
    },
    'vin_operating': {
        'sym': [r'^V[_\(]?IN', r'^VCC', r'^VDD'],
        'desc': [r'input.*volt.*range', r'input.*operat', r'supply.*volt.*range'],
        'extract': lambda p: _to_hint(p),
    },
    'vref': {
        'sym': [r'^V[_\(]?REF', r'^V[_\(]?FB', r'^VFEEDBACK'],
        'desc': [r'reference\s+volt', r'feedback.*volt', r'feedback.*regul'],
        'extract': lambda p: _to_hint(p),
    },
    'enable_threshold': {
        'sym': [r'^V.*EN', r'^VTH.*EN', r'^VIH.*EN', r'^VIL.*EN', r'^VIH$', r'^VIL$'],
        'desc': [r'enable.*thresh', r'enable.*volt.*ris', r'enable.*high', r'high.level\s+input\s+volt'],
        'extract': lambda p: _to_hint(p),
    },
    'iout_max': {
        'sym': [r'^I[_\(]?LIM', r'^I[_\(]?OUT', r'^I[_\(]?LOAD', r'^I[_\(]?OCL'],
        'desc': [r'current\s+limit', r'output\s+current', r'load\s+current', r'source\s+current\s+limit'],
        'extract': lambda p: _to_hint(p),
    },
    'iq': {
        'sym': [r'^I[_\(]?Q\b', r'^I[_\(]?GND', r'^I[_\(]?VDD.*S0', r'^IVDD\(S0\)'],
        'desc': [r'quiescent\s+curr', r'supply\s+curr.*operat', r'VDD\s+supply\s+curr'],
        'extract': lambda p: _to_hint(p),
    },
    'fsw': {
        'sym': [r'^f[_\(]?SW', r'^F[_\(]?OSC', r'^f[_\(]?CLK'],
        'desc': [r'switch.*freq', r'oscillat.*freq', r'PWM.*freq'],
        'extract': lambda p: _to_hint(p),
    },
    'soft_start': {
        'sym': [r'^t[_\(]?SS', r'^I[_\(]?SS'],
        'desc': [r'soft.?start\s+time', r'soft.?start\s+charge'],
        'extract': lambda p: _to_hint(p),
    },
    'thermal_shutdown': {
        'sym': [r'^T[_\(]?SD', r'^TJ[_\(]?SD', r'^T[_\(]?OTP'],
        'desc': [r'thermal\s+shut', r'over.?temp.*protect'],
        'extract': lambda p: _to_hint(p),
    },
    'thermal_resistance': {
        'sym': [r'^[θR].*JA', r'^RθJA'],
        'desc': [r'junction.to.ambient', r'thermal\s+resist'],
        'extract': lambda p: _to_hint(p),
    },
    'uvlo': {
        'sym': [r'^V.*UVLO', r'^V.*UVP'],
        'desc': [r'under.?volt.*lock', r'UVLO.*thresh.*ris'],
        'extract': lambda p: _to_hint(p),
    },
    'vout': {
        'sym': [r'^V[_\(]?OUT'],
        'desc': [r'^output\s+volt.*range', r'^output\s+volt.*accur'],
        'extract': lambda p: _to_hint(p),
    },
}


def extract_drc_hints_v2(extraction: dict) -> dict:
    """Phase 1 试验：语义模糊匹配提取 drc_hints"""
    elec = extraction.get('electrical_characteristics', [])
    abs_max = extraction.get('absolute_maximum_ratings', [])
    hints = {}
    
    for hint_name, rule in RULES.items():
        source = abs_max if rule.get('source') == 'abs_max' else elec
        sym_pats = rule.get('sym', [])
        desc_pats = rule.get('desc', [])
        first_only = hint_name not in ('thermal_resistance',)  # some may want multiple
        
        matches = _find_params(source, sym_pats, desc_pats, first_only=first_only)
        if matches:
            p = matches[0]
            hint_val = rule['extract'](p)
            if any(v is not None for v in hint_val.values()):
                hints[hint_name] = hint_val
                hints[hint_name]['_matched'] = f"{p.get('symbol','?')} | {p.get('parameter','?')}"
    
    return hints


# === 测试 ===

TEST_FILES = {
    'RT6365 (DCDC Buck)': 'data/extracted_v2/0130-01-00049_RT6365GSP.json',
    'TPS62085 (DCDC Buck)': 'data/extracted_v2/0130-01-00016_TPS62085RLTR.json',
    'TPS51206 (DDR VTT)': 'data/extracted_v2/0130-01-00014_TPS51206DSQR.json',
}


def main():
    for label, path in TEST_FILES.items():
        with open(path) as f:
            d = json.load(f)
        ext = d['extraction']
        hints = extract_drc_hints_v2(ext)

        print(f'\n{"="*60}')
        print(f'{label} — {ext["component"]["mpn"]}')
        print(f'{"="*60}')

        for k, v in hints.items():
            matched = v.pop('_matched', '')
            print(f'  ✅ {k}: {v}')
            print(f'     ← {matched}')

        all_rules = set(RULES.keys())
        matched_rules = set(hints.keys())
        missing = all_rules - matched_rules
        if missing:
            print(f'  ❌ Not found: {", ".join(sorted(missing))}')


if __name__ == '__main__':
    main()
