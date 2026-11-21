from __future__ import annotations
import sys
import tempfile
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import load_catalog, load_metadata, validate, export_report, copy_validated

st.set_page_config(page_title="BIM DOC MANAGER | Gestión documental", layout="wide")

st.title("BIM DOC MANAGER | GESTIÓN DOCUMENTAL")
st.caption("Renombrado y validación de archivos según catálogo y metadatos")

if "results" not in st.session_state:
    st.session_state.results = []

catalog_path = ROOT / "data" / "catalogos.json"

col_in1, col_in2, col_in3 = st.columns(3)
with col_in1:
    folder = st.text_input("Carpeta de documentos", value=str(ROOT / "data" / "archivos_prueba"))
with col_in2:
    csv_path = st.text_input("Archivo de metadatos (CSV)", value=str(ROOT / "data" / "metadatos.csv"))
with col_in3:
    output = st.text_input("Carpeta de salida", value=str(ROOT / "output" / "renombrados_BIM"))

include_revision = st.checkbox("Incluir campo de revisión en el nombre", value=False)


def ejecutar_validacion() -> None:
    catalog = load_catalog(catalog_path)
    metadata = load_metadata(Path(csv_path))
    st.session_state.results = validate(Path(folder), metadata, catalog, include_revision)


col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("1. Validar documentos", use_container_width=True):
        try:
            ejecutar_validacion()
        except (OSError, ValueError, KeyError) as exc:
            st.error(f"Error de validación: {exc}")

with col2:
    if st.button("2. Generar copias renombradas", use_container_width=True):
        if not st.session_state.results:
            st.info("Primero debes validar los documentos antes de generar.")
        else:
            try:
                count, errors = copy_validated(st.session_state.results, Path(output))
                st.success(f"Copias generadas: {count} | Carpeta: {output}")
                if errors:
                    st.warning("Observaciones:\n" + "\n".join(errors))
                ejecutar_validacion()
            except (OSError, ValueError, KeyError) as exc:
                st.error(f"Error al generar copias: {exc}")

with col3:
    if st.session_state.results:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                tmp_path = Path(tmp.name)
            export_report(st.session_state.results, tmp_path)
            csv_bytes = tmp_path.read_bytes()
            tmp_path.unlink(missing_ok=True)
            st.download_button(
                label="Exportar reporte CSV",
                data=csv_bytes,
                file_name="reporte_validacion.csv",
                mime="text/csv",
                use_container_width=True,
            )
        except OSError as exc:
            st.error(f"Error al preparar reporte: {exc}")
    else:
        st.button("Exportar reporte CSV", disabled=True, use_container_width=True)

with col4:
    if st.button("Limpiar", use_container_width=True):
        st.session_state.results = []
        st.rerun()

results = st.session_state.results

if results:
    total = len(results)
    ok = sum(1 for r in results if getattr(r, "status", None) == "OK")
    blocked = sum(1 for r in results if getattr(r, "status", None) == "BLOQUEADO")
    pending = sum(1 for r in results if getattr(r, "status", None) == "PENDIENTE")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total", total)
    m2.metric("OK", ok)
    m3.metric("Bloqueados", blocked)
    m4.metric("Pendientes", pending)

    st.dataframe([vars(r) for r in results], use_container_width=True)
else:
    st.info("Carga los datos y pulsa '1. Validar documentos'.")

