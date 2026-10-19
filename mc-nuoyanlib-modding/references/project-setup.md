# 从一般项目模板建项并安装 nuoyanlib

## 先确认三个名称

| 参数 | 示例 | 实际用途 |
| --- | --- | --- |
| 项目根目录 | `E:\MCMod\Mod\MyProject\CloudFlight` | 包含开发脚本、资源和打包目录的工作区 |
| 模组名称 | `CloudFlight` | `MOD_NAME`、manifest 显示名；小写后形成 `cloudflight_scripts` |
| 顶层目录名称 | `cloud_flight` | 项目内同时包含 `bp`、`rp` 的目录 |

项目根目录名称、模组名称和顶层目录名称是不同概念。模块包名按 `MOD_NAME.lower() + "_scripts"` 形成，不按顶层目录推导。模组名称应能生成合法的 Python 2 包名，通常采用 ASCII 字母开头的英文名称；中文显示名称可在建项后单独调整 manifest。

## 沿用模板自带的 setup.py

模板根目录是 `E:\MCMod\Mod\模板\一般项目`，包含 `setup.py`、`cleaner.py`、`assets/` 和 `template/`。先复制整个模板根目录，再在项目副本里运行建项脚本：

```powershell
$template_root = 'E:\MCMod\Mod\模板\一般项目'
$project_root = 'E:\MCMod\Mod\MyProject\CloudFlight'
Copy-Item -LiteralPath $template_root -Destination $project_root -Recurse
Set-Location -LiteralPath $project_root
py -3 .\setup.py
```

复制前确认目标根目录不存在，防止 `Copy-Item` 把模板嵌套进已有目录。模板 `setup.py` 会原地改文件、重命名目录，应在副本内运行一次。依次输入 `CloudFlight` 和 `cloud_flight`。

当前模板脚本会执行：

1. 在 `common/constant.py` 中替换 `$DATE$`、`$MOD_NAME$`，在 `common/config.py` 及主系统文件中替换日期占位符。
2. 在 BP、RP 的 `manifest.json` 中替换模组名称和 `$UUID1$` 至 `$UUID4$`，生成四个不同的 UUID。
3. 从硬编码路径 `E:/MCMod/nuoyanlib/src/nuoyanlib` 复制源码到 `template/bp/template_scripts/nuoyanlib`，忽略 `*.pyc` 与 `__pycache__`。
4. 将 `template_scripts` 改为 `cloudflight_scripts`，将 `template` 改为 `cloud_flight`。

因此，默认建项过程已安装 nuoyanlib。无需随后再往同一目录套一层库，也无需对该源码副本执行 `pip install`。若本机来源位置不同，先检查副本中的 `setup.py` 并修改其来源路径；不要修改公共模板源文件。

## 安装到已有项目

先定位 `modMain.py`，它所在的目录才是安装目标。例如：

```text
CloudFlight/
├── setup.py
├── cleaner.py
├── assets/
└── cloud_flight/
    ├── bp/
    │   ├── manifest.json
    │   └── cloudflight_scripts/
    │       ├── modMain.py
    │       ├── main_client.py
    │       ├── main_server.py
    │       ├── common/
    │       ├── modules/
    │       ├── ui/
    │       └── nuoyanlib/
    └── rp/
        ├── manifest.json
        └── ui/_ui_defs.json
```

只缺少库时，将来源 `src/nuoyanlib` 的整份目录复制到脚本根目录下，保留 `__init__.py`、`client/`、`server/`、`common/`、`core/`、`.pyi` 和库自带的 `LICENSE`，排除 Python 缓存。若目标中已有库，先比较版本、来源差异和本地修改；更新库属于替换依赖，不能靠重复运行项目初始化完成。
