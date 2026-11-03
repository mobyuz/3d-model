# SPDX-License-Identifier: CERN-OHL-P-2.0
"""Mesh, materials and camera helpers for Moby Mini."""

from math import cos, pi, radians, sin

import bmesh
import bpy
from mathutils import Euler, Vector


MM = 0.001


def mm(values):
    return tuple(value * MM for value in values)


def collection(name):
    group = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(group)
    return group


def move_to(obj, group):
    group.objects.link(obj)
    for other in list(obj.users_collection):
        if other != group:
            other.objects.unlink(obj)
    return obj


def material(name, color, roughness, metallic=0.0, emission=0.0):
    def linear(channel):
        value = int(color[channel:channel + 2], 16) / 255
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    rgba = (*[linear(channel) for channel in (0, 2, 4)], 1.0)
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    node = mat.node_tree.nodes.get("Principled BSDF")
    node.inputs["Base Color"].default_value = rgba
    node.inputs["Roughness"].default_value = roughness
    node.inputs["Metallic"].default_value = metallic
    node.inputs["Emission Color"].default_value = rgba
    node.inputs["Emission Strength"].default_value = emission
    return mat


def rounded_outline(half_w, half_d, radius):
    corners = ((half_w - radius, half_d - radius), (-half_w + radius, half_d - radius),
               (-half_w + radius, -half_d + radius), (half_w - radius, -half_d + radius))
    for quadrant, (cx, cy) in enumerate(corners):
        for segment in range(13):
            angle = (quadrant + segment / 12) * pi / 2
            yield cx + radius * cos(angle), cy + radius * sin(angle)


def box(name, center, dims, radius, edge, group, mat=None, rotation=None):
    """Rounded plan with circular fillets at the top and bottom."""
    half_w, half_d, half_h = (value / 2 for value in dims)
    assert 0 < radius < min(half_w, half_d)
    assert 0 <= edge < min(radius, half_h)
    if edge:
        lower = [(-half_h + edge * (1 - cos(i * pi / 12)),
                  edge * (1 - sin(i * pi / 12))) for i in range(7)]
        rings = lower + [(-z, inset) for z, inset in reversed(lower)]
    else:
        rings = [(-half_h, 0), (half_h, 0)]

    vertices = []
    for z, inset in rings:
        vertices.extend(mm((x, y, z)) for x, y in
                        rounded_outline(half_w - inset, half_d - inset, radius - inset))
    sides = len(vertices) // len(rings)
    top = len(vertices) - sides
    faces = [tuple(reversed(range(sides)))]
    for offset in range(0, top, sides):
        for i in range(sides):
            j = (i + 1) % sides
            faces.append((offset + i, offset + j, offset + sides + j, offset + sides + i))
    faces.append(tuple(range(top, len(vertices))))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    if edge:
        for face in list(mesh.polygons)[1:-1]:
            # Keep the planar panels flat when later cutouts split their faces.
            face.use_smooth = max(abs(axis) for axis in face.normal) < 0.99995
    obj = bpy.data.objects.new(name, mesh)
    group.objects.link(obj)
    obj.location = mm(center)
    if rotation is not None:
        obj.rotation_euler = rotation
    if mat:
        mesh.materials.append(mat)
    return obj


def face(name, center, dims, radius, edge, group, mat=None, twist=0):
    rotation = Euler((pi / 2, 0, 0)).to_matrix() @ Euler((0, 0, radians(twist))).to_matrix()
    return box(name, center, dims, radius, edge, group, mat, rotation.to_euler())


def cylinder(name, center, diameter, depth, group, mat=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=diameter * MM / 2,
                                       depth=depth * MM, location=mm(center))
    obj = bpy.context.object
    obj.name = name
    move_to(obj, group)
    if mat:
        obj.data.materials.append(mat)
    for polygon in obj.data.polygons:
        polygon.use_smooth = len(polygon.vertices) == 4
    return obj


def boolean(target, tool, operation="DIFFERENCE"):
    modifier = target.modifiers.new(tool.name, "BOOLEAN")
    modifier.object = tool
    modifier.operation = operation
    modifier.solver = "EXACT"
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(tool, do_unlink=True)


def text(name, body, location, size, group, mat, rotation=(0, 0, 0)):
    font = bpy.data.curves.new(name, "FONT")
    font.body = body
    font.align_x = "CENTER"
    font.align_y = "CENTER"
    font.size = size * MM
    font.space_character = 1.15
    font.materials.append(mat)
    obj = bpy.data.objects.new(name, font)
    group.objects.link(obj)
    obj.location = mm(location)
    obj.rotation_euler = rotation
    return obj


def check_solid(obj):
    mesh = bmesh.new()
    try:
        mesh.from_mesh(obj.data)
        if any(not edge.is_manifold for edge in mesh.edges):
            raise ValueError(f"{obj.name}: mesh is open or non-manifold")
        if mesh.calc_volume(signed=True) <= 0:
            raise ValueError(f"{obj.name}: invalid solid volume")
        pending = set(mesh.verts)
        frontier = [pending.pop()]
        while frontier:
            vertex = frontier.pop()
            for edge in vertex.link_edges:
                other = edge.other_vert(vertex)
                if other in pending:
                    pending.remove(other)
                    frontier.append(other)
        if pending:
            raise ValueError(f"{obj.name}: disconnected geometry")
    finally:
        mesh.free()


def aim(obj, target):
    obj.rotation_euler = (Vector(mm(target)) - obj.location).to_track_quat("-Z", "Y").to_euler()


def camera(name, location, target, ortho_scale, studio):
    data = bpy.data.cameras.new(name)
    data.type = "ORTHO"
    data.ortho_scale = ortho_scale * MM
    data.clip_start = 0.001
    data.clip_end = 10
    obj = bpy.data.objects.new(name, data)
    studio.objects.link(obj)
    obj.location = mm(location)
    aim(obj, target)
    return obj


def softbox(name, location, target, size, power, color, studio):
    data = bpy.data.lights.new(name, "AREA")
    data.shape = "DISK"
    data.size = size * MM
    data.energy = power
    data.color = color
    obj = bpy.data.objects.new(name, data)
    studio.objects.link(obj)
    obj.location = mm(location)
    aim(obj, target)
    return obj
