// Slot-otter ISA bracket for the release (discrete-logic) card.
//
// Parametric reconstruction of bracket-release-card.stl. Coordinates match
// the original mesh, so exports can be compared one-to-one:
//
//   X  across the bracket (card side at the clevis lugs, -X)
//   Y  thickness; the outside face of the bracket lies in the plane y = 0,
//      the ribs and lugs point towards -Y, the top flange folds towards +Y
//   Z  along the bracket; the slot tab at the bottom, the screw flange on top
//
// All dimensions in millimetres.

$fn = 64;

eps = 0.01;

// ---------------------------------------------------------------------------
// Bracket plate
// ---------------------------------------------------------------------------

skin_t   = 1;          // front skin, present over the whole outline
plate_t  = 2;          // nominal plate thickness

x_left   = -9.15;      // left edge of the plate
x_right  =  8.992;     // right edge of the plate

// Bottom tab that enters the slot in the PC case
tab_half_w   = 5.1;
tab_bottom   = -60.5;
tab_corner_r = 2;
tab_top      = -52.8;  // start of the 45 degree shoulders

// Top part that carries the flange
top_x_left   = -6.35;
top_x_right  = 12.45;
top_z        = 62;
shoulder_l_z = 51.5;   // left 45 degree shoulder, from (x_left, z) ...
shoulder_r_z0 = 53.9;  // right shoulder from (x_right, z0) ...
shoulder_r_z1 = 57.2;  // ... to (top_x_right, z1)

// The tab stays at skin thickness; the full plate starts with a 45 degree
// step on the back.
thick_start_z = tab_top + (plate_t - skin_t);   // -51.8

// Card-edge groove on the back: plate is skin-thick here
groove_x0 = -7.15;
groove_x1 = -5.15;
groove_top_z = 54.3;

// SD-card window
win_x0 = -6.15;
win_x1 = -3.15;
win_z0 = 13.65;
win_z1 = 29.65;

// ---------------------------------------------------------------------------
// Stiffening ribs on the back
// ---------------------------------------------------------------------------

rib_depth  = 4;                        // y of rib backs = -rib_depth
rib_w      = 2;
rib_x0     = [-5.15, -1.15, 2.85];     // left edges of the three ribs
rib_z0     = -47.75;                   // bottom of the rib back face
rib_z1     = 53.3;                     // top of the rib back face

// ---------------------------------------------------------------------------
// Clevis lugs holding the card (two of them)
// ---------------------------------------------------------------------------

lug_z       = [-28.3, 36.2];   // centre heights of the lower / upper lug
boss_r      = [2.75, 3.0];     // outer radius of the outer boss per lug
lug_hole_y  = -7.22;           // pivot axis position
lug_hole_d  = 3.3;             // M3 clearance
lug_depth   = 12;              // back end of the prongs (y = -lug_depth)
lug_half_h  = 3.05;            // prong half height
lug_end_r   = 1.5;             // rounding of the prong back corners

prong_a_x   = [-9.15, -7.15];  // outer prong
prong_b_x   = [-5.45, -3.15];  // inner prong (merges into rib 1)
prong_b_full = [false, true];  // outer 0.3 mm of the inner prong full height?
boss_x      = [-11.15, -9.15]; // outer boss on prong A
boss_hole_fillet = 1;          // rounded entry of the hole on the boss face

web_half_h  = 2.05;            // half height of the webs tying the lugs in
bridge_half_h = 1.55;          // half height of the bridge under the boss

// ---------------------------------------------------------------------------
// Top screw flange
// ---------------------------------------------------------------------------

flange_z0     = 60;
flange_y1     = 11.5;
flange_r_l    = 1;     // corner radius on the left
flange_r_r    = 2;     // corner radius on the right
flange_edge_r = 1;     // fillet on the outer fold edge
slot_y        = 5.1;   // screw slot centre line
slot_r        = 2.2;
slot_x        = 9.25;  // centre of the slot's round end

gusset_x      = [-2.15, 1.85];
gusset_size   = 4;

// ---------------------------------------------------------------------------
// Thumb socket: a shallow scooped recess in the outside face next to the SD
// window, so a fingertip can press the card in (push-push socket) and grip
// it once it pops out. Set thumb_socket = false for the original bracket.
//
// The scoop is a quarter ellipsoid that starts at the groove edge and only
// cuts into the full-thickness plate on the open (+X) side. It never touches
// the 1 mm skin over the card-edge groove, and its length equals the window
// so it runs out exactly at the window ends: no thin ledges or terraces that
// would print badly.
// ---------------------------------------------------------------------------

thumb_socket    = true;
thumb_cx        = groove_x1;               // starts where the plate is 2 mm
thumb_cz        = (win_z0 + win_z1) / 2;
thumb_half_z    = (win_z1 - win_z0) / 2;   // same length as the window
thumb_half_x    = 7;      // reach towards the open side (+X)
thumb_depth     = 1.2;    // depth at the groove edge (inside the window)
thumb_min_wall  = 0.8;    // plate always left behind the scoop

assert(thumb_depth <= plate_t - thumb_min_wall,
       "thumb_depth leaves less than thumb_min_wall of plate");

// ===========================================================================

// Front outline of the bracket in the X-Z plane.
module outline_2d() {
    union() {
        polygon([
            [-tab_half_w, tab_bottom + tab_corner_r],
            [-tab_half_w, tab_top],
            [x_left, tab_top + (-x_left - tab_half_w)],
            [x_left, shoulder_l_z],
            [top_x_left, shoulder_l_z + (top_x_left - x_left)],
            [top_x_left, top_z],
            [top_x_right, top_z],
            [top_x_right, shoulder_r_z1],
            [x_right, shoulder_r_z0],
            [x_right, tab_top + (x_right - tab_half_w)],
            [tab_half_w, tab_top],
            [tab_half_w, tab_bottom + tab_corner_r],
        ]);
        // rounded bottom of the tab
        hull()
            for (s = [-1, 1])
                translate([s * (tab_half_w - tab_corner_r), tab_bottom + tab_corner_r])
                    circle(r = tab_corner_r);
    }
}

// Extrude an X-Z shape into the bracket thickness (y from -t to 0).
module xz_extrude(t) {
    translate([0, -t, 0]) rotate([-90, 0, 0])
        mirror([0, 1, 0]) linear_extrude(height = t) children();
}

// Extrude a Y-Z polygon along X from x0 to x1.
module yz_extrude(x0, x1) {
    translate([x0, 0, 0]) rotate([90, 0, 90])
        linear_extrude(height = x1 - x0) children();
}

module plate() {
    difference() {
        xz_extrude(plate_t) outline_2d();

        // Tab region is only skin-thick, with a 45 degree transition.
        yz_extrude(-50, 50) polygon([
            [-skin_t, tab_bottom - 1],
            [-skin_t, tab_top],
            [-plate_t, thick_start_z],
            [-plate_t - 1, thick_start_z],
            [-plate_t - 1, tab_bottom - 1],
        ]);

        // Groove for the card edge, closed at the top by a 45 degree ramp.
        yz_extrude(groove_x0, groove_x1) polygon([
            [-skin_t, tab_bottom - 1],
            [-skin_t, groove_top_z],
            [-plate_t, groove_top_z + (plate_t - skin_t)],
            [-plate_t - 1, groove_top_z + (plate_t - skin_t)],
            [-plate_t - 1, tab_bottom - 1],
        ]);
    }
}

module ribs() {
    for (x0 = rib_x0)
        yz_extrude(x0, x0 + rib_w) polygon([
            [-plate_t + eps, rib_z0 - (rib_depth - plate_t)],
            [-rib_depth, rib_z0],
            [-rib_depth, rib_z1],
            [-plate_t + eps, rib_z1 + (rib_depth - plate_t)],
        ]);
}

// Opening for the SD card, with a 45 degree lead-in where the plate is
// only skin-thick (inside the groove).
module sd_window() {
    d = rib_depth - plate_t;
    translate([win_x0, -lug_depth, win_z0])
        cube([win_x1 - win_x0, lug_depth + 1, win_z1 - win_z0]);
    // Rib ends chamfered towards the window
    yz_extrude(win_x0 - eps, win_x1 + eps) polygon([
        [-plate_t + eps, win_z0],
        [-rib_depth - eps, win_z0 - d - eps],
        [-rib_depth - eps, win_z1 + d + eps],
        [-plate_t + eps, win_z1],
    ]);
    // Lead-in in the skin-thick part
    hull() {
        translate([win_x0, -eps, win_z0]) cube([groove_x1 - win_x0, 2 * eps, win_z1 - win_z0]);
        translate([win_x0, -skin_t - eps, win_z0 - skin_t])
            cube([groove_x1 - win_x0, 2 * eps, win_z1 - win_z0 + 2 * skin_t]);
    }
}

// One prong of the clevis (Y-Z profile extruded along X), without hole.
module prong(x0, x1, zc, y_top = -plate_t + eps) {
    yz_extrude(x0, x1)
        hull() {
            translate([y_top - eps, zc - lug_half_h]) square([eps, 2 * lug_half_h]);
            for (s = [-1, 1])
                translate([-lug_depth + lug_end_r, zc + s * (lug_half_h - lug_end_r)])
                    circle(r = lug_end_r);
        }
}

// Half-space { p : n . p <= d } for a unit normal n, as a large cube.
module halfspace(n, d, size = 200) {
    translate(n * d)
        rotate([0, acos(n[2]), atan2(n[1], n[0])])
            translate([-size / 2, -size / 2, -size]) cube(size);
}

// Web tying the lug into the ribs. Between the ribs it is flat for 0.5 mm
// behind the plate and then runs down at 45 degrees to the rib back; right
// of the last rib it is a full-depth block. The right end is a 45 degree
// chamfer in the X-Y plane with two inclined hip planes above and below.
web_end   = x_right + plate_t;   // x - y <= web_end
web_hip   = web_end + 0.779;     // x - y + sqrt(2) |z - zc| <= web_hip

module lug_web(zc) {
    d = rib_depth - plate_t;
    x_rib_end = rib_x0[len(rib_x0) - 1] + rib_w;
    intersection() {
        union() {
            yz_extrude(prong_b_x[1] - eps, x_rib_end + eps) polygon([
                [-skin_t, zc - web_half_h],
                [-plate_t - 0.5, zc - web_half_h],
                [-rib_depth, zc - web_half_h + d - 0.5],
                [-rib_depth, zc + web_half_h - d + 0.5],
                [-plate_t - 0.5, zc + web_half_h],
                [-skin_t, zc + web_half_h],
            ]);
            translate([x_rib_end, -rib_depth, zc - web_half_h])
                cube([x_right - x_rib_end, rib_depth - skin_t, 2 * web_half_h]);
        }
        halfspace([1, -1, 0] / sqrt(2), web_end / sqrt(2));
        translate([0, 0, zc]) halfspace([1, -1,  sqrt(2)] / 2, web_hip / 2);
        translate([0, 0, zc]) halfspace([1, -1, -sqrt(2)] / 2, web_hip / 2);
    }
}

// Strip of the inner prong that reaches past rib 1 over the groove, up to
// the skin. On the upper lug it has the full prong height below the rib
// back; on the lower lug it is limited to the web height throughout.
module prong_b_step(zc, full) {
    x0 = prong_b_x[0];
    x1 = groove_x1 + eps;
    translate([x0, -rib_depth - eps, zc - web_half_h])
        cube([x1 - x0, rib_depth - skin_t + eps, 2 * web_half_h]);
    if (full)
        prong(x0, x1, zc, -rib_depth + eps);
    else
        intersection() {
            prong(x0, x1, zc, -rib_depth + eps);
            translate([x0 - 1, -lug_depth - 1, zc - web_half_h])
                cube([x1 - x0 + 2, lug_depth + 1, 2 * web_half_h]);
        }
}

// Round boss on the outside of prong A plus the bridge back to the plate.
// The bridge is chamfered at 45 degrees on its outer face and front edge.
module boss(zc, r) {
    bx0 = boss_x[0];
    bx1 = boss_x[1] + eps;
    translate([bx0, lug_hole_y, zc]) rotate([0, 90, 0])
        cylinder(r = r, h = bx1 - bx0);
    intersection() {
        translate([0, -eps, 0]) rotate([90, 0, 0])
            linear_extrude(height = -lug_hole_y) polygon([
                [bx0, zc - bridge_half_h + 1],
                [bx0 + 1, zc - bridge_half_h],
                [bx1, zc - bridge_half_h],
                [bx1, zc + bridge_half_h],
                [bx0 + 1, zc + bridge_half_h],
                [bx0, zc + bridge_half_h - 1],
            ]);
        // keep x - y >= x_left
        halfspace([-1, 1, 0] / sqrt(2), -x_left / sqrt(2));
    }
}

// Pivot hole through boss and both prongs, with a rounded entry.
module lug_hole(zc) {
    f = boss_hole_fillet;
    rh = lug_hole_d / 2;
    translate([boss_x[0], lug_hole_y, zc]) rotate([0, 90, 0]) {
        translate([0, 0, -1]) cylinder(d = lug_hole_d, h = prong_b_x[1] - boss_x[0] + 2);
        rotate_extrude() difference() {
            translate([0, -1]) square([rh + f, f + 1]);
            translate([rh + f, f]) circle(r = f);
        }
    }
}

module lug(i) {
    zc = lug_z[i];
    prong(prong_a_x[0], prong_a_x[1], zc);
    prong(groove_x1, prong_b_x[1], zc, -rib_depth + eps);
    prong_b_step(zc, prong_b_full[i]);
    lug_web(zc);
    boss(zc, boss_r[i]);
}

// ---------------------------------------------------------------------------

module flange() {
    translate([0, 0, flange_z0]) linear_extrude(height = top_z - flange_z0)
        difference() {
            hull() {
                translate([top_x_left, -plate_t]) square([top_x_right - top_x_left, eps]);
                translate([top_x_left + flange_r_l, flange_y1 - flange_r_l]) circle(r = flange_r_l);
                translate([top_x_right - flange_r_r, flange_y1 - flange_r_r]) circle(r = flange_r_r);
            }
            hull() {
                translate([slot_x, slot_y]) circle(r = slot_r);
                translate([top_x_right, slot_y - slot_r]) square([1, 2 * slot_r]);
            }
        }
    // gusset under the flange
    yz_extrude(gusset_x[0], gusset_x[1]) polygon([
        [-eps, flange_z0 - gusset_size],
        [gusset_size, flange_z0 + eps],
        [-eps, flange_z0 + eps],
    ]);
}

// Rounded outer edge of the fold between plate and flange.
module fold_edge_cut() {
    r = flange_edge_r;
    yz_extrude(top_x_left - 1, top_x_right + 1) difference() {
        translate([-plate_t - 1, top_z - r]) square([r + 1, r + 1]);
        translate([-plate_t + r, top_z - r]) circle(r = r);
    }
}

module thumb_socket_cut() {
    translate([thumb_cx, 0, thumb_cz])
        intersection() {
            scale([thumb_half_x, thumb_depth, thumb_half_z]) sphere(r = 1, $fn = 128);
            translate([0, -thumb_depth - 1, -thumb_half_z - 1])
                cube([thumb_half_x + 1, thumb_depth + 2, 2 * thumb_half_z + 2]);
        }
}

module bracket() {
    difference() {
        union() {
            plate();
            difference() {
                ribs();
                sd_window();
            }
            for (i = [0 : len(lug_z) - 1]) lug(i);
            flange();
        }
        sd_window();
        for (zc = lug_z) lug_hole(zc);
        fold_edge_cut();
        if (thumb_socket) thumb_socket_cut();
    }
}

// Output orientation. The model is built in the frame of the original mesh
// (tab down, flange up). For printing, the bracket stands on its flange:
// flipped 180 degrees with the top of the flange on the build plate (z = 0).
print_orientation = true;

if (print_orientation)
    translate([0, 0, top_z]) rotate([180, 0, 0]) bracket();
else
    bracket();
