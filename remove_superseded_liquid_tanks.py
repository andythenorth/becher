"""Optional, narrowly scoped deletion of superseded generated tank assemblies.

Run after applying v4 overlay. Deletes only names from the earlier generated
catalogues if they are no longer referenced by *any* vocabulary.
Does not remove custom components with unrelated names.
"""
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parent / 'data' / 'assemblies'
vocab = json.loads((root / 'vocabularies.json').read_text())
active = {name for category in vocab.values() for names in category.values() for name in names}
patterns = (
    re.compile(r'storage_(?:vertical|domed|conical|squat|slender|twin)_(?:low|high)_0[1-4]'),
    re.compile(r'storage_tank_(?:small|medium|large|service)_(?:low|high)_0[1-4]'),
    re.compile(r'storage_tank_(?:pair|quad)_(?:low|high)_0[1-3]'),
    re.compile(r'storage_tank_horizontal_(?:low|high)_0[1-4]'),
    re.compile(r'storage_tank_horizontal_pair_(?:low|high)_0[1-2]'),
    re.compile(r'storage_tank_horizontal_stack_(?:low|high)_0[1-2]'),
)
removed = []
for path in root.glob('*.json'):
    if path.stem not in active and any(p.fullmatch(path.stem) for p in patterns):
        path.unlink()
        removed.append(path.name)
print(f'Removed {len(removed)} superseded generated tank component files.')
