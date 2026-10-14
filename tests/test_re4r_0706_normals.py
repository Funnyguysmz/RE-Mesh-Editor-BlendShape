"""Public synthetic regressions for upstream 0.70.6 and the RE4R contract.

Run in Blender with --background --factory-startup --python-exit-code 1.
No game/model fixture or bundled native library is loaded.
"""
import importlib
import importlib.util
import json
from pathlib import Path
import sys

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/re4r.2/normals'
OUT.mkdir(parents=True, exist_ok=True)


def forbid_bundled_libraries(event, args):
    if event == 'ctypes.dlopen' and args and args[0]:
        value = str(args[0]).lower()
        if any(s in value for s in ('texconv', 'gdeflate', str(ROOT).lower())):
            raise RuntimeError('Bundled library execution forbidden in synthetic tests')


sys.addaudithook(forbid_bundled_libraries)
sys.path.insert(0, str(ROOT.parent))
spec = importlib.util.spec_from_file_location('upstream_normal_tests', ROOT / 'tests/test_static_normals_blender.py')
up = importlib.util.module_from_spec(spec)
spec.loader.exec_module(up)
up.main(OUT)
assert all(result[1] for result in up.results), up.results

bridge = importlib.import_module(ROOT.name + '.modules.mesh.blender_re_mesh')
codec = importlib.import_module(ROOT.name + '.modules.mesh.file_re_mesh')
core = importlib.import_module(ROOT.name + '.modules.mesh.re4_blendshape')
results = []


def check(name, condition, detail=''):
    results.append(dict(name=name, passed=bool(condition), detail=detail))
    assert condition, (name, detail)
    print('PASS ' + name, flush=True)


def read_re4(path):
    mesh = codec.readREMesh(str(path))
    header = mesh.meshBufferHeader
    vb = bytes(header.vertexBuffer)
    elements = {int(e.typing): e for e in header.vertexElementList}
    count = elements[1].posStartOffset // 12
    positions = np.frombuffer(vb, '<f4', count * 3, elements[0].posStartOffset).reshape(-1, 3)
    normals = np.frombuffer(vb, np.int8, count * 8, elements[1].posStartOffset).reshape(-1, 8)[:, :3]
    start = (int(header.vertexElementSize) & 0xffff) | ((int(header.unkn1) & 0xffff) << 16)
    channels = {}
    if mesh.blendShapeHeader:
        for body in mesh.blendShapeHeader.blendShapeList:
            for target in body.blendTargetList[:body.targetCount]:
                rows_per_key = sum(run.vertCount for run in target.subMeshEntryList)
                for ch in range(target.blendShapeNum):
                    name = mesh.rawNameList[mesh.blendShapeNameRemapList[int(target.blendSSIndex) + ch]]
                    rows = channels.setdefault(name, {})
                    for run in target.subMeshEntryList:
                        offset = run.vertOffset + ch * rows_per_key
                        raw = np.frombuffer(vb, np.int8, run.vertCount * 8, start + 8 * offset).reshape(-1, 8)
                        for i in range(run.vertCount):
                            rows[run.subMeshVertexStartIndex + i] = raw[i, 4:7].copy()
    return mesh, positions, normals, channels


def export_re4(collection, name, mode='KEEPNORMALS_SURFACE', packed=True, taps=True):
    path = OUT / (name + '.mesh.221108797')
    assert bpy.ops.re_mesh.exportfile(
        filepath=str(path), targetCollection=collection.name, shapeKeyExportMode=mode,
        re4KeepToonNormals=packed, re4NativeMouthTaps=taps,
        selectedOnly=False, exportAllLODs=False, rotate90=True,
        useBlenderMaterialName=False, preserveBoneMatrices=False, preserveMaterialTable=False,
        autoSolveRepeatedUVs=False, preserveSharpEdges=False, splitLoopVertices=True,
        limitTotal=False, normalizeWeights=False) == {'FINISHED'}
    return path, read_re4(path)


check('New export default is surface turn',
      bpy.ops.re_mesh.exportfile.get_rna_type().properties['shapeKeyExportMode'].default == 'KEEPNORMALS_SURFACE')

# Reuse upstream's stylised quad sphere and independent mathematical reference.
collection, obj, custom = up.build_sphere('re4_locked_face', stylised=True)
collection['~TYPE'] = 'RE_MESH_COLLECTION'
bridge.setStaticNormals(obj.data, 'lockS', True)
bridge.setStaticNormals(obj.data, 'squash_static', True)
path, (mesh, positions, normals, channels) = export_re4(collection, 'locked_static')
check('RE4 generated two keys plus nine receivers', len(channels) == 11)
check('RE4 packed no-recalc marker', mesh.fileHeader.normalRecalcOffset == 0 and all(b.unknFlag == 0 for b in mesh.blendShapeHeader.blendShapeList))
check('Every RE4 key and receiver repeats final base normal bytes',
      all(np.array_equal(normal, normals[row]) for rows in channels.values() for row, normal in rows.items()))

from math import radians
from mathutils import Matrix
rotation = np.array(Matrix.Rotation(radians(-90), 3, 'X'))
baked_positions = up.key_positions(obj, {'lockA': 1, 'lockS': 1})
row_vertex = up.rows_to_vertices(positions, baked_positions)
basis = up.key_positions(obj, {})
expected = up.rotate(custom, up.unit(up.vertex_normals_at(obj, basis)),
                     up.unit(up.vertex_normals_at(obj, up.key_positions(obj, {'lockA': 1})))) @ rotation.T
cosine = (up.unit(normals.astype(float)) * expected[row_vertex]).sum(1)
check('RE4 locked surface turn excludes Static locked key', cosine.min() > .995, float(cosine.min()))

# Generic selector compatibility: it only enables keys for RE4; layout stays opt-in.
for mode in ('MODE1', 'KEEPNORMALS', 'KEEPNORMALS_SURFACE'):
    candidate, _ = export_re4(collection, 'selector_' + mode, mode)
    check('RE4 packed bytes independent of generic selector ' + mode,
          candidate.read_bytes() == path.read_bytes())
    candidate, (float_mesh, _, _, float_channels) = export_re4(collection, 'recalc_' + mode, mode, False)
    check('RE4 recalc selector compatibility ' + mode,
          float_mesh.fileHeader.normalRecalcOffset != 0 and len(float_channels) == 11)
    if mode == 'MODE1':
        recalc_bytes = candidate.read_bytes()
    else:
        check('RE4 recalc bytes equal MODE1 ' + mode, candidate.read_bytes() == recalc_bytes)

# Per-exported-key Static does not rewrite the RE4 final-base payload contract.
bridge.setStaticNormals(obj.data, 'squash_static', False)
candidate, _ = export_re4(collection, 'exported_static_off')
check('RE4 exported-key Static flag has no per-key payload effect', candidate.read_bytes() == path.read_bytes())
bridge.setStaticNormals(obj.data, 'lockS', False)
candidate, (_, _, changed_normals, changed_channels) = export_re4(collection, 'locked_static_off')
check('RE4 locked Static flag changes baked base normals', not np.array_equal(changed_normals, normals))
check('RE4 changed locked base still repeated on every key',
      all(np.array_equal(normal, changed_normals[row]) for rows in changed_channels.values() for row, normal in rows.items()))

# A quad and a five-sided polygon carry distinct authored corner normals.
# Check both the triangulation helper and actual packed RE4 export.
for sides in (4, 5):
    from math import cos, sin, pi
    vertices = [(cos(2*pi*i/sides)*.1, sin(2*pi*i/sides)*.1, 0) for i in range(sides)]
    data = bpy.data.meshes.new('polygon_' + str(sides))
    data.from_pydata(vertices, [], [tuple(range(sides))])
    data.update()
    data.polygons[0].use_smooth = True
    authored = up.unit(np.array([(1+i*.12, .2+i*.2, 1) for i in range(sides)]))
    data.normals_split_custom_set(authored.tolist())
    original = np.array([tuple(n.vector) for n in data.corner_normals])
    tri = data.copy()
    bridge.triangulateMesh(tri)
    corners = np.array([loop.vertex_index for loop in tri.loops])
    after = np.array([tuple(n.vector) for n in tri.corner_normals])
    dots = (after * original[corners]).sum(1)
    check('Triangulate authored corner normals, sides=' + str(sides), dots.min() > .9999, float(dots.min()))
    check('Triangulation helper leaves no temporary normal attribute, sides=' + str(sides),
          bridge.TRIANGULATE_NORMALS_ATTRIBUTE not in tri.attributes)
    bpy.data.meshes.remove(tri)
    fixture = bpy.data.collections.new('polygon_' + str(sides))
    bpy.context.scene.collection.children.link(fixture)
    fixture['~TYPE'] = 'RE_MESH_COLLECTION'
    uv = data.uv_layers.new(name='UVMap')
    for loop, vertex in zip(uv.data, vertices):
        loop.uv = ((vertex[0]+.1)*5, (vertex[1]+.1)*5)
    data.materials.append(bpy.data.materials.new('PolyMaterial'))
    polygon = bpy.data.objects.new('LOD_0_Group_0_Sub_0__PolyMaterial', data)
    fixture.objects.link(polygon)
    polygon.shape_key_add(name='Basis')
    polygon.shape_key_add(name='Move').data[0].co.z += .002
    _, (_, pos, packed_normals, poly_channels) = export_re4(fixture, 'export_polygon_' + str(sides))
    mapping = up.rows_to_vertices(pos, np.array(vertices))
    wanted = original[mapping] @ rotation.T
    dot = (up.unit(packed_normals.astype(float)) * wanted).sum(1)
    check('Actual RE4 export preserves polygon authored normals, sides=' + str(sides), dot.min() > .999, float(dot.min()))
    check('Actual RE4 polygon morph normals repeat the final base bytes, sides=' + str(sides),
          all(np.array_equal(normal, packed_normals[row]) for rows in poly_channels.values() for row, normal in rows.items()))

report = dict(status='PASS', upstream_baseline='c030c89f95e6f20c697c402d21b7bae7ec8a52e9',
              fixture='generated spheres, quad and pentagon only',
              upstream_checks=[dict(name=n, passed=p, detail=str(d)) for n,p,d in up.results],
              re4_checks=results, bundled_libraries_executed=False,
              re4_semantics='Surface turn and Static affect locked-key base baking. RE4 packed morphs always repeat final base normals; generic selector and exported-key Static do not override that.',
              game_feedback='Merged build pending new in-game feedback')
(ROOT / 'reports/upstream_0706_normals.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('UPSTREAM_0706_AND_RE4R_NORMALS_PASS', len(up.results), len(results))
