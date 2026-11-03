# SPDX-License-Identifier: CERN-OHL-P-2.0
"""Component placement, harness routing and studio setup."""

import csv
import json
import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Euler, Matrix, Vector

from geometry import MM, boolean, box, collection, cylinder, face, material, mm, move_to, softbox


ROOT = Path(__file__).resolve().parent
FRONT = (math.pi / 2, 0, 0)
SIDE = (0, math.pi / 2, 0)
HEAD_Z = 75.0
FACE_Z = HEAD_Z - 2.6
PITCH = (0, 1.8, 49.2)
MIC = (-15.0, 8.5)
SPEAKER = (0.0, -18.4, 35.0)

SOURCE = {
    "U1": ("VCC-GND YD-ESP32-S3 N16R8", "https://github.com/vcc-gnd/YD-ESP32-S3",
           "Moby mechanical model of the 57.15 × 27.94 mm dual USB-C board and P1/P2 headers"),
    "M1": ("LCDwiki MC096VX SSD1306 0.96 inch", "https://partreel.com/p/ssd1306_module_096/",
           "STEP · PartReel, CC BY 4.0; derived from LCDwiki drawing"),
    "M2": ("INMP441 I2S breakout", "https://ardustore.dk/wp-content/uploads/2026/04/INMP441-Digital-I2C-Mikrofon-Module-Datasheet.pdf",
           "Mechanical reconstruction from breakout drawing and TDK package drawing"),
    "S1": ("C&K JS202011CQN DPDT", "https://www.littelfuse.com/assetdocs/littelfuse-ck-slide-js-series-datasheet?assetguid=aba42b08-0d2c-423b-813d-a2faa5a3bb14",
           "Mechanical reconstruction of the through-hole part from the C&K drawing"),
    "SW1": ("6 mm tactile switch, 4.3 mm height", "https://kicad.github.io/packages3d/Button_Switch_THT.html",
            "STEP · KiCad Libraries, CC BY-SA 4.0 with KiCad library exception"),
    "M3": ("Adafruit 3006 MAX98357A breakout", "https://www.adafruit.com/product/3006",
           "Moby mechanical model of the board with the factory screw terminal"),
    "LS1": ("Same Sky CMS-28528N-L152, 8 Ω 2 W", "https://www.sameskydevices.com/product/resource/cms-28528n-l152.pdf",
            "Mechanical reconstruction from the manufacturer drawing, wire-lead version"),
    "M4": ("TowerPro SG90 9 g", "https://github.com/FreeCAD/FreeCAD-library/tree/master/Electrical%20Parts/Servos/SG-90",
           "STEP · Gafeju via FreeCAD Parts Library, CC BY 3.0"),
    "C4/C5": ("Panasonic EEU-FR1A471, 470 µF 10 V", "https://media.digikey.com/pdf/Data%20Sheets/Panasonic%20Electronic%20Components/EEU-FR_Series.pdf",
              "8 mm radial package, 3.5 mm pitch, 11.5 mm enclosure allowance"),
}


def read_wiring():
    nets = {}
    with (ROOT / "wiring.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            nets.setdefault(row["Net"], []).append(row["Contact"])
    contacts = [contact for terminals in nets.values() for contact in terminals]
    if len(nets) != 22 or len(contacts) != 69 or len(set(contacts)) != len(contacts):
        raise ValueError("Expected 22 nets and 69 distinct connected contacts in wiring.csv")
    return list(nets.items())

def round_y(name, xyz, diameter, depth, group, mat=None):
    obj = cylinder(name, xyz, diameter, depth, group, mat)
    obj.rotation_euler = FRONT
    return obj


def round_x(name, xyz, diameter, depth, group, mat=None):
    obj = cylinder(name, xyz, diameter, depth, group, mat)
    obj.rotation_euler = SIDE
    return obj


def half(obj, y_cut, front, group):
    y = y_cut + (60 if front else -60)
    boolean(obj, box("Assembly split plane", (0, y, 50), (150, 120, 155), 0.5, 0, group))
    return obj


def drill_pattern(target, cutters, group):
    bpy.context.view_layer.update()
    vertices, faces = [], []
    for cutter in cutters:
        offset = len(vertices)
        vertices.extend(cutter.matrix_world @ vertex.co for vertex in cutter.data.vertices)
        faces.extend(tuple(offset + i for i in face.vertices) for face in cutter.data.polygons)
        bpy.data.objects.remove(cutter, do_unlink=True)
    mesh = bpy.data.meshes.new("Drill pattern")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    tool = bpy.data.objects.new("Drill pattern", mesh)
    group.objects.link(tool)
    boolean(target, tool)


def sharp_edges(obj):
    mesh = bmesh.new()
    try:
        mesh.from_mesh(obj.data)
        for edge in mesh.edges:
            if edge.is_manifold and edge.calc_face_angle() > math.radians(27):
                edge.smooth = False
        mesh.to_mesh(obj.data)
        obj.data.update()
    finally:
        mesh.free()


def tube(name, points, radius, group, mat, smooth=True):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 12
    curve.bevel_depth = radius * MM
    curve.bevel_resolution = 3
    curve.use_fill_caps = True
    spline = curve.splines.new("BEZIER" if smooth else "POLY")
    if smooth:
        spline.bezier_points.add(len(points) - 1)
        for point, location in zip(spline.bezier_points, points):
            point.co = mm(location)
            point.handle_left_type = "AUTO"
            point.handle_right_type = "AUTO"
    else:
        spline.points.add(len(points) - 1)
        for point, location in zip(spline.points, points):
            point.co = (*mm(location), 1)
    obj = bpy.data.objects.new(name, curve)
    group.objects.link(obj)
    curve.materials.append(mat)
    return obj


def screw(name, xyz, group, metal, axis="Z", length=5.0, thread=2.0):
    make = {"X": round_x, "Y": round_y, "Z": cylinder}[axis]
    i = "XYZ".index(axis)
    offset = list(xyz)
    offset[i] += (length / 2 - 0.2) * (1 if axis == "Y" else -1)
    head = make(name, xyz, thread * 1.8, 1.25, group, metal)
    boolean(head, make("Screw shank", offset, thread, length, group), "UNION")
    slot = {"X": (0.68, 2.1, 0.48), "Y": (2.1, 0.68, 0.48), "Z": (2.1, 0.48, 0.68)}[axis]
    seat = list(xyz)
    seat[i] += 0.51 * (-1 if axis == "Y" else 1)
    boolean(head, box("Driver slot", seat, slot, 0.17, 0.04, group))
    return head


def tag(obj, ref):
    name, url, origin = SOURCE[ref]
    obj["Ref"] = ref
    obj["Selected part"] = name
    obj["CAD source"] = url
    obj["Geometry provenance"] = origin
    return obj


def add_cad(ref, group, orientation, src_origin, dest, mat, skip=(), fallback=None):
    parts = json.loads((ROOT / "cad" / (ref + ".mesh.json")).read_text(encoding="utf-8"))
    if callable(src_origin):
        src_origin = src_origin(parts)
    rot = Matrix(orientation)
    src_origin, dest = Vector(src_origin), Vector(dest)

    def position(point):
        return tuple(dest + rot @ (Vector(point) - src_origin))

    vertices, faces, indices, palette = [], [], [], {None: 0}
    mesh = bpy.data.meshes.new(ref + " imported CAD mesh")
    mesh.materials.append(mat)
    for index, part in enumerate(parts):
        if index in skip:
            continue
        offset = len(vertices)
        vertices.extend(mm(position(point)) for point in part["v"])
        for triangle, color in zip(part["f"], part["c"]):
            faces.append(tuple(index + offset for index in triangle))
            key = tuple(color) if color else (fallback(index) if fallback else None)
            if key not in palette:
                palette[key] = len(palette)
                if isinstance(key, bpy.types.Material):
                    mesh.materials.append(key)
                    indices.append(palette[key])
                    continue
                name = "CAD " + " ".join(f"{channel:.3f}" for channel in key)
                shade = bpy.data.materials.get(name)
                if shade is None:
                    shade = bpy.data.materials.new(name)
                    shade.diffuse_color = (*key, 1)
                    shade.use_nodes = True
                    shade.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value = (*key, 1)
                    shade.node_tree.nodes.get("Principled BSDF").inputs["Roughness"].default_value = 0.38
                mesh.materials.append(shade)
            indices.append(palette[key])
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh.polygons.foreach_set("material_index", indices)
    obj = bpy.data.objects.new(ref + " · " + SOURCE[ref][0], mesh)
    group.objects.link(obj)
    tag(obj, ref)
    return obj, position, parts


def split_shell(name, center, dims, radius, edge, wall, plane, front, group, mat):
    outer = box(name, center, dims, radius, edge, group, mat)
    inner = box("Shell core", center, tuple(value - 2 * wall for value in dims),
                radius - wall, edge - wall, group)
    boolean(outer, inner)
    return half(outer, plane, front, group)


def materials():
    styles = {
        "skin": ("Fern · matte shell", "ADBF9C", 0.36),
        "dark": ("Basalt · matte shell", "283435", 0.35),
        "accent": ("Persimmon · buttons and foot tips", "DC673D", 0.36),
        "black": ("Charcoal · acoustic mesh and soles", "1B2223", 0.6),
        "trim": ("Shadow green · internal carrier", "3B5350", 0.43),
        "glass": ("Smoked OLED cover", "0E191B", 0.21),
        "cover": ("Optical polycarbonate", "D4E6D9", 0.12),
        "mark": ("Warm gray · legends", "BBC5B9", 0.54),
        "eyes": ("Mint OLED pixels", "86FAD9", 0.37, 0.0, 1.65),
        "pcb": ("Solder mask", "214A3C", 0.49),
        "board": ("Dark printed board", "222A29", 0.52),
        "amp": ("Purple breakout solder mask", "4C3974", 0.48),
        "gold": ("Connector and pad metal", "CAAA56", 0.38, 0.68),
        "steel": ("Stainless steel", "838C91", 0.32, 0.78),
        "plastic": ("IC epoxy and headers", "28292A", 0.56),
        "servo": ("SG90 translucent blue", "306BA4", 0.37),
        "red": ("LED1 red · recording off", "AB283D", 0.27),
        "green": ("LED2 green · mic live", "6DE64A", 0.28, 0.0, 0.95),
        "paper": ("Technical studio floor", "3B514F", 0.6),
    }
    mats = {key: material(*style) for key, style in styles.items()}
    cover = mats["cover"].node_tree.nodes.get("Principled BSDF")
    cover.inputs["Transmission Weight"].default_value = 1.0
    cover.inputs["IOR"].default_value = 1.46
    return mats


def devkit_model(group, m, pin):
    x, y, z = 3.2, 5.3, 32.3  # Top surface of the PCB at its center.
    board = tag(box("U1 · YD-ESP32-S3 PCB", (x, y, z - 0.5),
                    (57.15, 27.94, 1.02), 0.45, 0.04, group, m["board"]), "U1")
    board["Pin source"] = "VCC-GND Studio P1/P2 pin table, 2.54 mm pitch"
    box("U1 · WROOM module substrate and antenna", (x - 22.06, y, z + 0.41),
        (25.5, 18.0, 0.82), 0.32, 0.06, group, m["pcb"])
    box("U1 · WROOM shield can", (x - 19.17, y, z + 1.95),
        (17.6, 15.8, 2.3), 0.48, 0.24, group, m["steel"])
    box("U1 · USB to UART controller", (x + 15.8, y + 6.4, z + 0.46),
        (3.5, 3.5, 0.92), 0.21, 0.08, group, m["plastic"])
    for offset, name in ((-5.85, "Native USB"), (5.65, "UART USB")):
        port = box("U1 · " + name + " connector", (x + 25.8, y + offset, z + 1.1),
                   (6.8, 8.94, 4.2), 0.8, 0.55, group, m["steel"])
        boolean(port, box("USB-C receptacle cavity", (x + 27.1, y + offset, z + 1.28),
                          (5.5, 8.2, 2.6), 0.65, 0.53, group))
        box("U1 · USB-C tongue", (x + 27.0, y + offset, z + 1.22),
            (4.0, 6.1, 0.74), 0.27, 0.12, group, m["plastic"])
    for offset, name in ((-5.0, "RST"), (0.5, "BOOT")):
        box("U1 · " + name + " switch", (x + offset, y + 5.0, z + 0.94),
            (3.0, 5.0, 1.9), 0.26, 0.12, group, m["steel"])

    p1 = {1: "3V3", 4: "GPIO4", 5: "GPIO5", 6: "GPIO6", 7: "GPIO7", 8: "GPIO15",
          9: "GPIO16", 10: "GPIO17", 11: "GPIO18", 12: "GPIO8", 15: "GPIO9", 16: "GPIO10",
          21: "5V", 22: "GND"}
    p2 = {18: "GPIO21"}
    for header, row, contacts in (("P1", y - 12.7, p1), ("P2", y + 12.7, p2)):
        box("U1 · " + header + " spacer", (x - 0.005, row, z - 2.3),
            (55.89, 2.55, 2.5), 0.27, 0.13, group, m["plastic"])
        for number in range(1, 23):
            px = x - 26.675 + 2.54 * (number - 1)
            lead = box(f"U1 · {header}.{number:02d}", (px, row, z - 3.075),
                       (0.65, 0.65, 11.25), 0.075, 0.025, group, m["gold"])
            if number in contacts:
                name = "U1." + contacts[number]
                lead["Contact"] = name
                pin(name, (px, row, z + 2.55), "Main board", (0, 0, 1))


def amplifier_model(group, m, pin):
    x, y, z = 18.8, -4.1, 39.3  # Top surface of the PCB at its center.
    pcb = tag(box("M3 · MAX98357A breakout PCB", (x, y, z - 0.76),
                  (17.8, 19.4, 1.58), 1.25, 0.06, group, m["amp"]), "M3")
    pcb["Assembly variant"] = "Factory screw terminal with a soldered harness"
    for dx in (-6.5, 6.5):
        boolean(pcb, cylinder("M3 mounting hole", (x + dx, y - 7.5, z), 2.3, 3.5, group))
        screw("M3 · PCB mounting screw", (x + dx, y - 7.5, z + 0.61),
              group, m["steel"], length=4.8, thread=2.3)
    box("M3 · Class D amplifier IC", (x, y + 1.0, z + 0.47),
        (3.0, 3.0, 0.9), 0.15, 0.05, group, m["plastic"])
    for dx in (-3.3, 3.3):
        box("M3 · Bypass capacitor", (x + dx, y + 1.0, z + 0.41),
            (2.0, 1.25, 0.78), 0.17, 0.04, group, m["mark"])

    terminal = box("M3 · Two-position terminal block", (x, y - 6.5, z + 4.4),
                   (7.5, 6.8, 8.8), 0.52, 0.19, group, m["plastic"])
    for name, dx in (("OUT+", -1.75), ("OUT-", 1.75)):
        px = x + dx
        boolean(terminal, round_y("Terminal wire opening", (px, y - 8.7, z + 4.2), 2.3, 3.6, group))
        cylinder("M3 · Terminal clamp screw", (px, y - 6.5, z + 8.82), 2.65, 0.36, group, m["steel"])
        pin("M3." + name, (px, y - 9.45, z + 4.2), "Amplifier", (0, -1, 0))
    for i, name in enumerate(("LRC", "BCLK", "DIN", "GAIN", "SD", "GND", "VIN")):
        pin("M3." + name, (x + 7.62 - 2.54 * i, y + 7.0, z + 0.23), "Amplifier", (0, 0, 1), True)


def create_electronics(g, m):
    pins = {}
    steel, gold, plastic = (m[key] for key in ("steel", "gold", "plastic"))

    def pin(name, point, group, direction, show=False):
        assert name not in pins
        pins[name] = (Vector(point), Vector(direction), group)
        if show:
            contact = cylinder(name + " · solder termination", point, 0.78, 0.65, g[group], gold)
            contact.rotation_euler = Vector(direction).to_track_quat("Z", "Y").to_euler()
            contact["Contact"] = name

    devkit_model(g["Main board"], m, pin)

    display, locate, _ = add_cad(
        "M1", g["OLED"], ((1, 0, 0), (0, 0, -1), (0, 1, 0)),
        (0, -2.1, 11.22), (0, -20.0, FACE_Z), m["pcb"],
        fallback=lambda i: m["glass"] if i == 0 else (m["pcb"] if i == 5 else gold),
    )
    for i, name in enumerate(("VCC", "GND", "SCL", "SDA")):
        pin("M1." + name, locate((-3.81 + 2.54*i, -12.4, 0.10)), "OLED", (0, 1, 0))
    # SSD1306 PCB drawing places the active center 2.1 mm off the board center.
    display["Active area mm"] = "21.74 × 10.86; front window aligned to CAD"

    mic = g["Microphone"]
    cx, cy = MIC
    pcb = tag(cylinder("M2 · Ø14 INMP441 breakout PCB", (cx, cy, 87.3), 14.0, 1.55, mic, m["board"]), "M2")
    boolean(pcb, cylinder("M2 acoustic via", (cx, cy, 87.3), 1.0, 3, mic))
    chip = box("M2 · TDK INMP441 MEMS package", (cx, cy, 86.03),
               (4.72, 3.76, 1.0), 0.20, 0.08, mic, steel)
    chip["Datasheet"] = "https://product.tdk.com/system/files/dam/doc/product/sw_piezo/mic/mems-mic/data_sheet/inmp441.pdf"
    gasket = cylinder("M2 · silicone acoustic gasket", (cx, cy, 89.38), 5.8, 2.62, mic, m["black"])
    boolean(gasket, cylinder("Ø1.4 open acoustic path", (cx, cy, 89.38), 1.4, 5, mic))
    for y, row in ((3.81, ("L/R", "WS", "SCK")), (-3.81, ("GND", "VDD", "SD"))):
        for i, name in enumerate(row):
            x = cx - 2.54 + 2.54*i
            cylinder("M2 · plated header pad", (x, cy + y, 86.47), 1.68, 0.12, mic, gold)
            cylinder("M2 · pin", (x, cy + y, 85.82), 0.64, 1.52, mic, gold)
            pin("M2." + name, (x, cy+y, 85.13), "Microphone", (0, 0, -1))

    amplifier_model(g["Amplifier"], m, pin)

    servo, locate, _ = add_cad(
        "M4", g["Servo"], ((0, 0, 1), (0, -1, 0), (1, 0, 0)),
        (0, 16.6, 29.9), (13.5, PITCH[1], PITCH[2]), m["servo"],
    )
    servo["Pitch axis"] = "World X through y=1.8 mm, z=49.2 mm"
    servo["Source dimension"] = "STEP 32.4 mm over flange, 11.8 mm wide, 29.9 mm tall over spline"
    horn = round_x("M4 · SG90 horn hub adapter", (14.75, PITCH[1], PITCH[2]), 6.7, 3.9, g["Neck yoke"], m["trim"])
    boolean(horn, round_x("Spline pocket envelope", (13.25, PITCH[1], PITCH[2]), 4.6, 2.55, g["Neck yoke"]))
    for i, name in enumerate(("brown", "red", "orange")):
        point = locate((1.15*(i-1), 23.0, 2.0))
        sleeve = box("M4 · lead exit strain relief", point, (1.5, 2.5, 0.96),
                     0.33, 0.14, g["Servo"], plastic)
        sleeve["Wire"] = name
        pin("M4." + name, (point[0], point[1]-1.15, point[2]), "Servo", (0, -1, 0))
    # Cradle under the servo ears. Fasteners are modeled with clearances in the clamp.
    for y in (-2.35, 24.85):
        px, py, pz = locate((0, y, 11.0))
        bracket = box("M4 · Servo flange clamp", (px-1.85, py, pz), (3.45, 4.25, 5.7),
                      0.85, 0.48, g["Servo"], m["trim"])
        boolean(bracket, round_x("M2 servo mounting clearance", (px-1.85, py, pz), 1.85, 6.0, g["Servo"]))
        screw("M4 · Servo flange screw", (px+2.65, py, pz), g["Servo"], steel, "X", 6.3, 2.0)

    speaker = g["Speaker"]
    sx, sy, sz = SPEAKER
    frame = tag(round_y("LS1 · CMS-28528N-L152 frame", SPEAKER, 28.0, 5.2, speaker, steel), "LS1")
    boolean(frame, round_y("Diaphragm face recess", (sx, sy - 2.5, sz), 25.2, 2.7, speaker))
    round_y("LS1 · PET diaphragm", (sx, sy - 1.94, sz), 24.9, 0.56, speaker, m["black"])
    round_y("LS1 · magnet back", (sx, sy + 2.13, sz), 16.0, 1.02, speaker, plastic)
    for x in (-16.0, 16.0):
        ear = face("LS1 · screw flange", (x, sy - 0.1, sz), (5.6, 7.5, 1.15), 2.45, 0.3, speaker, steel)
        boolean(ear, round_y("LS1 mounting hole Ø3", (x, sy-0.1, sz), 3.0, 4.2, speaker))
    seal = round_y("LS1 · foam baffle gasket", (0, -21.9, sz), 28.0, 1.8, speaker, m["black"])
    boolean(seal, round_y("Speaker air passage", (0, -21.9, sz), 25.8, 4, speaker))
    for pin_name, x in (("1", -2.0), ("2", 2.0)):
        pin("LS1." + pin_name, (x, -15.6, sz + 8.75), "Speaker", (0, 1, 0), True)

    controls = g["Front controls"]
    sw, locate, _ = add_cad(
        "SW1", controls, ((1, 0, 0), (0, 0, -1), (0, 1, 0)),
        (3.15, -2.25, 4.3), (24.0, -23.9, 34.0), plastic,
    )
    sw["Connection"] = "Opposite corners on the 6 mm four-leg package"
    pin("SW1.1", locate((0.0, 0.0, -3.45)), "Front controls", (0, 1, 0))
    pin("SW1.2", locate((6.3, -4.5, -3.45)), "Front controls", (0, 1, 0))
    face("SW1 · Persimmon push cap", (24.0, -25.0, 34.0),
         (8.35, 5.8, 2.4), 2.12, 0.6, controls, m["accent"])

    switch = tag(face("S1 · C&K through-hole DPDT body", (-24, -18.65, 34),
                      (9.0, 3.6, 3.5), 0.5, 0.17, controls, steel), "S1")
    switch["Logic"] = "ON: A carries microphone SD; B grounds GPIO10/MIC LIVE. OFF throws isolated."
    face("S1 · Switch travel bezel", (-24, -24.6, 34), (9.58, 3.15, 1.2),
         1.28, 0.28, controls, plastic)
    face("S1 · Live position actuator", (-22.65, -25.45, 34), (4.15, 2.72, 2.42),
         0.67, 0.34, controls, m["skin"])
    face("S1 · Actuator stem", (-22.65, -22.9, 34), (2.05, 2.22, 4.9),
         0.48, 0.24, controls, plastic)
    for row, dz in (("A", -1.25), ("B", 1.25)):
        for index, function in enumerate(("off", "common", "on")):
            x = -24.0 + (index-1) * 2.5
            name = f"common {row}" if function == "common" else f"{row}-{function}"
            terminal = round_y("S1." + name, (x, -16.17, 34 + dz), 0.62, 2.1, controls, gold)
            terminal["Contact"] = "S1." + name
            pin("S1." + name, (x, -15.13, 34 + dz), "Front controls", (0, 1, 0))

    for ref, x, lens in (("LED1", 23.8, m["red"]), ("LED2", -23.8, m["green"])):
        diode = face(ref + " · 3 mm indicator lens", (x, -23.5, 38.9),
                     (3.0, 3.0, 4.6), 1.48, 0.82, controls, lens)
        diode["Function"] = "REC, dark at idle" if ref == "LED1" else "MIC LIVE, physically linked to S1"
        round_y(ref + " · flange", (x, -21.08, 38.9), 3.8, 0.65, controls, lens)
        for i, name in enumerate(("A", "K")):
            lead_x = x + (i - 0.5) * 1.27
            round_y(ref + "." + name, (lead_x, -19.5, 38.9), 0.54, 2.85, controls, gold)
            pin(ref + "." + name, (lead_x, -18.1, 38.9), "Front controls", (0, 1, 0))

    # Compact hand-wired carrier for the resistors, bulk capacitors and three buses.
    passive = g["Passive board"]
    substrate = face("P01 · Passive and solder-junction carrier", (-12.5, 19.65, 41.0),
                     (20.3, 12.2, 1.5), 0.65, 0.19, passive, m["pcb"])
    substrate["Construction"] = "Individual copper pads on insulating carrier, 2.54 mm grid. Wire by wiring.csv."
    for x, z in ((-20.95, 45.6), (-4.6, 43.1)):
        boolean(substrate, round_y("Carrier mounting hole", (x, 19.65, z), 2.25, 5.0, passive))
        screw("P01 · Carrier mounting screw", (x, 18.3, z), passive, steel, "Y", 4.5)
    resistor_values = ("330", "330", "100", "10k", "10k", "330", "10k")
    for i, value in enumerate(resistor_values):
        ref = f"R{i+1}"
        x, z = -21.05 + (i % 4) * 4.67, 44.65 - (i // 4) * 2.65
        obj = face(ref + f" · {value} Ω 0805", (x, 18.67, z),
                   (2.0, 1.25, 0.56), 0.14, 0.04, passive, plastic)
        obj["Resistance"] = value + " Ω"
        for j in range(2):
            px = x + (j - 0.5)*1.62
            face(ref + " · resistor solder pad", (px, 18.42, z),
                 (0.9, 1.38, 0.35), 0.18, 0.06, passive, gold)
            pin(ref + "." + str(j+1), (px, 18.24, z), "Passive board", (0, -1, 0))
    for ref, x in (("C4", -19.15), ("C5", -9.8)):
        cap = tag(round_y(ref + " · 470 µF / 10 V", (x, 13.6, 38.88), 8.0, 10.3, passive, plastic), "C4/C5")
        cap["Ref"] = ref
        round_y(ref + " · scored aluminum top", (x, 8.32, 38.88), 7.36, 0.35, passive, steel)
        face(ref + " · negative stripe", (x+3.86, 13.6, 39.3), (0.7, 0.76, 9.0),
             0.23, 0.11, passive, m["mark"])
        for j, pol in enumerate(("+", "-")):
            px = x + (j-0.5)*3.5
            round_y(ref + " · radial lead " + pol, (px, 19.25, 38.88), 0.62, 2.8, passive, gold)
            pin(ref + "." + pol, (px, 20.62, 38.88), "Passive board", (0, 1, 0))
    for ref, group, point in (("C1", "Microphone", (-15, 13.65, 86.15)),
                              ("C2", "OLED", (7.0, -14.5, FACE_Z - 9.9))):
        body = box(ref + " · 100 nF ceramic", point, (2.0, 1.25, 1.1),
                   0.24, 0.12, g[group], m["mark"])
        body["Capacitance"] = "100 nF"
        for j in range(2):
            contact = (point[0]+(j-0.5)*1.64, point[1], point[2])
            pin(ref + "." + str(j+1), contact, group, (0, 1, 0), True)
    return pins


def shifted(point, group, offsets):
    return Vector(point) + Vector(offsets.get(group, (0, 0, 0)))


def create_harness(nets, pins, g, m, offsets, collection_name, single_shell=False, bus_frame=None):
    harness = collection(collection_name)
    head_groups = {"OLED", "Microphone"}
    nc = {"M3.GAIN", "M3.SD", "S1.A-off", "S1.B-off"}
    expected = {name for _, contacts in nets for name in contacts}
    if set(pins) - nc != expected:
        raise ValueError(f"Mismatch in pin assignments: {set(pins) ^ (expected | nc)}")

    color = {
        "3V3": "DC5B4A", "5V": "D78932", "GND": "4B535C",
        "SDA": "4793D2", "SCL": "43B2D4", "SCK": "9C68CB",
        "WS": "7F69BD", "M2.SD": "B776D6", "GPIO6": "9356B7",
        "GPIO10": "58AA73", "GPIO7": "78B5A4", "GPIO21": "DD6C71",
        "GPIO15": "CEB34D", "GPIO16": "D7A458", "GPIO17": "B49250",
        "OUT+": "EC7B47", "OUT-": "805A8A", "SERVO_SIG": "3EAAA8",
        "GPIO18": "2D9E99",
    }
    palette = {}
    for hexcolor in set(color.values()) | {"9CAEB2"}:
        name = "Wire jacket " + hexcolor
        palette[hexcolor] = bpy.data.materials.get(name) or material(name, hexcolor, 0.50)

    graph = {name: set() for name in expected}
    wire_no = 0
    for index, (net, terminals) in enumerate(nets, start=1):
        shade = next((c for key, c in color.items() if key in net), "9CAEB2")
        gage = 0.44 if net in ("3V3", "5V", "GND") else 0.34
        # Power buses have a single solder bridge per supply on the rear carrier.
        common = net in ("3V3", "5V", "GND")
        locations = dict(pins)
        if common:
            x = {"3V3": -19.15, "5V": -12.5, "GND": -5.85}[net]
            point = (x, 18.69, 35.34)
            direction = Vector((0, -1, 0))
            if bus_frame is not None:
                point = bus_frame @ Vector(mm(point)) / MM
                direction = bus_frame.to_3x3() @ direction
            junction = f"JUNCTION.{net}"
            copper = face(net + " · common solder bridge", shifted(point, "Passive board", offsets),
                          (5.3, 1.12, 0.42), 0.30, 0.10, harness, m["gold"])
            if bus_frame is not None:
                copper.rotation_euler = (bus_frame.to_3x3() @ Euler(FRONT).to_matrix()).to_euler()
            copper["Net"] = net
            locations[junction] = (Vector(point), direction, "Passive board")
            graph[junction] = set()
            # Route one trunk per subsystem. Local decoupling branches stay short.
            pairs = []
            by_part = {}
            for terminal in terminals:
                by_part.setdefault(pins[terminal][2], []).append(terminal)
            for local in by_part.values():
                pairs.append((junction, local[0]))
                pairs.extend(zip(local, local[1:]))
        else:
            pairs = [(terminals[0], terminal) for terminal in terminals[1:]]

        for branch, (first, second) in enumerate(pairs):
            a, va, ga = locations[first]
            b, vb, gb = locations[second]
            start, end = shifted(a, ga, offsets), shifted(b, gb, offsets)
            lane = (index % 7 - 3) * 0.92
            departure = start + va * 1.45
            approach = end + vb * 1.45
            middle = []
            if single_shell and ga != gb:
                if not offsets and (ga in head_groups) != (gb in head_groups):
                    head_group, body_point = (ga, b) if ga in head_groups else (gb, a)
                    if head_group == "OLED":
                        middle.append((-12.5 + 0.45*lane, -12.8, 42.8))
                    middle.append((-19.15 + 0.48*lane, -1.6 + 0.38*lane, 44.0))
                    if body_point.z < 38.0:
                        middle.append((-18.7 + 0.48*lane, -1.55 + 0.37*lane, 31.7))
                    elif body_point.x < -25:
                        middle.append((-23.6, body_point.y, 43.4))
                    if ga not in head_groups:
                        middle.reverse()
                elif not offsets and first.startswith("JUNCTION.") and ga == "Passive board":
                    middle = [(-23.0, a.y + 0.35, max(a.z, 42.2)),
                              (max(b.x, -23.0), b.y + 0.85, max(b.z + 1.8, 31.3))]
                else:
                    p = (departure + approach) / 2
                    p.y += 0.8 + lane
                    p.z += 1.7
                    middle = [p]
            elif (ga in head_groups) != (gb in head_groups):
                h, t = (ga, gb) if ga in head_groups else (gb, ga)
                stem = [
                    shifted((-21.5 + lane, 11.7, 61.8), h, offsets),
                    shifted((-21.7 + lane, 11.7, 56.1), "Head shell", offsets),
                    shifted((-22.5 + lane, 11.7, 49.0), "Rear tray", offsets),
                    shifted((-21.1 + lane, 10.6, 43.9), t, offsets),
                ]
                middle = stem if ga in head_groups else list(reversed(stem))
            elif ga != gb:
                if ga in head_groups:
                    middle = [shifted((-15 + lane, 0.2, 69.4 + branch * 0.7), "Head shell", offsets)]
                else:
                    p = a.lerp(b, 0.5)
                    p.y += 2.0 + lane
                    p.z = max(p.z, min(max(a.z, b.z) + 1.4, 47.0))
                    delta = (Vector(offsets.get(ga, (0, 0, 0))) + Vector(offsets.get(gb, (0, 0, 0)))) / 2
                    middle = [p + delta]
            elif (b-a).length > 3.0:
                p = (departure + approach) / 2
                p += (va + vb) * (0.38 + 0.18 * (branch % 3))
                middle = [p]
            points = [start, departure, *middle, approach, end]
            route = tube(f"N{index:02d} · {first} → {second}", points, gage, harness, palette[shade])
            route["Net"] = net
            route["From"] = first
            route["To"] = second
            route["Wire jacket diameter mm"] = round(2*gage, 2)
            route["Layout"] = "Exploded assembly, displayed harness spread" if offsets else "Assembled routing"
            graph[first].add(second)
            graph[second].add(first)
            wire_no += 1

    for net, contacts in nets:
        reached = {contacts[0]}
        todo = [contacts[0]]
        while todo:
            for candidate in graph[todo.pop()] - reached:
                reached.add(candidate)
                todo.append(candidate)
        reached = {p for p in reached if not p.startswith("JUNCTION.")}
        if reached != set(contacts):
            raise ValueError(f"Wire graph failed net isolation audit: {net}")
    return harness, wire_no


def external_diode(g, m):
    body = round_x("D1 · 1N5819 DO-41", (0, 0, 0), 2.71, 5.2, g, m["plastic"])
    body["Circuit"] = "External servo 5 V option, stored disconnected from the USB circuit"
    round_x("D1 · Cathode stripe", (1.74, 0, 0), 2.75, 0.52, g, m["mark"])
    for x in (-7.0, 7.0):
        round_x("D1 · Formed axial lead", (x, 0, 0), 0.82, 9.1, g, m["steel"])


def stage(scene, m):
    studio = collection("Studio and orthographic cameras")
    bpy.ops.mesh.primitive_plane_add(size=2.2, location=(0, 0, -0.000025))
    floor = move_to(bpy.context.object, studio)
    floor.name = "Studio floor"
    floor.data.materials.append(m["paper"])
    softbox("Warm key", (-155, -156, 240), (0, 0, 51), 160, 2.95, (1.0, 0.91, 0.79), studio)
    softbox("Cool fill", (140, -83, 135), (0, 0, 52), 110, 1.2, (0.75, 0.91, 1.0), studio)
    softbox("Edge", (54, 146, 183), (0, 0, 60), 142, 3.2, (0.9, 1, 0.9), studio)
    scene.world = bpy.data.worlds.new("Studio bounce")
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.52, 0.64, 0.68, 1.0)
    background.inputs["Strength"].default_value = 0.25
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    scene.render.resolution_x = 1440
    scene.render.resolution_y = 1180
    scene.render.resolution_percentage = 100
    for obj in studio.objects:
        if obj.type != "CAMERA":
            obj.hide_set(True)
    return floor


def viewport(shot, target, distance):
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                space = area.spaces.active
                space.clip_start = 0.00018
                space.overlay.show_floor = False
                space.overlay.show_axis_x = False
                space.overlay.show_axis_y = False
                space.shading.color_type = "MATERIAL"
                space.region_3d.view_location = mm(target)
                space.region_3d.view_distance = distance * MM
                space.region_3d.view_rotation = shot.rotation_euler.to_quaternion()
                space.region_3d.view_perspective = "ORTHO"
