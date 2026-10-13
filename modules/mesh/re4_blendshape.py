"""Resident Evil 4 (2023) blend-shape export for the unified RE Mesh exporter.

RE4 shares Wilds' target records (active targets with BlendSubMesh runs, then
`typing` inactive targets) and its canonical normal-recalc tables, so those
parts reuse mhwilds_blendshape. Layout of the six vanilla faces surveyed
(cha000/005/006/102/800 _10, 2026-10-12) and four modded heads:
- one active target per body holding every channel; its runs are whole
  submeshes (vanilla: the face submesh). One inactive target per viscon group
  covers the remaining vertices, an empty one when nothing is left;
- each payload row is 8 bytes, float16 (dx, dy, dz, 0) in mesh units; the
  target AABB is the symmetric max |delta| and is not used to decode;
- the payload follows the vertex elements, its start in the two shorts at
  MeshBufferHeader + 44; vertOffset is the run's absolute payload row;
- body 0 (LOD0): unknFlag 1, blendS (-1, 0, 0), every blendSS -1. Higher LOD
  bodies (cha800 only) repeat the LOD0 channels in order with blendSSIndex 0,
  blendS (0, 0, 0) and blendSS 0..n-1, plus their own "_LOD<n>" names;
- the canonical tables cover LOD0 only and live in their own section at
  normalRecalcOffset: count 1, pointer array, {vertex table, face table}.
  Wilds' generator rebuilds them from vanilla geometry byte for byte except
  on cha006, where vanilla keeps twins within 1 degree apart (99.4%); only
  exact-normal merging reproduces that, but Blender exports add 1-4 units of
  normal noise to vanilla's identical twins, so the 1 degree rule is kept.
"""

import struct
import json

# RE4R Face Integration 0.70.6, funnyguyz (2026-10-13).
# Additional mode observed on native RE4 chd000_00 and tested on Xiaoyu:
# unknFlag=0, no recalc section, packed delta + authored int8 normal rows.
# This fork preserves the static exported normal field on every key.

import numpy as np

from . import file_re_mesh as mesh_format
from . import mhwilds_blendshape as wilds


# The header qword differs per vanilla file (it looks like a stale pointer);
# this is cha000_10's, which the known working mods also carry.
BLEND_HEADER_HASH = 2615081718160
NORMAL_RECALC_HEADER_BYTES = 48


RE4_NATIVE_MOUTH_TAPS = ('Face__geo__p000_cbs.crct_jaw_openExtreme', 'Face__geo__p000_cbs.crct_mouth_purse_L_U', 'Face__geo__p000_cbs.crct_mouth_purse_L_D', 'Face__geo__p000_cbs.crct_mouth_purse_R_U', 'Face__geo__p000_cbs.crct_mouth_purse_R_D', 'Face__geo__p000_cbs.crct_mouth_funnel_L_U', 'Face__geo__p000_cbs.crct_mouth_funnel_L_D', 'Face__geo__p000_cbs.crct_mouth_funnel_R_U', 'Face__geo__p000_cbs.crct_mouth_funnel_R_D')


def parse_native_tap_names(value):
	"""Explicit per-export receiver names, supplied by the head collection only."""
	if value is None or value == "":
		return []
	if isinstance(value, str):
		value = json.loads(value)
	if not isinstance(value, (list, tuple)):
		raise ValueError("RE4_native_taps must be a JSON list of full native channel names")
	result = []
	for name in value:
		if not isinstance(name, str) or not name.startswith("Face__geo__p000_cbs.crct_") or len(name) <= len("Face__geo__p000_cbs.crct_") or any(c.isspace() for c in name):
			raise ValueError("Invalid full RE4 native tap name: " + repr(name))
		if name not in result:
			result.append(name)
	return result


def _pack_rows(deltas):
	deltas = np.asarray(deltas, dtype=np.float32).reshape((-1, 3))
	rows = np.zeros((len(deltas), 4), dtype="<f2")
	rows[:, :3] = deltas
	return rows.tobytes()


def _pack_toon_rows(deltas, aabb):
	words = np.frombuffer(wilds._pack_delta_rows(deltas, aabb), dtype="<u4")
	rows = np.zeros((len(words), 2), dtype="<u4")
	rows[:, 0] = words
	# Fill second words from the final exported geometry in finalize_re4_export.
	return rows.tobytes()


def _new_target(channel_count, runs, lo):
	target = mesh_format.BlendTarget()
	target.blendSSIndex = 0
	target.blendShapeNum = int(channel_count)
	target.unkn0 = 0
	target.unkn2 = 1 if channel_count else 0
	target.subMeshEntryList = wilds._run_entries(runs, lo)
	target.subMeshEntryCount = len(target.subMeshEntryList)
	return target


def _group_deltas(submeshes, names):
	"""Deltas of the given channels over one viscon group's global range."""
	lo = min(int(info.vertexStartIndex) for _parsed, info, _count in submeshes)
	hi = max(int(info.vertexStartIndex) + count for _parsed, info, count in submeshes)
	valid = np.zeros(hi - lo, dtype=bool)
	ranges = []
	for _parsed, info, count in submeshes:
		start = int(info.vertexStartIndex) - lo
		valid[start:start + count] = True
		ranges.append((start, start + count))
	channels = []
	for name in names:
		deltas = np.zeros((hi - lo, 3), dtype=np.float32)
		for parsed_submesh, info, count in submeshes:
			start = int(info.vertexStartIndex) - lo
			deltas[start:start + count] = wilds._normalized_deltas(
				parsed_submesh, name, count
			)
		mask = np.any(np.abs(deltas) > wilds.EDIT_DELTA_THRESHOLD, axis=1)
		channels.append((name, deltas, mask))
	return lo, valid, ranges, channels


def _submesh_runs(mask, ranges):
	"""Runs made of every whole submesh that has a moving vertex."""
	marked = np.zeros(len(mask), dtype=bool)
	for start, end in ranges:
		if mask[start:end].any():
			marked[start:end] = True
	return wilds._mask_runs(marked)


def _build_body(lod, parsed_to_mesh_info, channel_order=None, native_taps=()):
	"""One blend body. LOD0 passes no order; higher LODs repeat LOD0's channels.

	Returns (body, [(target, [(deltas, runs)])], names) or None when the LOD
	has no usable shape keys.
	"""
	groups = wilds._viscon_submeshes(lod, parsed_to_mesh_info)
	if not groups:
		return None
	body = mesh_format.BlendShapeData()
	body.padding1 = 0
	body.padding2 = 0
	body.unknFlag = 1
	body.aabbList = []
	active = []
	inactive = []
	names = []
	taps_added = False
	for submeshes in groups:
		if channel_order is None:
			lo, valid, ranges, channels = _group_deltas(
				submeshes, wilds._shape_names(submeshes)
			)
			# Receivers must be zero-delta. A real deformation under the same name is ambiguous.
			for name, _deltas, moving in channels:
				if name in native_taps and moving.any():
					raise ValueError("Native receiver must have zero deltas: " + name)
			channels = [channel for channel in channels if channel[2].any()]
			# Attach once to the first active group; zeros share the custom channels' existing runs.
			if channels and native_taps and not taps_added:
				channels = [(name, np.zeros((len(valid), 3), dtype=np.float32), np.zeros(len(valid), dtype=bool)) for name in native_taps] + channels
				taps_added = True
		else:
			lo, valid, ranges, channels = _group_deltas(submeshes, channel_order)
			if not any(channel[2].any() for channel in channels):
				channels = []
		covered = np.zeros(len(valid), dtype=bool)
		if channels:
			mask = np.zeros(len(valid), dtype=bool)
			for channel in channels:
				mask |= channel[2]
			runs = _submesh_runs(mask, ranges)
			if len(runs) > wilds.MAX_TARGET_ENTRIES:
				raise RuntimeError(
					f"RE4 blend target needs {len(runs)} vertex runs, "
					f"more than {wilds.MAX_TARGET_ENTRIES}"
				)
			target = _new_target(len(channels), runs, lo)
			target.unkn0 = len(active)
			for start, end in runs:
				covered[start:end] = True
			body.aabbList.append(wilds._symmetric_aabb([
				deltas[mask] for _name, deltas, mask in channels
			]))
			active.append((
				target,
				[(deltas, runs) for _name, deltas, _mask in channels],
			))
			names.extend(name for name, _deltas, _mask in channels)
		rest = wilds._mask_runs(valid & ~covered)
		for chunk_start in range(0, len(rest), wilds.MAX_TARGET_ENTRIES):
			inactive.append(_new_target(
				0, rest[chunk_start:chunk_start + wilds.MAX_TARGET_ENTRIES], lo
			))
	if not active:
		return None
	if not inactive:
		inactive.append(_new_target(0, [], 0))
	body.targetCount = len(active)
	body.typing = len(inactive)
	body.blendTargetList = [target for target, _rows in active] + inactive
	return body, active, names


def build_re4_blend_shape_plan(parsed_mesh, parsed_to_mesh_info):
	"""Build the blend bodies, their name list and the float16 payload."""
	lods = wilds._list_or_empty(getattr(parsed_mesh, "mainMeshLODList", None))
	if not lods:
		return None
	native_taps = parse_native_tap_names(getattr(parsed_mesh, "_re4NativeTapNames", None))
	wilds._drop_empty_shapes(lods)
	built = _build_body(lods[0], parsed_to_mesh_info, native_taps=native_taps)
	if built is None:
		if native_taps:
			raise ValueError("Native taps require at least one moving custom shape key")
		return None
	if native_taps and not all(name in built[2] for name in native_taps):
		raise ValueError("Requested native taps were not included in LOD0")
	bodies = [built]
	base_names = built[2]
	for lod_index, lod in enumerate(lods[1:], start=1):
		lod_names = {
			name
			for submeshes in wilds._viscon_submeshes(lod, parsed_to_mesh_info)
			for name in wilds._shape_names(submeshes)
		}
		if not lod_names:
			break
		reason = None
		if len(bodies[0][1]) != 1:
			reason = "LOD0 has shape keys in more than one viscon group"
		elif not lod_names <= set(base_names):
			reason = "it has shape keys LOD0 does not have: " + ", ".join(
				sorted(lod_names - set(base_names))
			)
		else:
			built = _build_body(lod, parsed_to_mesh_info, channel_order=base_names)
			if built is None:
				break
			if len(built[1]) != 1:
				reason = "its shape keys move more than one viscon group"
		if reason:
			print(
				f"RE4 shape keys exported for LOD0-LOD{lod_index - 1} only; "
				f"LOD{lod_index} skipped because {reason}"
			)
			break
		bodies.append(built)

	header = mesh_format.BlendShapeHeader()
	header.zero = 0
	header.hash = BLEND_HEADER_HASH
	header.blendShapeList = []
	remap_names = list(base_names)
	payload = bytearray()
	row = 0
	keep_toon = bool(getattr(parsed_mesh, "_re4KeepToonNormals", False))
	normal_runs = []
	for body_index, (body, active, names) in enumerate(bodies):
		if keep_toon:
			body.unknFlag = 0
		if body_index == 0:
			body.blendS = [-1, 0, 0]
			body.blendSSList = [-1] * len(names)
		else:
			# Higher LODs follow the LOD0 channel with the same index.
			body.blendS = [0, 0, 0]
			body.blendSSList = list(range(len(names)))
			remap_names.extend(f"{name}_LOD{body_index}" for name in names)
		channel_base = 0
		for target_index, (target, rows) in enumerate(active):
			target.blendSSIndex = channel_base if body_index == 0 else 0
			channel_base += int(target.blendShapeNum)
			target_rows = sum(int(entry.vertCount) for entry in target.subMeshEntryList)
			prefix = 0
			for entry in target.subMeshEntryList:
				entry.vertOffset = row + prefix
				prefix += int(entry.vertCount)
			for deltas, runs in rows:
				for start, end in runs:
					if keep_toon:
						normal_runs.append((len(payload), int(target.subMeshEntryList[0].subMeshVertexStartIndex) - int(runs[0][0]) + start, end - start))
						payload.extend(_pack_toon_rows(deltas[start:end], body.aabbList[target_index]))
					else:
						payload.extend(_pack_rows(deltas[start:end]))
			row += target_rows * int(target.blendShapeNum)
		header.blendShapeList.append(body)
	header.count = len(header.blendShapeList)
	payload.extend(b"\x00" * mesh_format.getPaddingAmount(len(payload), 16))
	return {
		"header": header,
		"shapeRemapNames": remap_names,
		"payload": bytes(payload),
		"keepToonNormals": keep_toon,
		"normalRuns": normal_runs,
	}


def _lod0_range(re_mesh):
	lod = re_mesh.lodHeader.lodGroupList[0]
	vertex_count = sum(int(group.vertexCount) for group in lod.meshGroupList)
	index_count = max(
		(
			int(entry.faceStartIndex) + int(entry.faceCount)
			for group in lod.meshGroupList
			for entry in group.vertexInfoList
			if int(entry.faceCount)
		),
		default=0,
	)
	return lod, vertex_count, index_count


def reserve_re4_normal_recalc(re_mesh, current_offset):
	"""Reserve the LOD0 canonical-table section; returns the offset after it."""
	if getattr(re_mesh, "_re4KeepToonNormals", False):
		re_mesh.fileHeader.normalRecalcOffset = 0
		return current_offset
	_lod, vertex_count, index_count = _lod0_range(re_mesh)
	offset = wilds._align16(current_offset)
	size = (
		NORMAL_RECALC_HEADER_BYTES
		+ wilds._align16(vertex_count * 4)
		+ wilds._align16(index_count * 4)
	)
	re_mesh.fileHeader.normalRecalcOffset = offset
	re_mesh._re4NormalRecalcSize = size
	return offset + size


def _warn_lane_overflow(face_table, lod_range):
	"""Face-table lanes are 10 bits: one 1536-index block holds 1024 vertices.

	Vanilla blocks stay at or below 968; a triangle soup can exceed it, and the
	lanes of those blocks then wrap.
	"""
	canonical = np.frombuffer(face_table, dtype="<u4") & 0x3FFFFF
	starts = []
	for start, end, vertex_start in wilds._face_intervals(lod_range):
		for block in range(start, end, 1536):
			if len(np.unique(canonical[block:min(end, block + 1536)])) > 1024:
				starts.append(vertex_start)
				break
	if starts:
		mesh_format.raiseWarning(
			"RE4 normal recalculation: LOD0 submeshes starting at vertex "
			+ ", ".join(str(value) for value in starts)
			+ " have more than 1024 distinct vertices in one 512-triangle block "
			"(unconnected triangles). Their recalculated normals may be wrong "
			"while shape keys are active."
		)


def finalize_re4_export(re_mesh):
	"""Write the payload start and generate the canonical normal-recalc tables."""
	mesh_header = re_mesh.meshBufferHeader
	payload_start = int(re_mesh._re4BlendPayloadStart)
	mesh_header.vertexElementSize = wilds._signed_short(payload_start & 0xFFFF)
	mesh_header.unkn1 = wilds._signed_short((payload_start >> 16) & 0xFFFF)

	if getattr(re_mesh, "_re4KeepToonNormals", False):
		plan = re_mesh._blendShapeExportPlan
		element = next((e for e in mesh_header.vertexElementList if int(e.typing) == 1), None)
		if element is None or int(element.stride) != 8:
			raise RuntimeError("RE4 toon normals require the exported 8-byte normal/tangent element")
		vertex_count = int(element.posStartOffset) // 12
		normals = np.frombuffer(bytes(mesh_header.vertexBuffer), dtype=np.int8,
			count=vertex_count * 8, offset=int(element.posStartOffset)).reshape((-1, 8))
		payload = bytearray(plan["payload"])
		rows = np.frombuffer(payload, dtype=np.uint8).reshape((-1, 8))
		for byte_start, vertex_start, count in plan["normalRuns"]:
			if byte_start % 8 or vertex_start < 0 or vertex_start + count > vertex_count:
				raise RuntimeError("Invalid RE4 authored-normal payload range")
			start = byte_start // 8
			rows[start:start + count, 4:7] = normals[vertex_start:vertex_start + count, :3].view(np.uint8)
			rows[start:start + count, 7] = 0
		if len(payload) != len(plan["payload"]):
			raise RuntimeError("RE4 authored-normal payload size changed")
		mesh_header.vertexBuffer[payload_start:payload_start + len(payload)] = payload
		plan["payload"] = bytes(payload)
		re_mesh.fileHeader.normalRecalcOffset = 0
		re_mesh._re4NormalRecalcBlob = None
		return
	lod, vertex_count, _index_count = _lod0_range(re_mesh)
	lod_range = {"lod": lod, "baseVertex": 0, "vertexCount": vertex_count, "baseFace": 0}
	# Twins are rows with the same position and normals within 1 degree.
	# Blender vertex identity is not used: imported UV-seam twins are separate
	# Blender vertices, and keeping them apart would show as normal seams.
	face_table, vertex_table = wilds._canonical_tables(
		re_mesh,
		0,
		bytes(mesh_header.faceBuffer),
		bytes(mesh_header.vertexBuffer),
		mesh_header.vertexElementList,
		lod_range,
	)
	_warn_lane_overflow(face_table, lod_range)
	offset = int(re_mesh.fileHeader.normalRecalcOffset)
	vertex_table_offset = offset + NORMAL_RECALC_HEADER_BYTES
	face_table_offset = vertex_table_offset + len(vertex_table)
	blob = (
		struct.pack("<QQ", 1, offset + 16)
		+ struct.pack("<QQ", offset + 32, 0)
		+ struct.pack("<QQ", vertex_table_offset, face_table_offset)
		+ vertex_table
		+ face_table
	)
	if len(blob) != int(re_mesh._re4NormalRecalcSize):
		raise RuntimeError(
			"RE4 normal-recalc tables differ from their reservation: "
			f"{len(blob)}/{int(re_mesh._re4NormalRecalcSize)} bytes"
		)
	if offset + len(blob) != int(re_mesh.fileHeader.blendShapesOffset):
		raise RuntimeError("RE4 normal-recalc tables must end at blendShapesOffset")
	re_mesh._re4NormalRecalcBlob = blob
