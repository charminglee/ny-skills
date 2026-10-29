# -*- coding: utf-8 -*-
# =================================================
# Author: Nuoyan <https://github.com/charminglee>
# Email : 1279735247@qq.com
# Date  : 2026-10-29
# =================================================


import json
from collections import defaultdict

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty
from mathutils.kdtree import KDTree


def mesh_object(self, obj):
    """
    限制对象选择框只显示网格。
    """
    return obj.type == 'MESH'


def read_colors(attribute, encoding):
    """
    按用户核实的原版表示读取 RGBA，Alpha 始终保持线性。
    """
    if encoding == 'SRGB_BYTES':
        return [tuple(round(v * 255) / 255 for v in item.color_srgb)
                for item in attribute.data]
    return [tuple(item.color) for item in attribute.data]


def color_index(mesh, attribute, loop_index):
    """
    在角点域和顶点域之间选择实际颜色元素索引。
    """
    if attribute.domain == 'CORNER':
        return loop_index
    return mesh.loops[loop_index].vertex_index


def validate_object(obj):
    """
    检查源网格数据的可用性，不读取修改器求值后的模型。
    """
    if not obj or obj.type != 'MESH' or obj.mode != 'OBJECT':
        raise ValueError("请选择处于对象模式的网格")
    if obj.library or obj.data.library:
        raise ValueError("请先将链接的网格转成本地数据")
    mesh = obj.data
    if 'COL0' not in mesh.color_attributes:
        raise ValueError(obj.name + " 缺少 COL0")
    attribute = mesh.color_attributes['COL0']
    if attribute.domain not in {'POINT', 'CORNER'}:
        raise ValueError("COL0 必须是 POINT 或 CORNER 域")
    if not mesh.polygons or not mesh.uv_layers:
        raise ValueError("网格必须有面和 UV；不按下标直接复制颜色")
    return mesh, attribute


def build_plan(target, reference, encoding, position_tolerance, uv_tolerance):
    """
    按世界空间静态位置、材质槽索引和全部同名 UV 匹配，不猜测冲突数据。
    """
    if target == reference:
        raise ValueError("原版基线与待修复对象不能相同")
    if encoding not in {'LINEAR', 'SRGB_BYTES'}:
        raise ValueError("基线数据表示必须为 LINEAR 或 SRGB_BYTES")
    if position_tolerance <= 0 or uv_tolerance <= 0:
        raise ValueError("位置和 UV 容差必须大于零")
    mesh, attribute = validate_object(target)
    source, source_attribute = validate_object(reference)
    uv_names = [layer.name for layer in mesh.uv_layers]
    if set(uv_names) != {layer.name for layer in source.uv_layers}:
        raise ValueError("两网格的全部 UV 层名称必须一致，请先核对基线")
    if len(mesh.materials) != len(source.materials) or not mesh.materials:
        raise ValueError("两网格必须有相同数量、相同顺序含义的材质槽")

    # 每个材质分区单独建空间索引，UV 作为接缝筛选条件。
    source_colors = read_colors(source_attribute, encoding)
    records = defaultdict(list)
    for face in source.polygons:
        for loop_index in face.loop_indices:
            loop = source.loops[loop_index]
            records[face.material_index].append((
                reference.matrix_world @ source.vertices[loop.vertex_index].co,
                tuple(tuple(source.uv_layers[name].data[loop_index].uv)
                      for name in uv_names),
                source_colors[color_index(source, source_attribute, loop_index)],
            ))
    trees = {}
    for slot, items in records.items():
        tree = KDTree(len(items))
        for index, (position, uvs, rgba) in enumerate(items):
            tree.insert(position, index)
        tree.balance()
        trees[slot] = tree

    # 保留未匹配元素的现有线性浮点值，不量化、不填白、不变更 Alpha。
    values = read_colors(attribute, 'LINEAR')
    proposals = defaultdict(list)
    unmatched_loops = []
    ambiguous_loops = []
    for face in mesh.polygons:
        for loop_index in face.loop_indices:
            element_index = color_index(mesh, attribute, loop_index)
            candidates = []
            if face.material_index in trees:
                vertex_index = mesh.loops[loop_index].vertex_index
                position = target.matrix_world @ mesh.vertices[vertex_index].co
                for coordinate, index, distance in trees[face.material_index].find_range(
                    position, position_tolerance
                ):
                    source_position, source_uvs, rgba = records[face.material_index][index]
                    if all(
                        abs(mesh.uv_layers[name].data[loop_index].uv[axis] - uv[axis])
                        <= uv_tolerance
                        for name, uv in zip(uv_names, source_uvs)
                        for axis in (0, 1)
                    ):
                        candidates.append(rgba)
            if not candidates:
                unmatched_loops.append(loop_index)
                proposals[element_index].append(None)
            elif any(rgba != candidates[0] for rgba in candidates[1:]):
                ambiguous_loops.append(loop_index)
                proposals[element_index].append(None)
            else:
                proposals[element_index].append(candidates[0])

    # POINT 域的共享顶点必须在所有相邻角点上达成一致，否则整个元素不写入。
    restored_elements = []
    conflicting_elements = []
    for index, colors in proposals.items():
        if any(rgba is None for rgba in colors) or any(
            rgba != colors[0] for rgba in colors[1:]
        ):
            conflicting_elements.append(index)
            continue
        values[index] = colors[0]
        restored_elements.append(index)
    report = {
        'target': target.name, 'reference': reference.name,
        'reference_encoding': encoding, 'attribute': 'COL0',
        'reference_storage': source_attribute.data_type,
        'baseline_note': 'BYTE_COLOR 的 color 可能已有量化误差；匹配不证明基线等于游戏原始字节',
        'domain': attribute.domain, 'old_storage': attribute.data_type,
        'new_storage': 'FLOAT_COLOR', 'required_fbx_colors_type': 'LINEAR',
        'position_space': 'WORLD_UNEVALUATED',
        'position_tolerance': position_tolerance, 'uv_tolerance': uv_tolerance,
        'uv_layers': uv_names, 'material_mapping': 'SLOT_INDEX',
        'total_elements': len(values), 'restored_elements': len(restored_elements),
        'changed_elements': sum(
            any(abs(a - b) > 1e-7 for a, b in zip(values[i], attribute.data[i].color))
            for i in restored_elements
        ),
        'preserved_elements': len(values) - len(restored_elements),
        'unmatched_loops': unmatched_loops, 'ambiguous_loops': ambiguous_loops,
        'conflicting_elements': conflicting_elements,
        'validation_scope': 'Blender source only; no FBX/cooked/game validation',
    }
    return values, report


def fix_outline(target, reference, encoding='LINEAR', position_tolerance=0.00001,
                uv_tolerance=0.00001, dry_run=False):
    """
    建立匹配计划，在独立网格副本中只重建 COL0，并保留旧网格供恢复。
    """
    values, report = build_plan(
        target, reference, encoding, position_tolerance, uv_tolerance,
    )
    report['dry_run'] = dry_run
    if not dry_run:
        if not report['restored_elements']:
            raise ValueError("没有可靠匹配的颜色元素，未修改模型；请先使用仅诊断查看报告")
        original = target.data
        working = original.copy()
        try:
            # 新属性保留原域及名称，活动/渲染颜色层按名字恢复。
            colors = working.color_attributes
            active_name = colors.active_color.name if colors.active_color else None
            render_name = colors[colors.render_color_index].name if colors else None
            domain = colors['COL0'].domain
            colors.remove(colors['COL0'])
            restored = colors.new(name="COL0", type='FLOAT_COLOR', domain=domain)
            restored.data.foreach_set('color', [v for rgba in values for v in rgba])
            if active_name:
                colors.active_color = colors[active_name]
            if render_name:
                colors.render_color_index = list(colors.keys()).index(render_name)
            working.update()
        except Exception:
            bpy.data.meshes.remove(working)
            raise
        # 最后一步才切换对象数据，不改基线或共享旧网格的其他对象。
        original.use_fake_user = True
        target.data = working
        report['backup_mesh'] = original.name
        report['result_mesh'] = working.name
    text = bpy.data.texts.new("NTE_Outline_Report.json")
    text.write(json.dumps(report, ensure_ascii=False, indent=2))
    print(text.as_string())
    return report


class NTE_OT_fix_outline_colors(bpy.types.Operator):
    bl_idname = "nte.fix_outline_colors"
    bl_label = "NTE：从原版恢复描边顶点色"
    bl_description = "只恢复可靠匹配的 COL0，保留未匹配数据及修复前网格副本"
    bl_options = {'REGISTER', 'UNDO'}

    target: PointerProperty(name="待修复网格", type=bpy.types.Object, poll=mesh_object)
    reference: PointerProperty(name="原版基线网格", type=bpy.types.Object, poll=mesh_object)
    encoding: EnumProperty(
        name="基线数据表示",
        items=[
            ('LINEAR', "color 线性值", "直接复制已核实的线性控制数据，不做 gamma 转换"),
            ('SRGB_BYTES', "color_srgb 原版整数值", "仅当原版 RGBA 字节位于 color_srgb 时使用"),
        ], default='LINEAR',
    )
    position_tolerance: FloatProperty(name="世界空间位置容差", default=0.00001, min=1e-9, precision=6)
    uv_tolerance: FloatProperty(name="全部 UV 容差", default=0.00001, min=1e-9, precision=6)
    slots_confirmed: BoolProperty(name="已核实两网格各材质槽索引含义一致", default=False)
    dry_run: BoolProperty(name="仅诊断，不修改网格", default=False)

    def draw(self, context):
        """
        显示基线选择和影响匹配的必要条件。
        """
        layout = self.layout
        for name in ('target', 'reference', 'encoding', 'position_tolerance',
                     'uv_tolerance', 'slots_confirmed', 'dry_run'):
            layout.prop(self, name)
        layout.label(text="使用未求值静态网格；原版须处于相同空间及参考姿态。")
        layout.label(text="未匹配/冲突保留现值；导出 FBX 顶点色必须选 LINEAR。")

    def execute(self, context):
        """
        执行显式目标修复，并在文本数据块中留下完整报告。
        """
        if not self.slots_confirmed:
            self.report({'ERROR'}, "请先核实材质槽索引含义一致")
            return {'CANCELLED'}
        try:
            report = fix_outline(
                self.target, self.reference, self.encoding,
                self.position_tolerance, self.uv_tolerance, self.dry_run,
            )
        except (ValueError, RuntimeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self.report({'INFO'}, "匹配 %d，保留 %d；详见 NTE_Outline_Report.json" % (
            report['restored_elements'], report['preserved_elements'],
        ))
        return {'FINISHED'}

    def invoke(self, context, event):
        """
        活动网格作为待修复对象，另一个选中网格作为原版基线建议。
        """
        selected = [obj for obj in context.selected_objects if obj.type == 'MESH']
        active = context.active_object
        if active and active.type == 'MESH':
            self.target = active
            others = [obj for obj in selected if obj != active]
            if len(others) == 1:
                self.reference = others[0]
        return context.window_manager.invoke_props_dialog(self, width=560)


def register():
    """
    支持文本编辑器重复运行，并通过 F3 随时再次调用。
    """
    previous = getattr(bpy.types, NTE_OT_fix_outline_colors.__name__, None)
    if previous:
        bpy.utils.unregister_class(previous)
    bpy.utils.register_class(NTE_OT_fix_outline_colors)


if __name__ == '__main__':
    register()
    if not bpy.app.background:
        bpy.ops.nte.fix_outline_colors('INVOKE_DEFAULT')
