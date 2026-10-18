#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Batch KiCad GLB triangle primitives by material without changing geometry.

KiCad exports one primitive per CAD face. Batching avoids Blender's costly
per-primitive processing. Positions, normals, triangle order and node transforms
are preserved; repeated component geometry shares the batched accessors.
Requires NumPy. Restricted deliberately to KiCad's untextured triangle exports.
"""
from collections import defaultdict
import json
from pathlib import Path
import struct
import sys
import numpy as np


def compact(source, destination):
    with Path(source).open('rb') as stream:
        magic, version, size = struct.unpack('<III', stream.read(12))
        assert magic == 0x46546C67 and version == 2
        length, kind = struct.unpack('<II', stream.read(8))
        assert kind == 0x4E4F534A
        doc = json.loads(stream.read(length))
        length, kind = struct.unpack('<II', stream.read(8))
        assert kind == 0x004E4942
        binary = stream.read(length)
    old_accessors, old_views = doc['accessors'], doc['bufferViews']
    accessors, views, result = [], [], bytearray()
    types = {5121: '<u1', 5123: '<u2', 5125: '<u4', 5126: '<f4'}

    def read(index):
        acc = old_accessors[index]
        view = old_views[acc['bufferView']]
        assert 'sparse' not in acc
        width = {'SCALAR': 1, 'VEC3': 3}[acc['type']]
        offset = view.get('byteOffset', 0) + acc.get('byteOffset', 0)
        dtype = np.dtype(types[acc['componentType']])
        return np.ndarray((acc['count'], width), dtype=dtype, buffer=binary,
                          offset=offset, strides=(view.get('byteStride', width*dtype.itemsize), dtype.itemsize))

    def write(array, positions=False):
        result.extend(b'\0' * (-len(result) % 4))
        data = array.tobytes()
        views.append({'buffer': 0, 'byteOffset': len(result), 'byteLength': len(data)})
        result.extend(data)
        acc = {'bufferView': len(views)-1, 'componentType': 5126 if array.dtype.kind == 'f' else 5125,
               'count': len(array), 'type': 'VEC3' if array.shape[1] == 3 else 'SCALAR'}
        if positions:
            acc.update(min=array.min(axis=0).tolist(), max=array.max(axis=0).tolist())
        accessors.append(acc)
        return len(accessors)-1

    cache = {}
    original_count = 0
    for mesh in doc['meshes']:
        original_count += len(mesh['primitives'])
        signature = json.dumps(mesh['primitives'], sort_keys=True)
        if signature not in cache:
            groups = defaultdict(list)
            for primitive in mesh['primitives']:
                assert primitive.get('mode', 4) == 4
                assert set(primitive['attributes']) == {'POSITION', 'NORMAL'}
                groups[primitive.get('material')].append(primitive)
            primitives = []
            for material, items in groups.items():
                positions, normals, indices = [], [], []
                offset = 0
                for item in items:
                    pos = read(item['attributes']['POSITION'])
                    positions.append(pos)
                    normals.append(read(item['attributes']['NORMAL']))
                    idx = read(item['indices']).astype('<u4')
                    assert idx.max() < len(pos)
                    indices.append(idx + offset)
                    offset += len(pos)
                primitive = {'attributes': {
                    'POSITION': write(np.concatenate(positions).astype('<f4'), True),
                    'NORMAL': write(np.concatenate(normals).astype('<f4'))},
                    'indices': write(np.concatenate(indices).astype('<u4')),
                    'mode': 4}
                if material is not None:
                    primitive['material'] = material
                primitives.append(primitive)
            cache[signature] = primitives
        mesh['primitives'] = cache[signature]
    doc['accessors'], doc['bufferViews'] = accessors, views
    doc['buffers'] = [{'byteLength': len(result)}]
    header = json.dumps(doc, separators=(',', ':')).encode()
    header += b' ' * (-len(header) % 4)
    result.extend(b'\0' * (-len(result) % 4))
    with Path(destination).open('wb') as stream:
        stream.write(struct.pack('<III', magic, version, 28 + len(header) + len(result)))
        stream.write(struct.pack('<II', len(header), 0x4E4F534A))
        stream.write(header)
        stream.write(struct.pack('<II', len(result), 0x004E4942))
        stream.write(result)
    print(f'Batched {original_count} primitives into {sum(len(m["primitives"]) for m in doc["meshes"])}')


if __name__ == '__main__':
    compact(*sys.argv[1:])
