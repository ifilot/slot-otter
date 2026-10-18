// SPDX-License-Identifier: GPL-3.0-or-later
import { copyFile, mkdir, readFile, writeFile, stat } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const root = new URL('./', import.meta.url);
for (const directory of ['posters', 'draco']) await mkdir(new URL(`public/${directory}/`, root), { recursive: true });
const cards = { forge: 'slot-otter-cpld-rev1-blender', classic: 'slot-otter-discrete-blender' };
const sizes = {};
for (const [id, name] of Object.entries(cards)) {
  await copyFile(new URL(`../img/thumbnails/${name}.webp`, root), new URL(`public/posters/${id}.webp`, root));
  sizes[id] = (await stat(new URL(`public/models/${id}.glb`, root))).size;
}
await writeFile(new URL('public/models/sizes.json', root), JSON.stringify(sizes));
for (const name of ['draco_decoder.js', 'draco_decoder.wasm', 'draco_wasm_wrapper.js']) {
  await copyFile(new URL(`node_modules/three/examples/jsm/libs/draco/gltf/${name}`, root), new URL(`public/draco/${name}`, root));
}
const credits = `Slot-otter 3D explorer\n\nProject: https://github.com/ifilot/slot-otter\n\nCard geometry: CERN-OHL-S-2.0. Card illustrations: CC-BY-SA-4.0.\nWebsite and export scripts: GPL-3.0-or-later.\nFull project license details: https://github.com/ifilot/slot-otter/blob/master/LICENSE.md\nKiCad library models retain their upstream terms and design exception:\nhttps://www.kicad.org/libraries/license/\n\nThe downloadable models contain only the Slot-otter cards and brackets.\nNo motherboard assets are included. Copper textures are reduced for web use.\n\nThird-party software:\n\n`;
let notice = credits;
for (const [name, path] of [['Google model-viewer (Apache-2.0)', '@google/model-viewer/LICENSE'], ['Three.js (MIT)', 'three/LICENSE']]) {
  notice += `--- ${name} ---\n${await readFile(new URL(`node_modules/${path}`, root), 'utf8')}\n\n`;
}
notice += 'Draco decoder: Copyright Google Inc., Apache-2.0.\nhttps://github.com/google/draco/blob/main/LICENSE\n';
await writeFile(new URL('public/NOTICE.txt', root), notice);
console.log(`Prepared posters, local Draco decoder and credits in ${fileURLToPath(new URL('public/', root))}`);
