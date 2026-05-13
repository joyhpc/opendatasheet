import ast

def analyze(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
        
    classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
    print(f"Classes in {filename}: {classes}")

analyze('scripts/export_design_bundle.py')
analyze('scripts/normal_ic_bundle_service.py')
