"""Genera la versión estática de la demo (sin servidor) para GitHub Pages.

Uso:  python scripts/build_static.py [carpeta_salida]   (por defecto: _site)
La web resultante usa static/mock-api.js en lugar de la API en Python.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site"

# Base de datos temporal: no toca data/demo.db
os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp()) / "static.db")
sys.path.insert(0, str(ROOT))

from app import catalogos as cat  # noqa: E402
from app.db import connect  # noqa: E402
from app.seed import generar  # noqa: E402

generar()
conn = connect()
data = {
    "generado": date.today().isoformat(),
    "catalogos": {
        "escuelas": list(cat.ESCUELAS), "origenes": cat.ORIGENES, "motivos": cat.MOTIVOS,
        "estados": cat.ESTADOS, "acciones": cat.ACCIONES, "agentes": cat.AGENTES,
    },
    "pedidos": [dict(r) for r in conn.execute("SELECT * FROM pedidos ORDER BY np")],
    "solicitudes": [dict(r) for r in conn.execute("SELECT * FROM solicitudes ORDER BY id")],
}
conn.close()

if OUT.exists():
    shutil.rmtree(OUT)
shutil.copytree(ROOT / "static", OUT / "static")
(OUT / "static" / "demo-data.js").write_text(
    "window.DEMO_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n",
    encoding="utf-8",
)

html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
app_tag = '<script src="static/app.js" defer></script>'
assert app_tag in html, "index.html ha cambiado: revisa la etiqueta de app.js"
html = html.replace(
    app_tag,
    '<script src="static/demo-data.js" defer></script>\n'
    '  <script src="static/mock-api.js" defer></script>\n  ' + app_tag,
)
csp = ("default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com; style-src 'self'; "
       "img-src 'self' data:; connect-src 'self'")
html = html.replace('<meta charset="utf-8">',
                    f'<meta charset="utf-8">\n  <meta http-equiv="Content-Security-Policy" content="{csp}">')
(OUT / "index.html").write_text(html, encoding="utf-8")
(OUT / ".nojekyll").write_text("")
print(f"Web estática en {OUT}: {len(data['pedidos'])} pedidos, {len(data['solicitudes'])} solicitudes")
