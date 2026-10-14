"""Check packaged bytes against the public source; never load bundled libraries."""
from pathlib import Path
import hashlib,json,zipfile
from build_editor import ROOT,ARCHIVE,TAG
files=json.loads((ROOT/'plugin_files.json').read_text(encoding='utf-8'))
with zipfile.ZipFile(ARCHIVE) as z:
    assert z.testzip() is None
    assert set(z.namelist())=={'RE-Mesh-Editor-MeshFixes/'+n for n in files}
    hashes={}
    for n in files:
        data=z.read('RE-Mesh-Editor-MeshFixes/'+n)
        assert data==(ROOT/n).read_bytes(),n
        hashes[n]=hashlib.sha256(data).hexdigest()
report=dict(status='PASS',tag=TAG,archive=ARCHIVE.name,archive_sha256=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),entries=len(files),source_bytes_match_all_entries=True,zip_readback=True,bundled_binaries_executed=False,file_sha256=hashes)
(ROOT/'reports/package_check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(ARCHIVE.parent/'delivery_manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('PACKAGE_SOURCE_BYTES_PASS',len(files))
