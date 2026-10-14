"""Actual Blender export/import matrix; supplied DLLs cannot execute."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import zipfile

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT
TEST = ROOT / 'output/re4r.2/synthetic'
TEST.mkdir(parents=True, exist_ok=True)
baseline_only = '--upstream' in sys.argv
plugin = ROOT / 'output/re4r.2/upstream' if baseline_only else ROOT


def forbid_dlls(event, args):
    if event == 'ctypes.dlopen' and args and args[0]:
        value = str(args[0]).lower()
        if any(s in value for s in ('texconv', 'gdeflate', str(plugin).lower())):
            raise RuntimeError('Bundled DLL execution is disabled for mesh-only validation')


sys.addaudithook(forbid_dlls)
name = 're4_face_integration_test'
spec = importlib.util.spec_from_file_location(name, plugin / '__init__.py', submodule_search_locations=[str(plugin)])
module = importlib.util.module_from_spec(spec)
sys.modules[name] = module
spec.loader.exec_module(module)
module.register()
fmt = sys.modules[name + '.modules.mesh.file_re_mesh']
parser = sys.modules[name + '.modules.mesh.re_mesh_parse']
bridge = sys.modules[name + '.modules.mesh.blender_re_mesh']
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
collection=bpy.data.collections.new('SyntheticHead')
bpy.context.scene.collection.children.link(collection)
collection['~TYPE']='RE_MESH_COLLECTION'
data=bpy.data.meshes.new('SyntheticQuad')
data.from_pydata([(0,0,0),(.01,0,0),(.01,.01,0),(0,.01,0)],[],[(0,1,2),(0,2,3)])
data.update()
data.polygons.foreach_set('use_smooth',[True,True])
data.normals_split_custom_set([(0,0,1)]*6)
uv=data.uv_layers.new(name='UVMap')
for loop,coord in zip(uv.data,[(0,0),(1,0),(1,1),(0,0),(1,1),(0,1)]):loop.uv=coord
data.materials.append(bpy.data.materials.new('SyntheticMaterial'))
obj=bpy.data.objects.new('LOD_0_Group_0_Sub_0__SyntheticMaterial',data)
collection.objects.link(obj)
obj.shape_key_add(name='Basis')
obj.shape_key_add(name='Move').data[0].co.z=.002
options=dict(clearScene=True,createCollections=True,loadMaterials=False,loadMDFData=False,loadShellFur=False,loadUnusedTextures=False,loadUnusedProps=False,useBackfaceCulling=False,reloadCachedTextures=False,mdfPath='',importAllLODs=False,importBlendShapes=True,rotate90=True,mergeArmature='',importArmatureOnly=False,mergeGroups=False,importShadowMeshes=False,importOcclusionMeshes=False,importBoundingBoxes=False)


def parse(path):
    mesh = fmt.readREMesh(str(path))
    parsed = parser.ParsedREMesh()
    parsed.ParseREMesh(mesh, dict(importAllLOD=True, importShadowMesh=False, importOcclusionMesh=False, importBlendShapes=True))
    shapes = {}
    for lod in parsed.mainMeshLODList:
        for group in lod.visconGroupList:
            for sub in group.subMeshList:
                for shape in sub.blendShapeList:
                    array = np.asarray(shape.deltas, np.float32)
                    assert np.isfinite(array).all(), shape.blendShapeName
                    shapes.setdefault(shape.blendShapeName, []).append(array)
    return mesh, parsed, shapes


common = dict(targetCollection=collection.name, rotate90=True,
    exportAllLODs=False, selectedOnly=False, useBlenderMaterialName=False,
    preserveBoneMatrices=False, preserveMaterialTable=False, autoSolveRepeatedUVs=False,
    preserveSharpEdges=False, splitLoopVertices=False, limitTotal=False, normalizeWeights=False)


def export(label, taps=False, normals=False, **overrides):
    path = TEST / (label + '.mesh.221108797')
    arguments = dict(common, filepath=str(path))
    if not baseline_only:
        arguments.update(re4NativeMouthTaps=taps, re4KeepToonNormals=normals)
    arguments.update(overrides)
    assert bpy.ops.re_mesh.exportfile(**arguments) == {'FINISHED'} and path.is_file()
    return path, parse(path)


def geometry(mesh):
    v = mesh.meshBufferHeader
    element = next(e for e in v.vertexElementList if e.typing == 1)
    count = element.posStartOffset // 12
    end = max(e.posStartOffset + count * e.stride for e in v.vertexElementList)
    return bytes(v.vertexBuffer[:end]), bytes(v.faceBuffer), count


if baseline_only:
    path, (mesh, parsed, shapes) = export('upstream')
    assert len(shapes) == 1 and mesh.fileHeader.normalRecalcOffset != 0
    (ROOT / 'reports/upstream_baseline.json').write_text(json.dumps(dict(status='PASS', channels=1,
        mesh=path.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(path.read_bytes()).hexdigest()), indent=2), encoding='utf-8')
    print('UPSTREAM_0706_BASELINE_PASS')
    raise SystemExit

core = importlib.import_module(name + '.modules.mesh.re4_blendshape')
results = {}
shapes_by_mode = {}
default_geometry = None
for taps, normals in ((False, False), (True, False), (False, True), (True, True)):
    label = ('mouth9' if taps else 'no_taps') + ('_toon' if normals else '_recalc')
    path, (mesh, parsed, shapes) = export(label, taps, normals)
    names = [mesh.rawNameList[i] for i in mesh.blendShapeNameRemapList]
    assert len(names) == len(shapes) == (10 if taps else 1)
    if taps:
        assert names[:9] == list(core.RE4_NATIVE_MOUTH_TAPS)
        assert all(not a.any() for tap in names[:9] for a in shapes[tap])
    assert bool(mesh.fileHeader.normalRecalcOffset) == (not normals)
    assert all(b.unknFlag == (0 if normals else 1) for b in mesh.blendShapeHeader.blendShapeList)
    if default_geometry is None:
        default_geometry = geometry(mesh)
    else:
        assert geometry(mesh) == default_geometry
    normal_rows = 0
    if normals:
        v = mesh.meshBufferHeader
        el = next(e for e in v.vertexElementList if e.typing == 1)
        static = np.frombuffer(bytes(v.vertexBuffer), np.int8, default_geometry[2] * 8, el.posStartOffset).reshape(-1, 8)
        payload_start = (int(v.vertexElementSize) & 0xffff) | ((int(v.unkn1) & 0xffff) << 16)
        payload = np.frombuffer(bytes(v.vertexBuffer[payload_start:]), np.uint8).reshape(-1, 8)
        for body in mesh.blendShapeHeader.blendShapeList:
            for target in body.blendTargetList[:body.targetCount]:
                rows_per_key = sum(r.vertCount for r in target.subMeshEntryList)
                for channel in range(target.blendShapeNum):
                    for run in target.subMeshEntryList:
                        begin = run.vertOffset + channel * rows_per_key
                        rows = payload[begin:begin+run.vertCount]
                        assert not rows[:, 7].any()
                        assert np.array_equal(rows[:, 4:7].view(np.int8), static[run.subMeshVertexStartIndex:run.subMeshVertexStartIndex+run.vertCount, :3])
                        normal_rows += len(rows)
    shapes_by_mode[label] = shapes
    results[label] = dict(file=path.relative_to(ROOT).as_posix(), channels=len(names), normal_recalc_offset=mesh.fileHeader.normalRecalcOffset,
        vertices=default_geometry[2], bones=0, authored_normal_rows_verified=normal_rows,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest())

# Switches don't affect geometry or existing keys except packed quantization.
baseline_shapes = shapes_by_mode['no_taps_recalc']
for key, arrays in baseline_shapes.items():
    for other, rows in shapes_by_mode.items():
        assert len(rows[key]) == len(arrays)
        for a, b in zip(arrays, rows[key]):
            diff = float(np.abs(a-b).max(initial=0))
            if other.endswith('_recalc'):
                assert diff == 0, (other, key, diff)
            else:
                assert diff < 0.0001, (other, key, diff)
upstream = TEST / 'upstream.mesh.221108797'
assert upstream.is_file()
assert upstream.read_bytes() == (TEST / 'no_taps_recalc.mesh.221108797').read_bytes(), 'Default export drift from upstream'

# Batch export must reload the two saved switches and forward them to the operator.
collection['BatchExport_path'] = str(TEST / 'batch_mouth9_toon.mesh.221108797')
collection['BatchExport_enabled'] = True
assert collection['BatchExport_re4NativeMouthTaps'] and collection['BatchExport_re4KeepToonNormals']
assert bpy.ops.re_mesh.batch_exporter(skipPrompt=True) == {'FINISHED'}
batch_mesh, _, batch_shapes = parse(TEST / 'batch_mouth9_toon.mesh.221108797')
assert len(batch_shapes) == 10 and batch_mesh.fileHeader.normalRecalcOffset == 0
assert (TEST / 'batch_mouth9_toon.mesh.221108797').read_bytes() == (TEST / 'mouth9_toon.mesh.221108797').read_bytes()

# NO always omits shape keys, even with both RE4 switches enabled.
_, (static_mesh, _, static_shapes) = export('no_shapes', True, True, shapeKeyExportMode='NO')
assert not static_shapes and static_mesh.blendShapeHeader is None and static_mesh.fileHeader.normalRecalcOffset == 0

# Re-import and export the new packed layout, including zero receivers.
assert bridge.importREMeshFile(str(TEST / 'mouth9_toon.mesh.221108797'), options)
collection = next(c for c in bpy.data.collections if c.get('~TYPE') == 'RE_MESH_COLLECTION')
common['targetCollection'] = collection.name
roundtrip_path, (_, _, roundtrip_shapes) = export('roundtrip_mouth9_toon', True, True)
assert set(roundtrip_shapes) == set(shapes_by_mode['mouth9_toon'])
for key, arrays in roundtrip_shapes.items():
    for a, b in zip(arrays, shapes_by_mode['mouth9_toon'][key]):
        assert float(np.abs(a-b).max(initial=0)) < 0.0001

obj=next(o for o in collection.objects if o.type=='MESH')
obj.data.shape_keys.key_blocks[core.RE4_NATIVE_MOUTH_TAPS[0]].data[0].co.z += .001
try:
    export('conflicting_receiver',True,True)
except RuntimeError as error:
    assert 'Native receiver must have zero deltas' in str(error), str(error)
else:
    raise AssertionError('Nonzero receiver conflict accepted')
report=dict(status='PASS', upstream_baseline='c030c89f95e6f20c697c402d21b7bae7ec8a52e9', selector='upstream default KEEPNORMALS_SURFACE',fixture='generated quad and Move key; no private/game assets',blender_version=bpy.app.version_string,export_matrix=results,default_export_byte_identical_upstream=True,geometry_identical_all_four_modes=True,batch_flags_persisted_and_exported=True,no_shape_mode_ignores_switches=True,new_format_reimport_and_reexport=True,nonzero_receiver_conflict_rejected=True,supplied_dlls_executed=False,game_validation='Merged re4r.2 and integrated 94-channel real-model combination pending new game feedback')
(ROOT/'reports/synthetic_blender.json').write_text(json.dumps(report,indent=2))
print('SYNTHETIC_RE4R_PASS')
