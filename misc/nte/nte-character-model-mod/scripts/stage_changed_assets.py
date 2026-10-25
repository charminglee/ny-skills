# -*- coding: utf-8 -*-
# =================================================
# Author: Nuoyan <https://github.com/charminglee>
# Email : 1279735247@qq.com
# Date  : 2026-10-24
# =================================================


import argparse
import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath


SIDECARS = ('.uasset', '.uexp', '.ubulk', '.uptnl')
INVALID_PACKAGE_CHARACTERS = set(' <>:"\\|?*\t\r\n')


def game_relative_path(package):
    """
    把原版 /Game 长包名转换为 Content 下的安全相对路径。
    """
    if not isinstance(package, str) or not package.startswith('/Game/'):
        raise ValueError('资源必须使用 /Game/ 开头的原版长包名')
    parts = package[len('/Game/'):].split('/')
    if any(not part or part in ('.', '..') for part in parts):
        raise ValueError('包路径包含空段或目录跳转')
    if any(character in INVALID_PACKAGE_CHARACTERS for character in package):
        raise ValueError('包路径含不允许的字符')
    if any('.' in part for part in parts):
        raise ValueError('请使用长包名，不要包含对象后缀或文件扩展名')
    return Path(*PurePosixPath(*parts).parts)


def file_digest(path):
    """
    记录暂存副本的 SHA256，供包体清单核对。
    """
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def prepare_plan(manifest, cooked_content):
    """
    在复制前完整检查修改白名单、原版路径和烘焙伴随文件。
    """
    if not isinstance(manifest, dict):
        raise ValueError('manifest 必须为对象')
    if 'mesh_package' not in manifest:
        raise ValueError('缺少原版网格包路径 mesh_package')
    game_relative_path(manifest['mesh_package'])
    if 'original_references' not in manifest:
        raise ValueError('缺少原版引用基线 original_references')
    references = manifest['original_references']
    if not isinstance(references, dict) or any(
        key not in references for key in ('skeleton', 'physics_asset', 'materials')
    ):
        raise ValueError('引用基线必须显式记录 skeleton、physics_asset、materials')
    for key in ('skeleton', 'physics_asset'):
        value = references[key]
        if value is not None and (
            not isinstance(value, str) or not value.startswith(('/Game/', '/Engine/'))
        ):
            raise ValueError('骨骼/物理资产须为原版对象路径或已核实的 null')
    if not isinstance(references['materials'], list):
        raise ValueError('materials 必须为逐槽引用记录列表')
    if 'assets' not in manifest or not isinstance(manifest['assets'], list) or not manifest['assets']:
        raise ValueError('assets 必须为非空修改白名单')

    # 只接受显式修改的原版资源，不把 Cook 输出中其他依赖加入计划。
    packages = set()
    plan = []
    for asset in manifest['assets']:
        if not isinstance(asset, dict) or 'modified' not in asset or asset['modified'] is not True:
            raise ValueError('白名单每项必须明确 modified: true')
        if 'change' not in asset or not isinstance(asset['change'], str) or not asset['change'].strip():
            raise ValueError('每项必须说明实际修改 change')
        if 'package' not in asset or 'original_package' not in asset:
            raise ValueError('必须记录 package 和 original_package')
        package = asset['package']
        relative = game_relative_path(package)
        if package != asset['original_package']:
            raise ValueError('输出包路径必须与原版引用完全一致；先在 UE 中正确放置/命名')
        if package.casefold() in packages:
            raise ValueError('修改白名单存在重复或仅大小写不同的资源')
        packages.add(package.casefold())
        source_base = cooked_content / relative
        files = []
        for suffix in SIDECARS:
            source = source_base.with_suffix(suffix)
            if not source.is_file():
                if suffix in ('.uasset', '.uexp'):
                    raise ValueError('缺少 UE5.6 松散烘焙文件：' + str(source))
                continue
            if not source.resolve().is_relative_to(cooked_content):
                raise ValueError('烘焙文件通过链接越出了指定 Content 目录')
            files.append((source, Path('HT/Content') / relative.with_suffix(suffix)))
        for source in source_base.parent.glob(source_base.name + '.*'):
            if source.name.endswith(('.ubulk', '.uptnl')) and source.name not in {
                source_base.name + suffix for suffix in SIDECARS
            }:
                raise ValueError('发现未支持的流式伴随文件，先确认格式：' + str(source))
        plan.append({'package': package, 'change': asset['change'], 'files': files})
    return plan


def stage_assets(manifest_path, cooked_content, staging, report_path):
    """
    在全新暂存目录仅复制修改资源，并把审计报告写到包体目录之外。
    """
    cooked_content = Path(cooked_content).resolve()
    staging = Path(staging).resolve()
    report_path = Path(report_path).resolve()
    if not cooked_content.is_dir():
        raise ValueError('cooked-content 必须指向实际烘焙输出的 Content 目录')
    if staging.exists():
        raise ValueError('暂存目录已存在；使用新的任务目录，脚本不删除已有内容')
    if staging.is_relative_to(cooked_content) or cooked_content.is_relative_to(staging):
        raise ValueError('暂存目录与烘焙目录不得互相包含')
    if report_path.is_relative_to(staging):
        raise ValueError('审计报告不得放进包体暂存目录')
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8-sig'))
    plan = prepare_plan(manifest, cooked_content)

    # 全部验证通过后才开始复制；不会重命名 UE 内部资产或改写引用。
    staging.mkdir(parents=True)
    records = []
    expected = set()
    for asset in plan:
        for source, relative in asset['files']:
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            digest = file_digest(target)
            if digest != file_digest(source):
                raise RuntimeError('暂存复制校验失败：' + str(source))
            path = relative.as_posix()
            expected.add(path)
            records.append({'package': asset['package'], 'change': asset['change'], 'path': path, 'bytes': target.stat().st_size, 'sha256': digest})
    actual = {path.relative_to(staging).as_posix() for path in staging.rglob('*') if path.is_file()}
    if actual != expected:
        raise RuntimeError('暂存区包含白名单之外的文件')
    report = {'mesh_package': manifest['mesh_package'], 'original_references': manifest['original_references'], 'packages': [asset['package'] for asset in plan], 'files': records, 'staging': str(staging)}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    """
    从已审查的修改清单生成最小 HT/Content 暂存树。
    """
    parser = argparse.ArgumentParser(description='仅暂存实际修改的 NTE 资源，保持原版包路径')
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--cooked-content', required=True)
    parser.add_argument('--staging', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    try:
        report = stage_assets(args.manifest, args.cooked_content, args.staging, args.report)
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(1, '暂存失败：' + str(error) + '\n')
    print(json.dumps({'packages': len(report['packages']), 'files': len(report['files']), 'staging': report['staging']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
