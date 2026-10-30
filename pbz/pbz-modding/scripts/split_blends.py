# -*- coding: utf-8 -*-
# =================================================
#   Author: Nuoyan <https://github.com/charminglee>
#   Email : 1279735247@qq.com
#   Date  : 2026-10-30
# =================================================


import argparse
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath

import bpy
import numpy as np
from mathutils import Vector



def property_hash(items, property_name, width, dtype=np.float32):
    """
    计算 Blender 数组属性摘要，用于验证拆分保存前后的数据一致性。
    """
    values = np.empty(len(items) * width, dtype=dtype)
    items.foreach_get(property_name, values)
    return hashlib.sha256(values.tobytes()).hexdigest()



def model_signature(obj):
    """
    记录网格、全部 UV、法线、材质分区、顶点色、骨骼和权重的数据摘要。
    """
    mesh = obj.data
    rig = obj.parent
    group_names = [group.name for group in obj.vertex_groups]
    weights = [
        [(group_names[group.group], group.weight) for group in vertex.groups]
        for vertex in mesh.vertices
    ]
    bones = [
        {
            'name': bone.name,
            'parent': bone.parent.name if bone.parent else "",
            'matrix': [list(row) for row in bone.matrix_local],
        }
        for bone in rig.data.bones
    ]
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.polygons),
        'bones': len(bones),
        'positions': property_hash(mesh.vertices, "co", 3),
        'indices': property_hash(mesh.loops, "vertex_index", 1, np.int32),
        'normals': property_hash(mesh.corner_normals, "vector", 3),
        'material_indices': property_hash(mesh.polygons, "material_index", 1, np.int32),
        'materials': [material.name for material in mesh.materials],
        'uvs': [
            {'name': layer.name, 'hash': property_hash(layer.data, "uv", 2)}
            for layer in mesh.uv_layers
        ],
        'colors': [
            {
                'name': attribute.name,
                'type': attribute.data_type,
                'domain': attribute.domain,
                'hash': property_hash(attribute.data, "color", 4),
            }
            for attribute in mesh.color_attributes
        ],
        'weights': hashlib.sha256(json.dumps(weights).encode()).hexdigest(),
        'skeleton': hashlib.sha256(json.dumps(bones).encode()).hexdigest(),
        'custom_normals': mesh.has_custom_normals,
    }



def material_images(materials):
    """
    收集材质及嵌套节点组中的图像，避免拆分时丢失节点组依赖。
    """
    images = set()
    visited = set()
    pending = [material.node_tree for material in materials if material.node_tree]
    while pending:
        tree = pending.pop()
        if tree in visited:
            continue
        visited.add(tree)
        for node in tree.nodes:
            if node.type == "TEX_IMAGE" and node.image:
                images.add(node.image)
            if node.type == "GROUP" and node.node_tree:
                pending.append(node.node_tree)
    return images


def isolate_model(mesh_object):
    """
    只保留当前部件及其骨架、所用材质和贴图，并解除外部装配依赖。
    """
    rig = mesh_object.parent
    assert rig and rig.type == "ARMATURE"
    keep = {mesh_object, rig}
    for obj in keep:
        for constraint in list(obj.constraints):
            if hasattr(constraint, "target") and constraint.target not in keep:
                obj.constraints.remove(constraint)
    for obj in list(bpy.data.objects):
        if obj not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)

    # 将目标部件放入新的可见集合，恢复独立资源的参考坐标。
    scene = bpy.context.scene
    collection = bpy.data.collections.new("Model")
    scene.collection.children.link(collection)
    for obj in keep:
        for previous in list(obj.users_collection):
            previous.objects.unlink(obj)
        collection.objects.link(obj)
        obj.hide_viewport = False
        obj.hide_render = False
        obj.hide_set(False)
    for other in list(bpy.data.collections):
        if other != collection:
            bpy.data.collections.remove(other)
    bpy.context.view_layer.active_layer_collection = (
        bpy.context.view_layer.layer_collection.children[collection.name]
    )
    scene.camera = None

    # 删除其他部件的数据，避免独立文件附带无关模型和贴图。
    used_materials = set(mesh_object.data.materials)
    used_images = material_images(used_materials)
    for mesh in list(bpy.data.meshes):
        if mesh != mesh_object.data:
            bpy.data.meshes.remove(mesh)
    for armature in list(bpy.data.armatures):
        if armature != rig.data:
            bpy.data.armatures.remove(armature)
    for material in list(bpy.data.materials):
        if material not in used_materials:
            bpy.data.materials.remove(material)
    for image in list(bpy.data.images):
        if image not in used_images:
            bpy.data.images.remove(image)
    bpy.data.orphans_purge(do_recursive=True)

    # 框选当前模型，默认隐藏骨架以便选择网格。
    rig.hide_set(True)
    mesh_object.select_set(True)
    bpy.context.view_layer.objects.active = mesh_object
    corners = [mesh_object.matrix_world @ Vector(corner) for corner in mesh_object.bound_box]
    center = sum(corners, Vector()) / 8.0
    radius = max((corner - center).length for corner in corners)
    direction = Vector((4.0, -6.5, 1.4))
    view_rotation = (-direction).to_track_quat("-Z", "Y")
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                space = area.spaces.active
                space.shading.type = "MATERIAL"
                space.overlay.show_extras = False
                space.region_3d.view_location = center
                space.region_3d.view_distance = max(radius * 2.8, 0.1)
                space.region_3d.view_rotation = view_rotation
    scene['UE_Readme'] = (
        "Standalone LOD0 model with original rig and weights. "
        "Textures use relative paths to YuCong/Textures."
    )
    scene['UE_StandaloneModel'] = mesh_object['UE_Source']
    return len(used_images)



def main():
    """
    从原版完整工程按明确的源包清单拆分独立骨骼模型并回读验证。
    """
    if not bpy.app.background:
        raise RuntimeError("Run in a separate background Blender process")
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", type=Path, required=True)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--asset-root", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    entries = json.loads(args.models.read_text(encoding="utf-8-sig"))
    if not isinstance(entries, list) or not entries:
        raise ValueError("models must be a nonempty Meshes.json array")
    prefix = args.asset_root.replace("\\", "/").rstrip("/") + "/"
    destinations = []
    sources = []
    for item in entries:
        source = item['Source'].replace("\\", "/")
        if not source.startswith(prefix) or not source.endswith(".uasset"):
            raise ValueError("Model source is outside asset-root: " + source)
        relative = PurePosixPath(source[len(prefix):])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid model path")
        destination = args.output / Path(str(relative)).with_suffix(".blend")
        if destination.exists():
            raise FileExistsError(destination)
        sources.append(source)
        destinations.append(destination)
    if len(set(destinations)) != len(destinations):
        raise ValueError("Duplicate output paths")
    master_hash = hashlib.sha256(args.master.read_bytes()).hexdigest()
    expected = []

    # 每次重新加载母本，单个文件的清理只作用于后台进程。
    for source, destination in zip(sources, destinations):
        bpy.ops.wm.open_mainfile(filepath=str(args.master), load_ui=False)
        if bpy.context.object and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        candidates = [
            obj for obj in bpy.data.objects
            if obj.type == "MESH" and 'UE_Source' in obj and obj['UE_Source'] == source
        ]
        if len(candidates) != 1:
            raise ValueError("Expected exactly one mesh for " + source)
        obj = candidates[0]
        signature = model_signature(obj)
        image_count = isolate_model(obj)
        bpy.context.view_layer.update()
        assert model_signature(obj) == signature
        destination.parent.mkdir(parents=True, exist_ok=True)
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(
            filepath=str(destination), check_existing=False, relative_remap=True, compress=True
        )
        expected.append((source, destination, obj.name, signature, image_count))
        print("SAVED", destination, flush=True)

    # 验证实际保存文件的独立性、模型数据和相对纹理路径。
    results = []
    for source, destination, name, signature, image_count in expected:
        bpy.ops.wm.open_mainfile(filepath=str(destination), load_ui=False)
        assert len(bpy.data.objects) == 2
        obj = bpy.data.objects[name]
        assert obj.type == "MESH" and obj.parent.type == "ARMATURE"
        assert model_signature(obj) == signature
        assert obj.visible_get()
        assert any(
            modifier.type == "ARMATURE" and modifier.object == obj.parent
            for modifier in obj.modifiers
        )
        images = [image for image in bpy.data.images if image.source == "FILE"]
        assert len(images) == image_count
        for image in images:
            assert image.filepath.startswith("//")
            assert Path(bpy.path.abspath(image.filepath)).is_file()
            assert image.size[0] > 0 and image.size[1] > 0
        results.append({
            'Source': source, 'File': str(destination),
            'vertices': signature['vertices'], 'triangles': signature['triangles'],
            'bones': signature['bones'], 'textures': image_count,
            'all_checks_passed': True,
        })
    assert hashlib.sha256(args.master.read_bytes()).hexdigest() == master_hash
    report = {
        'master': str(args.master), 'master_sha256': master_hash,
        'models': results, 'all_checks_passed': True,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SPLIT_VERIFIED", len(results), flush=True)


if __name__ == "__main__":
    main()
