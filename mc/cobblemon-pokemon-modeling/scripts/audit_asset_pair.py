#!/usr/bin/env python3
"""Read-only structural audit for a Cobblemon geometry and optional PNG."""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path
from typing import Any


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR":
        raise ValueError("not a valid PNG with an IHDR header")
    return struct.unpack(">II", header[16:24])


def has_cycle(parent_by_name: dict[str, str | None], start: str) -> bool:
    seen: set[str] = set()
    current: str | None = start
    while current is not None and current in parent_by_name:
        if current in seen:
            return True
        seen.add(current)
        current = parent_by_name[current]
    return False


def audit(model_path: Path, texture_path: Path | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "model": str(model_path),
        "texture": str(texture_path) if texture_path else None,
        "errors": [],
        "warnings": [],
        "geometries": [],
    }

    try:
        data = json.loads(model_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        result["errors"].append(f"cannot parse model JSON: {exc}")
        return result

    if data.get("format_version") != "1.12.0":
        result["warnings"].append(
            f"format_version is {data.get('format_version')!r}; the distilled 1.5.2 corpus uses '1.12.0'"
        )

    geometries = data.get("minecraft:geometry")
    if not isinstance(geometries, list) or not geometries:
        result["errors"].append("missing non-empty 'minecraft:geometry' array")
        return result

    declared_sizes: set[tuple[int, int]] = set()
    for index, geometry in enumerate(geometries):
        description = geometry.get("description") or {}
        identifier = description.get("identifier")
        width = description.get("texture_width")
        height = description.get("texture_height")
        if not identifier or identifier == "geometry.unknown":
            result["warnings"].append(f"geometry[{index}] has a missing or placeholder identifier")
        if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
            declared_sizes.add((width, height))
        else:
            result["errors"].append(f"geometry[{index}] has invalid texture dimensions")

        bones = geometry.get("bones") or []
        if not isinstance(bones, list) or not bones:
            result["errors"].append(f"geometry[{index}] has no bones")
            continue

        names = [bone.get("name") for bone in bones]
        valid_names = [name for name in names if isinstance(name, str) and name]
        duplicates = sorted({name for name in valid_names if valid_names.count(name) > 1})
        if duplicates:
            result["errors"].append(f"geometry[{index}] duplicate bone names: {duplicates}")

        name_set = set(valid_names)
        parents: dict[str, str | None] = {}
        for bone in bones:
            name = bone.get("name")
            if not isinstance(name, str) or not name:
                result["errors"].append(f"geometry[{index}] contains a bone without a valid name")
                continue
            parent = bone.get("parent")
            if parent is not None and parent not in name_set:
                result["errors"].append(f"bone {name!r} references missing parent {parent!r}")
            parents[name] = parent if isinstance(parent, str) else None
        cyclic = sorted(name for name in parents if has_cycle(parents, name))
        if cyclic:
            result["errors"].append(f"geometry[{index}] cyclic bone hierarchy touches: {cyclic}")

        cube_count = 0
        plane_count = 0
        fractional_size_count = 0
        fractional_uv_count = 0
        per_face_uv_count = 0
        for bone in bones:
            cubes = bone.get("cubes") or []
            if not isinstance(cubes, list):
                result["errors"].append(f"bone {bone.get('name')!r} has a non-list cubes value")
                continue
            for cube in cubes:
                cube_count += 1
                size = cube.get("size")
                if not isinstance(size, list) or len(size) != 3 or not all(isinstance(v, (int, float)) for v in size):
                    result["errors"].append(f"bone {bone.get('name')!r} contains a cube with invalid size")
                    continue
                if any(v < 0 for v in size):
                    result["errors"].append(f"bone {bone.get('name')!r} contains a negative cube size")
                zeros = sum(v == 0 for v in size)
                if zeros:
                    plane_count += 1
                if zeros > 1:
                    result["warnings"].append(
                        f"bone {bone.get('name')!r} contains a line/point-degenerate cube with size {size}"
                    )
                if any(not float(v).is_integer() for v in size):
                    fractional_size_count += 1

                uv = cube.get("uv")
                if isinstance(uv, dict):
                    per_face_uv_count += 1
                elif isinstance(uv, list) and len(uv) == 2:
                    if any(isinstance(v, (int, float)) and not float(v).is_integer() for v in uv):
                        fractional_uv_count += 1
                else:
                    result["warnings"].append(
                        f"bone {bone.get('name')!r} contains a cube without a recognized Box/per-face UV"
                    )

        if per_face_uv_count:
            result["warnings"].append(
                f"geometry[{index}] uses {per_face_uv_count} per-face UV cubes; the 1.5.2 corpus uses Box UV"
            )
        if fractional_uv_count:
            result["warnings"].append(
                f"geometry[{index}] uses {fractional_uv_count} fractional Box UV origins; corpus origins are integral"
            )

        result["geometries"].append(
            {
                "identifier": identifier,
                "texture_size": [width, height],
                "bones": len(bones),
                "cubes": cube_count,
                "planes": plane_count,
                "fractional_size_cubes": fractional_size_count,
                "per_face_uv_cubes": per_face_uv_count,
            }
        )

    if texture_path:
        try:
            actual = png_size(texture_path)
            result["png_size"] = list(actual)
            if declared_sizes and actual not in declared_sizes:
                result["errors"].append(
                    f"PNG size {actual[0]}x{actual[1]} does not match declared geometry sizes {sorted(declared_sizes)}"
                )
        except Exception as exc:
            result["errors"].append(f"cannot read PNG: {exc}")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path, help="path to a .geo.json file")
    parser.add_argument("--texture", type=Path, help="optional PNG used by the geometry")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    result = audit(args.model, args.texture)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Model: {result['model']}")
        if result.get("texture"):
            print(f"Texture: {result['texture']}")
        for geometry in result["geometries"]:
            print(
                "Geometry {identifier}: {bones} bones, {cubes} cubes, {planes} planes, texture {texture_size}".format(
                    **geometry
                )
            )
        for warning in result["warnings"]:
            print(f"WARNING: {warning}")
        for error in result["errors"]:
            print(f"ERROR: {error}")
        print(f"Result: {len(result['errors'])} error(s), {len(result['warnings'])} warning(s)")
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
