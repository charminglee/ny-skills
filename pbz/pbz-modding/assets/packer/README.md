# PBZ 本地打包器

固定部署在 `E:/PbzMod/Packer`。运行无需联网、Git、Cargo 或重新编译。直接使用系统 PowerShell 7（pwsh），不复制其运行时；其他依赖、映射和助手 DLL 已在部署时固定并记录 SHA-256。

```powershell
pwsh -NoProfile -File E:/PbzMod/Packer/Pack.ps1 -CheckEnvironment
pwsh -NoProfile -File E:/PbzMod/Packer/Pack.ps1 `
    -Manifest E:/PbzMod/.tmp/任务名/patched/repack-manifest.json `
    -Name zzz_ModName_P
```

`Name` 只接受英文、数字、下划线和连字符。默认成品目录为 `Backups/<Name>`，可用 `-OutputDirectory` 指定新的目录。已存在的目录不覆盖。

只输出同名 `.pak/.utoc/.ucas` 三件套。输入清单必须列出全部包与数据块，`raw-chunks/<id>.bin` 与清单相邻，长度和 SHA-256 必须正确。先冻结输入，再封装、执行 retoc info/verify，最后在只有新包与游戏 global 数据的独立挂载目录中回读全部数据块。所有日志、输入快照和验证报告保存在项目 `.tmp/packer-*`。

原版提取也复用已部署环境：

```powershell
pwsh -NoProfile -File E:/PbzMod/Packer/Invoke-Cue.ps1 `
    -Action extract -AssetsJson E:/PbzMod/.tmp/任务名/assets.json `
    -WorkDir E:/PbzMod/.tmp/任务名/original
```

`Invoke-Cue.ps1` 同时支持 `inspect`，或 `inventory -AssetRoot ProjectPBZ/...`。它加载预编译助手，不执行 Add-Type。系统 pwsh 路径、游戏目录、AES 配置在 `config.json`，工具和映射的校验清单在 `deployment.json`。缺失或不匹配即报错，日常流程不自动重建或下载。

封装器消费原生 Cooked/Zen 数据，不能把 Blend、UEFormat、PNG 直接当作 Cooked 数据。模型差异、各 LOD 删除映射、纹理原生格式写回及相应语义校验须先完成，之后把正确数据块交给此入口。没有安装动作；静态回读通过不代表游戏内测试完成。
