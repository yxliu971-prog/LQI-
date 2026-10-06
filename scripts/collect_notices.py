import importlib.metadata as metadata
from pathlib import Path
import shutil

root=Path(__file__).resolve().parents[1]
out=root/"docs"/"third_party_licenses"
out.mkdir(exist_ok=True)
lines=["# Third-party components", "", "Versions and license metadata below are collected from the installed distributions. Original license files are preserved in third_party_licenses. Each component remains under its own license; these are not original LQI code.", "", "Qt/PySide6 is dynamically shipped in the portable directory. Keep the directory structure and third-party notices intact. Qt/PySide6 source and license information: https://www.qt.io/qt-for-python and https://code.qt.io/cgit/pyside/pyside-setup.git/", "", "| Component | Version | Declared license |", "|---|---|---|"]
for dist in sorted(metadata.distributions(),key=lambda d:d.metadata["Name"].lower()):
    name=dist.metadata["Name"]
    license=dist.metadata.get("License-Expression") or dist.metadata.get("License") or "See original license files / upstream"
    license=license.splitlines()[0][:160].replace("|","/")
    lines.append(f"| {name} | {dist.version} | {license} |")
    for entry in dist.files or []:
        text=str(entry).lower().replace('\\','/')
        filename=Path(text).name
        if (any(filename.startswith(token) for token in ["license", "licence", "copying", "copyright", "notice"])
                and Path(filename).suffix not in {".py", ".pyc", ".pyo", ".so", ".pyd", ".dll"}):
            source=Path(dist.locate_file(entry))
            if source.is_file() and source.stat().st_size<3_000_000:
                target=out/name/str(entry).replace('..','_')
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(source,target)
(root/"docs"/"THIRD_PARTY_NOTICES.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
print("License files",sum(1 for p in out.rglob('*') if p.is_file()))
