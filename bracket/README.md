# Slot-otter bracket mesh sources

The STL meshes in this directory are the original editable design sources,
not exports from a separate parametric CAD project. Edit them with a mesh
editor and retain the modified mesh as source when sharing changes.

- `bracket-prototype-card.stl`: bracket for the historical prototype.
- `bracket-release-card.stl`: bracket for the historical discrete-logic card.
- `bracket-release-card.scad`: parametric OpenSCAD reconstruction of
  `bracket-release-card.stl` (same coordinate frame; matches the mesh to
  within curve tessellation), with an optional thumb socket around the SD
  window (`thumb_socket`, on by default). Export with
  `openscad -o bracket-release-card-thumb.stl bracket-release-card.scad`.
- `bracket-release-card-thumb.stl`: export of the `.scad` with the thumb socket,
  in print orientation (standing on the flange, tab up). Set
  `print_orientation = false` to export in the frame of the original mesh.

Check fit before adapting these meshes to CPLD revision 1.0. Project-authored
mechanical designs use CERN-OHL-S-2.0; this documentation uses CC-BY-SA-4.0.
See [licensing scope](../LICENSE.md).
