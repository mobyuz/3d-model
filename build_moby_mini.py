# SPDX-License-Identifier: CERN-OHL-P-2.0
"""Moby Mini. A single hollow helmet mounted directly on two feet."""

import csv
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from geometry import (
    MM, boolean, box, camera, check_solid, collection, cylinder, face, mm,
    text,
)
from assembly_support import (
    FRONT, SOURCE, create_electronics, create_harness, drill_pattern, external_diode,
    materials, read_wiring, round_x, round_y, screw, sharp_edges, split_shell, stage,
    viewport,
)


FACE_Z = 38.6
AXIS_Y = -0.35
AXIS_Z = 36.70
SPEAKER_Z = 39.8
SHELL = (0, 0, 34.9), (74.8, 56.0, 51.8), 15.5, 7.2, 2.45

SPREAD = {
    "Head shell": (0, 38, 15), "Visor": (-27, -39, 5), "OLED": (-51, -7, 29),
    "Microphone": (57, -2, 39), "Front controls": (-47, -11, -6),
    "Main board": (0, -1, -4), "Passive board": (-29, 15, 5),
    "Speaker": (49, 8, 13), "Amplifier": (29, -16, -3), "Servo": (9, -2, 41),
    "Neck yoke": (0, -8, 23), "Carrier": (0, 19, -3),
    "Leg L": (-3, 0, -7), "Leg R": (10, 0, -7),
    "Sole L": (-3, 0, -13), "Sole R": (10, 0, -13),
}


def transform(old, new, angle=0, axis="Z"):
    return Matrix.Translation(Vector(mm(new))) @ Matrix.Rotation(math.radians(angle), 4, axis) @ (
        Matrix.Translation(-Vector(mm(old)))
    )


def fitted_electronics(groups, styles):
    pins = create_electronics(groups, styles)
    move = {
        "OLED": transform((0, -20, 72.4), (0, -24.0, FACE_Z)),
        "Microphone": transform((0, 0, 87.3), (0, 0, 54.4)),
        "Front controls": transform((0, 0, 34), (0, -2.1, 19.5)),
        "Main board": transform((0, 0, 32.3), (0, 1.0, 22.7)),
        "Passive board": transform((-12.5, 19.65, 41.0), (-30.8, 6, 46.2), 90),
        "Speaker": transform((0, -18.4, 35), (0, 22.55, SPEAKER_Z), 180),
        "Amplifier": transform((18.8, -4.1, 39.3), (30.95, 5.2, 43.35), -90, "Y"),
        "Servo": transform((0, 1.8, 49.2), (0, AXIS_Y, AXIS_Z)),
    }
    move["Neck yoke"] = move["Servo"]
    bpy.context.view_layer.update()
    for group, matrix in move.items():
        for obj in groups[group].objects:
            obj.matrix_world = matrix @ obj.matrix_world
    for name, (point, direction, group) in pins.items():
        matrix = move[group]
        pins[name] = (matrix @ Vector(mm(point)) / MM, matrix.to_3x3() @ direction, group)
    return pins, move


def enclosure(g, m):
    hood, front = g["Head shell"], g["Visor"]
    skin, dark, steel, trim = (m[key] for key in ("skin", "dark", "steel", "trim"))
    rear = split_shell("H01 · Single head rear shell", *SHELL, -8.20, False, hood, skin)
    mask = split_shell("H02 · Single head face shell", *SHELL, -8.52, True, front, dark)

    # The only enclosure seam is around the removable front visor.
    side_rotation = Matrix(((0, 0, 1), (1, 0, 0), (0, 1, 0))).to_euler()
    for shell, group in ((rear, hood), (mask, front)):
        boolean(shell, box("Twin USB-C plug slot", (36.3, 6.3, 23.85),
                           (29.1, 8.6, 13.5), 2.5, 0.34, group,
                           rotation=side_rotation))
    bezel = box("H08 · Recessed dual USB-C guide", (33.02, 6.28, 23.81),
                (26.0, 7.8, 0.88), 2.10, 0.23, g["Carrier"], dark, side_rotation)
    for y in (0.45, 11.95):
        boolean(bezel, box("Individual USB-C plug nose opening", (33.02, y, 23.80),
                           (10.1, 5.45, 3.0), 1.58, 0.27, g["Carrier"], rotation=side_rotation))
    check_solid(bezel)

    # Isolated acoustic paths. The 28 mm driver faces the back and the MEMS inlet faces up.
    boolean(rear, round_y("Rear speaker opening", (0, 27.4, SPEAKER_Z), 26.0, 9.0, hood))
    grille = round_y("H03 · Rear acoustic grille", (0, 27.35, SPEAKER_Z), 25.82, 1.65, hood, dark)
    cutters = []
    for row in range(-3, 4):
        for col in range(-3, 4):
            x, z = col * 3.25 + (row % 2) * 1.625, row * 3.25
            if x*x + z*z < 11.55**2:
                cutters.append(round_y("Ø1.6 perforation", (x, 27.35, SPEAKER_Z + z), 1.60, 4, hood))
    drill_pattern(grille, cutters, hood)
    for x in (-16.0, 16.0):
        boolean(rear, round_y("Rear speaker screw boss", (x, 25.0, SPEAKER_Z), 3.8, 5.0, hood), "UNION")
        boolean(rear, round_y("Speaker M2.5 pilot", (x, 24.3, SPEAKER_Z), 2.0, 4.0, hood))
        screw("LS1 · Rear speaker fastener", (x, 21.72, SPEAKER_Z), g["Speaker"], steel, "Y", 5.1, 2.5)
    boolean(rear, cylinder("Top microphone inlet", (-15, 8.5, 59.9), 2.15, 7.0, hood))
    mic_seat = cylinder("M2 · Breakout retaining collar", (-15, 8.5, 53.28), 15.8, 1.20, g["Microphone"], trim)
    boolean(mic_seat, cylinder("Space for INMP441 pins and capsule", (-15, 8.5, 53.3), 11.0, 3.0, g["Microphone"]))

    # Clear opening through a tinted optical window. Emissive pixels stay on the OLED.
    boolean(mask, face("SSD1306 viewing aperture", (0, -27.65, FACE_Z),
                       (22.65, 11.85, 10.0), 1.25, 0.35, front))
    face("H04 · Optical polycarbonate window", (0, -27.72, FACE_Z),
         (22.45, 11.64, 0.64), 1.15, 0.16, front, m["cover"])
    for x, tilt in ((-5.0, -9), (5.0, 9)):
        face("M1 · Eyes on the SSD1306 active plane", (x, -24.10, FACE_Z + 0.2),
             (4.9, 6.75, 0.13), 1.95, 0.035, g["OLED"], m["eyes"], twist=tilt)
    for x in (-11.65, 11.65):
        for z in (FACE_Z + 2.1 - 11.9, FACE_Z + 2.1 + 11.9):
            boss = round_y("OLED mounting boss", (x, -25.2, z), 4.05, 4.2, front)
            boolean(mask, boss, "UNION")
            boolean(mask, round_y("OLED M2 pilot", (x, -24.2, z), 1.65, 4.1, front))
            fastener = screw("M1 · OLED screw", (x, -18.2, z), g["OLED"], steel, "Y", 7.0)
            fastener.rotation_euler.rotate_axis("Z", math.pi)

    for x in (-23.8, 23.8):
        boolean(mask, round_y("3 mm status LED hole", (x, -27.25, 24.4), 3.3, 8.3, front))
    boolean(mask, face("DPDT slide access", (-24, -27.2, 19.5), (10, 3.68, 9.4), 1.52, 0.30, front))
    boolean(mask, face("Talk button access", (24, -27.2, 19.5), (8.93, 6.35, 9.4), 2.20, 0.3, front))
    text("Moby marking", "moby", (0, -28.021, 21.0), 3.45, front, m["mark"], FRONT)
    text("Mute marking", "MUTE", (-23.6, -28.045, 27.3), 1.44, front, m["mark"], FRONT)
    text("Talk marking", "TALK", (23.6, -28.045, 27.3), 1.44, front, m["mark"], FRONT)

    # The visor screws enter from the sides into the mating seam ears.
    for side in (-1, 1):
        x = 33.4 * side
        z = 52.8
        ear = box("Visor seam tab", (x, -8.9, z), (5.8, 8.7, 5.2), 1.75, 0.65, front)
        boolean(mask, ear, "UNION")
        boolean(rear, box("Mating seam-tab pocket", (x, -7.05, z), (6.3, 5.1, 5.6), 1.55, 0.4, hood))
        boolean(mask, round_x("Visor tab M2 pilot", (x, -6.9, z), 1.65, 6.9, front))
        boolean(rear, round_x("Side access to visor screw", (35.65*side, -6.9, z), 2.3, 6.9, hood))
        s = screw("H05 · Visor seam screw", (36.7*side, -6.9, z), front, steel, "X", 5.3, 2.0)
        if side < 0:
            s.rotation_euler = (0, -math.pi / 2, 0)

    # Low profile board rails underneath the PCB, clear of both 22-pin strips.
    for y in (2.2, 14.8):
        rail = box("H06 · DevKit underside rail", (2.8, y, 20.9), (44.0, 1.65, 1.5),
                   0.61, 0.26, g["Carrier"], trim)
        for x in (-17, 20):
            rib = box("PCB rail support", (x, y, 15.3), (4.2, 1.6, 11.2), 0.59, 0.29, hood)
            boolean(rear, rib, "UNION")
        check_solid(rail)

    # Slots around the fixed foot uprights allow the shell to pitch as a unit.
    for x in (-20.4, 20.4):
        for shell, group in ((rear, hood), (mask, front)):
            boolean(shell, box("Foot upright travel aperture", (x, -12.0, 9.45),
                               (6.2, 13.6, 8.5), 2.5, 0.45, group))
    # Passive side of the hinge attaches to the moving shell.
    hinge = box("H07 · Left fixed-foot pivot saddle", (-30.55, AXIS_Y, AXIS_Z),
                (10.2, 5.8, 4.4), 1.75, 0.55, hood)
    boolean(rear, hinge, "UNION")
    boolean(rear, round_x("Passive pivot pin bore", (-27.1, AXIS_Y, AXIS_Z), 2.35, 11.7, hood))
    # The servo clamps sit on a cantilever above the main PCB.
    support = box("Servo saddle cross rail", (-21.8, 5.65, 28.95),
                  (29.2, 2.6, 1.8), 0.83, 0.32, hood)
    boolean(rear, support, "UNION")
    support = box("Servo saddle longitudinal rail", (-7.95, 4.5, 28.95),
                  (4.65, 29.4, 1.8), 1.1, 0.32, hood)
    boolean(rear, support, "UNION")
    for y in (-8.6, 18.6):
        depth = 2.25 if y > 0 else 3.2
        support = box("Servo clamp seat", (-7.95, y, 31.18), (4.1, depth, 5.35),
                      0.78, 0.43, hood)
        boolean(rear, support, "UNION")
    for z in (36.85, 49.85):
        boolean(rear, round_x("M3 · Right-side amplifier boss", (34.48, -2.3, z), 3.9, 2.45, hood), "UNION")
        boolean(rear, round_x("M3 · Amplifier pilot", (34.05, -2.3, z), 1.85, 2.65, hood))
        washer = round_x("M3 · Insulating shoulder washer", (32.91, -2.3, z), 4.25, 0.61,
                         g["Amplifier"], trim)
        boolean(washer, round_x("Clear the plated pad", (32.91, -2.3, z), 3.35, 1.4, g["Amplifier"]))
    for y, z in ((-2.45, 50.8), (13.9, 48.3)):
        boolean(rear, round_x("P01 · Left-side carrier boss", (-33.66, y, z), 3.6, 4.18, hood), "UNION")
        boolean(rear, round_x("P01 · Carrier pilot", (-32.42, y, z), 1.65, 2.2, hood))
    for part in (rear, mask, grille, mic_seat):
        check_solid(part)
        sharp_edges(part)
        part["Topology"] = "Connected closed mesh verified"
    return rear, mask


def feet_and_pivot(g, m):
    for side, suffix in ((-1, "L"), (1, "R")):
        group = g["Leg " + suffix]
        x = side * 20.4
        foot = box(f"F01{suffix} · Short foot bolted to internal upright", (x, -3.45, 4.42),
                   (22.4, 39.0, 5.78), 8.3, 1.72, group, m["skin"])
        shoe = box("Toe bumper", (x, -22.1, 3.95), (13.4, 3.9, 2.6),
                   1.7, 0.65, group, m["accent"])
        boolean(foot, cylinder("M2.5 foot clearance", (x, -12, 4.6), 2.8, 8.5, group))
        boolean(foot, cylinder("Foot screw head pocket", (x, -12, 2.0), 5.6, 3.05, group))
        sole = box(f"F02{suffix} · Anti-slip sole", (x, -3.45, 0.84),
                   (22.0, 38.7, 1.68), 8.05, 0.49, g["Sole " + suffix], m["black"])
        boolean(sole, cylinder("Foot screw access through sole", (x, -12, 0.84), 5.6, 3.5, g["Sole " + suffix]))
        bolt = screw(f"F03{suffix} · Foot screw", (x, -12, 3.5), group, m["steel"], length=8.7, thread=2.5)
        bolt.rotation_euler.rotate_axis("X", math.pi)
        fork = g["Neck yoke"]
        upright = box(f"J01{suffix} · Internal fixed-foot upright", (x, -12, 22.08),
                      (4.4, 5.4, 30.4), 1.55, 0.55, fork, m["trim"])
        boolean(upright, cylinder("Foot screw blind pilot", (x, -12, 8.15), 2.05, 5.4, fork))
        pivot_x = -21.1 if side < 0 else 17.5
        arm = box("Pivot arm", ((x + pivot_x)/2, -5.8, AXIS_Z),
                  (abs(x-pivot_x) + 4.4, 16.2, 5.35), 1.72, 0.58, fork, m["trim"])
        boolean(upright, arm, "UNION")
        boolean(upright, round_x("Coaxial hinge bore", (pivot_x, AXIS_Y, AXIS_Z), 2.35, 11.1, fork))
        if side < 0:
            round_x("J02 · Passive pin", (-23.0, AXIS_Y, AXIS_Z), 2.18, 9.7, fork, m["steel"])
        else:
            screw("J03 · Servo horn axle screw", (19.65, AXIS_Y, AXIS_Z), fork, m["steel"], "X", 7.1, 2.0)
        for part in (foot, sole, upright):
            check_solid(part)
            sharp_edges(part)


def notes(nets):
    note = bpy.data.texts.new("00 O‘QING · Moby Mini")
    note.write(
        "MOBY MINI\n"
        "CERN-OHL-P-2.0 · Moby design. See LICENSE and THIRD_PARTY.md.\n"
        "Bitta bosh-qobiq va bevosita ulangan ikki oyoq. Uzunlik birligi millimetr.\n"
        "Oyoqlar ichki tirgaklarga mahkamlanadi. SG90 va chap koaksial pin qobiqni "
        "oyoq tayanchlariga nisbatan ozgina burish uchun joylashtirilgan.\n"
        "Oldda OLED va boshqaruv, orqada dinamik, tepada INMP441 akustik kanali.\n\n"
        "Simlar wiring.csv faylidagi 22 tarmoq va 69 kontaktni ifodalaydi. Sochilgan sahnada simlar "
        "qismlarni ko‘rsatish uchun yoyilgan. Real sim uzunligi va bo‘shligi prototipda o‘lchanadi.\n"
        "D1 tashqi 5 V servo varianti, USB yig‘masida ajratilgan. S1 OFF tashlamalari, "
        "M3.GAIN va M3.SD ochiq. Dinamik chiqishlari GND ga ulanmaydi.\n"
        "Servo yurishi, tolerans, USB quvvat va haqiqiy detallar bilan moslik "
        "fizik prototipda tekshiriladi.\n\n"
    )
    for ref, (name, url, provenance) in SOURCE.items():
        note.write(f"{ref}  {name}\n{provenance}\n{url}\n\n")
    for i, (net, contacts) in enumerate(nets, 1):
        note.write(f"{i:02d}  {net}\n      {', '.join(contacts)}\n")


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene["Configuration"] = "Single head shell and two feet; Core v1 with A/B installed"
    scene["Nominal overall size mm"] = "74.8 × 57 × 60.8 excluding cable"
    bpy.context.preferences.filepaths.save_version = 0
    labels = {"Neck yoke": "Internal foot pivots", "Leg L": "Left foot", "Leg R": "Right foot"}
    groups = {name: collection(f"{n:02d} · {labels.get(name, name)}") for n, name in enumerate(SPREAD, 1)}
    m = materials()
    pins, frames = fitted_electronics(groups, m)
    enclosure(groups, m)
    feet_and_pivot(groups, m)
    nets = read_wiring()
    harness, wires = create_harness(nets, pins, groups, m, {}, "17 · Installed wiring",
                                   single_shell=True, bus_frame=frames["Passive board"])
    option = collection("18 · D1 external servo power option")
    external_diode(option, m)
    option.hide_render = True
    option.hide_viewport = True
    notes(nets)
    with (ROOT / "moby-mini-netlist.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        table = csv.writer(handle)
        table.writerow(("Net number", "Net", "Contact", "Assembly group", "X mm", "Y mm", "Z mm"))
        for n, (net, terminals) in enumerate(nets, 1):
            for name in terminals:
                point, _, group = pins[name]
                table.writerow((n, net, name, labels.get(group, group), *(round(v, 3) for v in point)))
    floor = stage(scene, m)
    studio = floor.users_collection[0]
    hero = camera("Moby Mini front", (143, -248, 100), (0, -3, 29.8), 110, studio)
    camera("Moby Mini rear and ports", (146, 220, 105), (0, 0, 29.4), 110, studio)
    explode = camera("Moby Mini exploded", (162, -294, 146), (-1, -2, 44), 202, studio)
    scene.camera = hero
    scene.name = "Moby Mini · assembled"
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 1100
    scene.render.filepath = "//moby-mini-assembled.png"
    scene["Netlist audit"] = f"22 nets / 69 contacts / {wires} wires and three common solder bridges"
    viewport(hero, (0, 0, 30), 141)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.overlay.show_extras = False
                area.spaces.active.overlay.show_relationship_lines = False
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "moby-mini-assembled.blend"))

    for obj in list(harness.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.collections.remove(harness)
    for group, delta in SPREAD.items():
        for obj in groups[group].objects:
            obj["Assembled location mm"] = [round(v/MM, 4) for v in obj.location]
            obj.location += Vector(mm(delta))
    create_harness(nets, pins, groups, m, SPREAD, "17 · Exploded wiring",
                   single_shell=True, bus_frame=frames["Passive board"])
    option.hide_render = False
    option.hide_viewport = False
    for obj in option.objects:
        obj.location += Vector(mm((-63, -17, 12)))
    scene.camera = explode
    scene.name = "Moby Mini · exploded"
    scene.render.resolution_x = 1680
    scene.render.resolution_y = 1250
    scene.render.filepath = "//moby-mini-exploded.png"
    floor.location.z = -0.014
    viewport(explode, (0, -2, 44), 250)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "moby-mini-exploded.blend"))
    return {"files": ["moby-mini-assembled.blend", "moby-mini-exploded.blend"],
            "nets": len(nets), "contacts": 69, "wire_objects": wires, "objects": len(scene.objects)}


if __name__ == "__main__":
    print(build())
