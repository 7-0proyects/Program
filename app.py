from __future__ import annotations
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

ROOT = Path(__file__).resolve().parents[1]
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import load_catalog, load_metadata, validate, export_report, copy_validated

class BIMApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BIM DOC MANAGER | Gestión documental")
        self.geometry("1120x720")
        self.minsize(940, 620)
        self.configure(bg="#f3f5f8")
        self.folder = tk.StringVar(value=str(ROOT / "data" / "archivos_prueba"))
        self.csv_path = tk.StringVar(value=str(ROOT / "data" / "metadatos.csv"))
        self.output = tk.StringVar(value=str(ROOT / "output" / "renombrados_BIM"))
        self.include_revision = tk.BooleanVar(value=False)
        self.results = []
        self.catalog_path = ROOT / "data" / "catalogos.json"
        self._style(); self._build()

    def _style(self):
        style = ttk.Style(self)
        try: style.theme_use("clam")
        except tk.TclError: pass
        style.configure("Treeview", background="white", fieldbackground="white", rowheight=30, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#e8edf4", foreground="#263449")
        style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=8)
        style.configure("Primary.TButton", background="#174a75", foreground="white")
        style.map("Primary.TButton", background=[("active", "#103957")])

    def _build(self):
        header = tk.Frame(self, bg="#102a43", padx=24, pady=18); header.pack(fill="x")
        tk.Label(header, text="BIM DOC MANAGER", bg="#102a43", fg="white", font=("Segoe UI", 19, "bold")).pack(anchor="w")
        tk.Label(header, text="Renombrado y validación documental BIM", bg="#102a43", fg="#c9d8e6", font=("Segoe UI", 10)).pack(anchor="w", pady=(3,0))

        body = tk.Frame(self, bg="#f3f5f8", padx=20, pady=16); body.pack(fill="both", expand=True)
        files = tk.LabelFrame(body, text="  1. Datos de entrada  ", bg="#f3f5f8", fg="#263449", font=("Segoe UI", 10, "bold"), padx=12, pady=10)
        files.pack(fill="x")
        self._path_row(files, "Carpeta de documentos", self.folder, self.pick_folder)
        self._path_row(files, "Tabla de metadatos (CSV)", self.csv_path, self.pick_csv)
        self._path_row(files, "Carpeta de salida", self.output, self.pick_output)
        options = tk.Frame(files, bg="#f3f5f8"); options.pack(fill="x", pady=(5,0))
        tk.Checkbutton(options, text="Incluir campo de revisión en el nombre (modificación en vivo)", variable=self.include_revision, bg="#f3f5f8", fg="#263449", activebackground="#f3f5f8").pack(side="left")

        actions = tk.Frame(body, bg="#f3f5f8"); actions.pack(fill="x", pady=12)
        ttk.Button(actions, text="Validar documentos", style="Primary.TButton", command=self.run_validation).pack(side="left", padx=(0,8))
        ttk.Button(actions, text="Generar copias válidas", command=self.generate).pack(side="left", padx=8)
        ttk.Button(actions, text="Exportar bitácora CSV", command=self.export).pack(side="left", padx=8)
        ttk.Button(actions, text="Restablecer", command=self.reset).pack(side="right")

        summary = tk.Frame(body, bg="#f3f5f8"); summary.pack(fill="x", pady=(0,10))
        self.summary = tk.Label(summary, text="Carga los datos y presiona Validar documentos.", bg="#f3f5f8", fg="#526477", font=("Segoe UI", 10))
        self.summary.pack(anchor="w")

        table_frame = tk.LabelFrame(body, text="  2. Vista previa y resultados  ", bg="#f3f5f8", fg="#263449", font=("Segoe UI", 10, "bold"), padx=10, pady=10)
        table_frame.pack(fill="both", expand=True)
        cols = ("archivo", "propuesto", "estado", "detalle")
        self.table = ttk.Treeview(table_frame, columns=cols, show="headings")
        for col, title, width in [("archivo","Nombre actual",190),("propuesto","Nombre propuesto",300),("estado","Estado",105),("detalle","Observación",390)]:
            self.table.heading(col, text=title); self.table.column(col, width=width, anchor="w")
        self.table.tag_configure("VÁLIDO", foreground="#18734b")
        self.table.tag_configure("BLOQUEADO", foreground="#b33a3a")
        self.table.tag_configure("PENDIENTE", foreground="#9a6a13")
        self.table.tag_configure("POR VALIDAR", foreground="#315b88")
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview); self.table.configure(yscrollcommand=yscroll.set)
        self.table.pack(side="left", fill="both", expand=True); yscroll.pack(side="right", fill="y")
        footer = tk.Label(body, text="Los originales nunca se modifican. La aplicación no interpreta ni aprueba el contenido técnico de PDF, DWG o Revit.", bg="#f3f5f8", fg="#6b7785", font=("Segoe UI", 8))
        footer.pack(anchor="w", pady=(10,0))

    def _path_row(self, parent, label, variable, command):
        row = tk.Frame(parent, bg="#f3f5f8"); row.pack(fill="x", pady=3)
        tk.Label(row, text=label, width=23, anchor="w", bg="#f3f5f8", fg="#35465a", font=("Segoe UI", 9)).pack(side="left")
        tk.Entry(row, textvariable=variable, relief="solid", bd=1, font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row, text="Examinar…", command=command).pack(side="right")

    def pick_folder(self):
        p = filedialog.askdirectory(title="Seleccionar carpeta de documentos")
        if p: self.folder.set(p)
    def pick_csv(self):
        p = filedialog.askopenfilename(title="Seleccionar metadatos", filetypes=[("CSV", "*.csv"), ("Todos", "*.*")])
        if p: self.csv_path.set(p)
    def pick_output(self):
        p = filedialog.askdirectory(title="Seleccionar carpeta de salida")
        if p: self.output.set(p)

    def run_validation(self):
        try:
            catalog = load_catalog(self.catalog_path)
            metadata = load_metadata(Path(self.csv_path.get()))
            self.results = validate(Path(self.folder.get()), metadata, catalog, Path(self.output.get()), self.include_revision.get())
            self.refresh()
            valid = sum(x.estado == "VÁLIDO" for x in self.results)
            blocked = sum(x.estado == "BLOQUEADO" for x in self.results)
            pending = sum(x.estado == "PENDIENTE" for x in self.results)
            self.summary.config(text=f"Registros: {len(self.results)}    |    Válidos: {valid}    |    Bloqueados: {blocked}    |    Pendientes: {pending}")
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror("No se pudo validar", str(exc))

    def refresh(self):
        for item in self.table.get_children(): self.table.delete(item)
        for r in self.results:
            self.table.insert("", "end", values=(r.archivo, r.nombre_propuesto, r.estado, r.detalle), tags=(r.estado,))

    def generate(self):
        if not self.results:
            messagebox.showinfo("Primero valida", "Debes validar los documentos antes de generar copias."); return
        if not messagebox.askyesno("Confirmar generación", "Se crearán copias de los documentos VÁLIDOS. Los originales no se modificarán. ¿Deseas continuar?"):
            return
        count, errors = copy_validated(self.results, Path(self.output.get()))
        message = f"Copias generadas: {count}\nCarpeta: {self.output.get()}"
        if errors: message += "\n\nObservaciones:\n" + "\n".join(errors)
        messagebox.showinfo("Proceso terminado", message)
        # Revalidar: los destinos creados ahora se detectan como existentes.
        self.run_validation()

    def export(self):
        if not self.results:
            messagebox.showinfo("Sin resultados", "Primero debes validar los documentos."); return
        p = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="bitacora_BIM.csv", filetypes=[("CSV", "*.csv")])
        if not p: return
        try:
            export_report(self.results, Path(p)); messagebox.showinfo("Exportación completa", f"Bitácora guardada en:\n{p}")
        except OSError as exc: messagebox.showerror("Error al exportar", str(exc))

    def reset(self):
        self.results = []; self.refresh(); self.summary.config(text="Carga los datos y presiona Validar documentos.")

if __name__ == "__main__":
    BIMApp().mainloop()
