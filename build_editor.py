"""Portable, allowlist-only plugin packaging. No asset conversion or DLL loading."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parent
TAG='v0.70.6-re4r.1'
ARCHIVE=ROOT/'output/RE-Mesh-Editor-BlendShape-0.70.6-RE4R-FaceIntegration.zip'
def build():
    files=json.loads((ROOT/'plugin_files.json').read_text(encoding='utf-8'))
    ARCHIVE.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(ARCHIVE,'w',zipfile.ZIP_DEFLATED) as z:
        for name in files:
            p=ROOT/name
            assert p.resolve().is_relative_to(ROOT) and p.is_file(),name
            info=zipfile.ZipInfo('RE-Mesh-Editor-MeshFixes/'+name,(2026,10,13,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o644 << 16
            z.writestr(info,p.read_bytes())
    print(ARCHIVE.name,hashlib.sha256(ARCHIVE.read_bytes()).hexdigest())
if __name__=='__main__':build()
