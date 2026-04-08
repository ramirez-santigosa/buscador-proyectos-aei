"""
Sube data/proyectos.db a GitHub Releases como asset de descarga.

Uso:
    python scripts/upload_db.py --token ghp_TU_TOKEN [--tag v1.0]

El script:
  1. Crea o actualiza un release con el tag indicado (defecto: "data-latest").
  2. Sube data/proyectos.db como asset del release.
  3. Imprime la URL de descarga directa para copiarla en entrypoint.py o HF Spaces.

Requisito: genera el token en GitHub → Settings → Developer settings →
           Personal access tokens → Fine-grained, con permiso "Contents: write"
           sobre este repositorio.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO      = "ramirez-santigosa/buscador-proyectos-aei"
DB_PATH   = Path(__file__).resolve().parents[1] / "data" / "proyectos.db"
API_BASE  = "https://api.github.com"
UPLOAD_BASE = "https://uploads.github.com"


def _req(method, url, token, data=None, headers=None, content_type="application/json"):
    h = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": content_type,
    }
    if headers:
        h.update(headers)
    body = json.dumps(data).encode() if data is not None and content_type == "application/json" else data
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")
        print(f"HTTP {e.code}: {msg}")
        raise


def obtener_o_crear_release(token, tag):
    """Devuelve el release existente con ese tag, o lo crea."""
    url_get = f"{API_BASE}/repos/{REPO}/releases/tags/{tag}"
    try:
        return _req("GET", url_get, token)
    except urllib.error.HTTPError:
        pass  # no existe, lo creamos

    print(f"  Creando release '{tag}'...")
    url_post = f"{API_BASE}/repos/{REPO}/releases"
    return _req("POST", url_post, token, data={
        "tag_name":    tag,
        "name":        f"Base de datos ({tag})",
        "body":        "Asset generado automáticamente por scripts/upload_db.py.\n"
                       "Contiene data/proyectos.db (SQLite con 54 823 proyectos AEI desde 2018).",
        "draft":       False,
        "prerelease":  False,
    })


def eliminar_asset_existente(token, release_id, nombre_asset):
    """Elimina el asset si ya existe (para poder re-subir)."""
    assets_url = f"{API_BASE}/repos/{REPO}/releases/{release_id}/assets"
    assets = _req("GET", assets_url, token)
    for asset in assets:
        if asset["name"] == nombre_asset:
            del_url = f"{API_BASE}/repos/{REPO}/releases/assets/{asset['id']}"
            _req("DELETE", del_url, token)
            print(f"  Asset anterior '{nombre_asset}' eliminado.")
            return


def subir_asset(token, upload_url, db_path):
    """Sube el fichero como asset del release."""
    # upload_url viene con {?name,label} al final → eliminarlo
    base_url = upload_url.split("{")[0]
    url = f"{base_url}?name={db_path.name}"
    size_mb = db_path.stat().st_size / 1_048_576
    print(f"  Subiendo {db_path.name} ({size_mb:.1f} MB) — puede tardar varios minutos...")

    with open(db_path, "rb") as f:
        data = f.read()

    result = _req(
        "POST", url, token,
        data=data,
        content_type="application/octet-stream",
    )
    return result["browser_download_url"]


def main():
    parser = argparse.ArgumentParser(description="Sube proyectos.db a GitHub Releases.")
    parser.add_argument("--token", required=True, help="GitHub personal access token")
    parser.add_argument("--tag",   default="data-latest", help="Tag del release (defecto: data-latest)")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} no existe. Ejecuta primero: python scripts/build_db.py")
        sys.exit(1)

    print(f"Repositorio : {REPO}")
    print(f"Tag         : {args.tag}")
    print(f"Fichero     : {DB_PATH}  ({DB_PATH.stat().st_size / 1_048_576:.1f} MB)")
    print()

    release = obtener_o_crear_release(args.token, args.tag)
    release_id = release["id"]
    print(f"  Release ID: {release_id}  |  {release['html_url']}")

    eliminar_asset_existente(args.token, release_id, DB_PATH.name)

    url_descarga = subir_asset(args.token, release["upload_url"], DB_PATH)

    print(f"\n✓ Asset disponible en:")
    print(f"  {url_descarga}")
    print(f"\nURL para entrypoint.py / HF Spaces:")
    print(f"  https://github.com/{REPO}/releases/latest/download/{DB_PATH.name}")


if __name__ == "__main__":
    main()
