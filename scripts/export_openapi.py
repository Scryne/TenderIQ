"""FastAPI OpenAPI şemasını dosyaya yazar.

`packages/api-client` bu şemadan TypeScript istemcisi üretir; CI, üretilen
şema ile commit'lenen arasındaki drift'i kontrol eder (bkz. B.5).
"""

from __future__ import annotations

import json
from pathlib import Path

from tenderiq_api.main import create_app

OUTPUT_PATH = Path("packages/api-client/openapi.json")


def export_openapi(output: Path = OUTPUT_PATH) -> Path:
    """OpenAPI şemasını `output` dosyasına yazar ve yolu döndürür."""
    app = create_app()
    schema = app.openapi()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


if __name__ == "__main__":
    written = export_openapi()
    print(f"OpenAPI şeması yazıldı: {written}")
