#!/usr/bin/env bash
set -euo pipefail
ROOT="${HOME}/vigilancia"
OUT="${HOME}/entrega-work/dependencias"
mkdir -p "$OUT"
{
  date -Is
  uname -a
  cat /etc/os-release
  command -v python3 || true
  python3 --version || true
} > "$OUT/sistema.txt" 2>&1
for name in .venv .venv-ocr; do
  py="$ROOT/$name/bin/python"
  if [[ -x "$py" ]]; then
    "$py" --version > "$OUT/${name#.}-python.txt" 2>&1
    "$py" -m pip list --format=freeze > "$OUT/${name#.}-pip-freeze.txt" 2>&1 || true
    "$py" -m pip check > "$OUT/${name#.}-pip-check.txt" 2>&1 || true
  fi
done
python3 - "$ROOT" "$OUT" <<'PY'
from pathlib import Path
import ast, sys
root, out = map(Path, sys.argv[1:])
rows=[]
for path in sorted((root/'prototipo').rglob('*.py')):
    if any(p in {'.venv','.venv-ocr','__pycache__'} for p in path.parts):
        continue
    try:
        tree=ast.parse(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, SyntaxError):
        continue
    modules=set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split('.')[0])
    rows.append(f"{path.relative_to(root)}: {', '.join(sorted(modules))}")
(out/'imports_por_archivo.txt').write_text('\n'.join(rows)+'\n',encoding='utf-8')
PY
printf 'Inventario creado en: %s\n' "$OUT"
printf 'REVISA los archivos por URLs privadas/tokens antes de subirlos.\n'
