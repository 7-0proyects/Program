"""Motor de validación y renombrado documental BIM.

La lógica está separada de la interfaz para facilitar pruebas y explicación.
"""
from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

REQUIRED_FIELDS = ["proyecto", "originador", "zona", "nivel", "tipo", "disciplina", "consecutivo"]

@dataclass
class Result:
    archivo: str
    nombre_propuesto: str
    estado: str
    detalle: str
    origen: str = ""

    def to_dict(self):
        return asdict(self)


def load_catalog(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_metadata(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "archivo" not in reader.fieldnames:
            raise ValueError("El CSV debe tener una columna llamada 'archivo'.")
        return [{(k or "").strip().lower(): (v or "").strip() for k, v in row.items()} for row in reader]


def _normal(value: str) -> str:
    return (value or "").strip().upper()


def _allowed(value: str, key: str, catalog: dict) -> bool:
    allowed = catalog.get("codigos", {}).get(key, [])
    return _normal(value) in {_normal(x) for x in allowed}


def build_name(meta: dict, extension: str, catalog: dict, include_revision: bool = False) -> tuple[str | None, str]:
    """Devuelve (nombre, error). No inventa metadatos ausentes."""
    missing = [field for field in REQUIRED_FIELDS if not _normal(meta.get(field, ""))]
    if include_revision and not _normal(meta.get("revision", "")):
        missing.append("revision")
    if missing:
        return None, "Faltan campos obligatorios: " + ", ".join(missing)

    for field in ("proyecto", "originador", "zona", "nivel", "tipo", "disciplina"):
        if not _allowed(meta[field], field, catalog):
            return None, f"Código no permitido para {field}: '{meta[field]}'"

    try:
        number = int(meta["consecutivo"])
    except (TypeError, ValueError):
        return None, "El consecutivo debe ser un número entero entre 1 y 9999."
    if not 1 <= number <= 9999:
        return None, "El consecutivo debe estar entre 1 y 9999."

    parts = [*[_normal(meta[x]) for x in ("proyecto", "originador", "zona", "nivel", "tipo", "disciplina")], f"{number:04d}"]
    if include_revision:
        revision = _normal(meta["revision"])
        if not _allowed(revision, "revision", catalog):
            return None, f"Código no permitido para revision: '{revision}'"
        parts.append(revision)
    # La extensión original se conserva; solo se normaliza el punto.
    ext = extension if extension.startswith(".") else f".{extension}"
    return "-".join(parts) + ext, ""


def validate(folder: Path, metadata: list[dict], catalog: dict, output_folder: Path | None = None,
             include_revision: bool = False) -> list[Result]:
    folder = Path(folder)
    output_folder = Path(output_folder) if output_folder else folder / "renombrados_BIM"
    if not folder.exists() or not folder.is_dir():
        raise ValueError("La carpeta de documentos no existe o no es válida.")

    files = {p.name.casefold(): p for p in folder.iterdir() if p.is_file() and p.suffix.lower() != ".csv"}
    rows_by_name: dict[str, list[dict]] = {}
    for row in metadata:
        rows_by_name.setdefault(row.get("archivo", "").casefold(), []).append(row)

    results: list[Result] = []
    # Registros repetidos en la tabla: se reportan todos, no se escoge uno arbitrariamente.
    for key, rows in rows_by_name.items():
        if len(rows) > 1:
            for row in rows:
                results.append(Result(row.get("archivo", ""), "", "BLOQUEADO", "El archivo aparece más de una vez en la tabla."))

    handled = set()
    for key, rows in rows_by_name.items():
        if len(rows) > 1:
            handled.add(key)
            continue
        row = rows[0]
        filename = row.get("archivo", "")
        source = files.get(key)
        if not source:
            results.append(Result(filename, "", "PENDIENTE", "El archivo está en la tabla, pero no existe en la carpeta."))
            handled.add(key)
            continue
        proposed, error = build_name(row, source.suffix, catalog, include_revision)
        if error:
            status = "PENDIENTE" if "Faltan campos" in error else "BLOQUEADO"
            results.append(Result(filename, "", status, error, str(source)))
        else:
            results.append(Result(filename, proposed, "POR VALIDAR", "Metadatos completos; falta revisar conflictos.", str(source)))
        handled.add(key)

    # Archivos que no tienen fila de metadatos.
    for key, source in files.items():
        if key not in handled:
            results.append(Result(source.name, "", "PENDIENTE", "El archivo no tiene registro en la tabla de metadatos.", str(source)))

    # Si dos archivos producen el mismo destino, ambos quedan bloqueados.
    candidates: dict[str, list[int]] = {}
    for i, item in enumerate(results):
        if item.estado == "POR VALIDAR":
            candidates.setdefault(item.nombre_propuesto.casefold(), []).append(i)
    for target_key, indexes in candidates.items():
        if len(indexes) > 1:
            for i in indexes:
                results[i].estado = "BLOQUEADO"
                results[i].detalle = "El mismo nombre de destino se repite; se bloquean todos los implicados."
                results[i].nombre_propuesto = results[i].nombre_propuesto
        else:
            i = indexes[0]
            target = output_folder / results[i].nombre_propuesto
            # No sobrescribir un destino que ya exista; comparación sin distinguir mayúsculas.
            existing = {p.name.casefold() for p in output_folder.iterdir()} if output_folder.exists() else set()
            if target_key in existing:
                results[i].estado = "BLOQUEADO"
                results[i].detalle = "El destino ya existe; no se sobrescribe ningún archivo."
            else:
                results[i].estado = "VÁLIDO"
                results[i].detalle = "Nombre y destino disponibles."
    return results


def export_report(results: Iterable[Result], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["archivo", "nombre_propuesto", "estado", "detalle", "origen"])
        writer.writeheader()
        for item in results:
            writer.writerow(item.to_dict())


def copy_validated(results: Iterable[Result], output_folder: Path) -> tuple[int, list[str]]:
    """Crea copias con copy2. Nunca modifica ni elimina el original."""
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    copied, errors = 0, []
    for item in results:
        if item.estado != "VÁLIDO":
            continue
        source = Path(item.origen)
        destination = output_folder / item.nombre_propuesto
        if destination.exists():
            errors.append(f"{item.nombre_propuesto}: el destino apareció después de validar; no se copió.")
            continue
        try:
            shutil.copy2(source, destination)
            copied += 1
        except OSError as exc:
            errors.append(f"{source.name}: no se pudo copiar ({exc}).")
    return copied, errors
