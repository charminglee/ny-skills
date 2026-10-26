---
name: cobblemon-pokemon-modeling
description: 使用 Blockbench MCP 创建、修改和审查 Cobblemon 风格的宝可梦模型、像素材质、行走与待机动画，并维护 resolver、材质图层和动画接线。适用于 Cobblemon 实体资产工作；不用于照搬现有受保护宝可梦资产、普通方块模型或游戏业务代码。
---

# Cobblemon Pokemon Modeling

以 Blockbench MCP（常见服务名 `bbmcp` 或 `blockbench`）作为模型编辑与视觉验收的主执行环境。离线文件和脚本用于审计、比较与交付复核，不能替代 Blockbench 现场检查。

## 开始任务

1. 发现当前可用的 Blockbench MCP 工具并读取其 schema；不要假设历史工具名或参数不变。
2. 读取当前 Blockbench 项目、格式、贴图、骨骼、动画、可见状态和未保存编辑。没有连接时，只能分析磁盘资产或给出方案，不能声称已在 Blockbench 中完成修改。
3. 明确目标是新建、局部修改、风格复刻、接线还是审查，并区分用户授权修改与必须保持不变的内容。
   同时确认运行目标是 Cobblemon Java 还是 Minecraft Bedrock；二者共享 geometry 格式不代表材质、剔除、缩放和动画接线相同。明确改为 Bedrock 时，采用可用的 `bbmcp-bedrock-modeling` 技能处理目标格式与验收，本技能保留美术和动作经验，不自动生成 resolver。
4. 实际查看参考图、模型关键视角和贴图；不要仅凭文件名或单一截图推断结构。
5. 修改前保存可恢复副本或 MCP 检查点；修改后通过 MCP 重读状态、预览关键角度并导出复核。
   用户已手动调整时，以重新读取的现场为后续基线，不从旧脚本、版本文件或预览恢复已删除部件。用户说“不用改”时保持只读；“整理进 Skill”仅授权更新经验文档，不授权重新导出或覆盖模型。

## 按需读取

- 创建或修改几何、骨骼、UV 时，读 [references/model-conventions.md](references/model-conventions.md)。
- 制作小型精灵、调整头身比例、简化口鼻嘴线、降低单面像素密度或迁移狐狸材质流程时，另读 [references/small-creature-budget.md](references/small-creature-budget.md)：区分几何预算、面像素预算与图集大小，包含迪莫与独角精灵的案例及验证边界。
- 从三视图重建、修复脸型/连接/闪烁、按人物对照调整大小时，另读 [references/reference-reconstruction-and-scale.md](references/reference-reconstruction-and-scale.md)。
- 绘制普通、异色、发光、半透明或动画贴图时，读 [references/texture-conventions.md](references/texture-conventions.md)。
- 从材质样品制作全身贴图、处理色块杂乱/明暗不连贯，或研究原模组整体着色时，另读 [references/whole-form-texture-shading.md](references/whole-form-texture-shading.md)：已有 320 物种重分析与 24 只 UV 细审，落实初贴后的整体结构重绘。
- 较大体型、长毛/大尾巴材质，或整体重绘后显得平板时，另读 [references/large-creature-materials.md](references/large-creature-materials.md)：40 只定向复查与 16 只材料部位 UV 精查，补足大明暗和小细节之间的毛束/羽列等结构；Plumeleaf v9 未获用户认可，不作成功模板。
- 制作眼睛、修复眼形/神态/视线、设计眨眼或做眼部专项研究时，另读 [references/eyes-and-expression.md](references/eyes-and-expression.md)：包含 24 只原模组近景证据、承载结构、像素职责、跨面眼与眼睑覆盖，以及迪莫和独角精灵的反馈。
- 新增形态、resolver、图层或动画接线时，读 [references/resource-wiring.md](references/resource-wiring.md)。
- 需要判断规则的证据强度或版本适用范围时，读 [references/corpus-findings.md](references/corpus-findings.md)。
- 批量蒸馏原模组、选择材质/体型/动作对照，或使用 120 物种深入分析结论时，读 [references/corpus-120-transfer.md](references/corpus-120-transfer.md)；其中区分文件统计、编辑器采样、人工观察与运行时验证。
- 继续扩大语料、审查条件图层/形态动画命名或持物与多子体角色时，另读 [references/corpus-200-extension.md](references/corpus-200-extension.md)：新增 200 个不同物种，累计 320，含避免“基础图缺花瓣”和“串用形态动作”的检查方法。
- 全量蒸馏、跨 resolver 继承、追查程序化动作/poser 或批量制作不同精灵时，另读 [references/full-corpus-transfer.md](references/full-corpus-transfer.md)：763 个几何资源、1,957 张贴图和 4,250 段定义的覆盖边界，以及实际状态名与动画名不同的证据。
- 从参考语料迁移材质、改进步态或验证蒸馏规则时，读 [references/material-motion-validation.md](references/material-motion-validation.md)。
- 制作完整行走、待机及其可播放验收预览时，另读 [references/full-body-animation.md](references/full-body-animation.md)。
- 复制、改编或分发原模组资产前，读 [references/licensing.md](references/licensing.md)。

## 工作原则

- 先保证正常游戏距离下的轮廓和物种识别度，再安排表面细节。用少量实体块表达主形；毛尖、叶片、翼膜等按体积、侧面轮廓和目标材质选择零厚度面或薄实体块。用户明确要求薄立方体时保留该选择，不将其替换为尖刺或交叉平面。
- 小型精灵先定主要块体与实际单面像素预算；迁移成功案例的材质制作方法，不照搬大型角色的分块和密度。迪莫后续直接依据原始三视图，不再默认加入“先生成 MC 风格角色图”的步骤；材质样品与角色造型生图分开处理。
- 按运动依赖建骨骼；眼睛、眼睑、下颚、尾段、翼段和四肢需要独立动作时保留独立骨骼及正确轴心。
- 默认遵循该语料的 Box UV 与整数 UV 起点；几何主体尺寸优先整数，允许用分数 origin、pivot、rotation 和小量 inflate 做轮廓校正。
- 不把统计规律伪装成引擎硬限制。非 2 的幂贴图、分数尺寸、逐面 UV 等方案按实际需求选用，并说明验证环境；未进目标游戏时只报告编辑器/导出验证，不能把预览当成运行时证明。
- 材质丰富度取决于形体明暗、固有花纹和方向性色簇的组织，不靠全身加噪或固定色数达标。先选相似部位的原模组对照，再做局部 A/B；不默认每个新角色都用 256 图集。
- 材质样品提供色阶和材质语言，不决定每个面的亮暗位置。初贴后按连续形体重绘整体明暗，再检查跨面过渡与正常距离可读性；保留固有花纹，不用统一高度渐变或全模正亮背暗公式取代结构判断。
- 较大表面不能只做色阶重分配和去碎斑：按部位设计毛束、羽列、叶脉或甲板等中等尺度色簇，再放少量细节。保留有效纹理，不把更平、更少色或数值回归通过等同于美术成功。
- 眼睛需单独检查参考符合度：分清瞳孔、眼内色区、上缘与脸部遮挡，不默认尖黑模板或整眼缩放眨眼。眼部反复被否定时先做局部同条件对照；UV/动画数值合格不代表神态已经被用户认可。
- 分开判断绑定姿势、单条动画姿势与 poser 混合后的游戏姿势；按角色选择地面行走、游动或飞行，不把悬浮起伏当通用移动。无声明时长的表达式动画先分析周期，观察窗口不是循环长度。
- 预览缺少部位时先核查 resolver 的条件图层和姿态隐藏；物种名、模型资源名、geometry 内部标识及动画前缀并非总一致。动画数量与实际移动覆盖分别报告，不把替代的 blink/cry/pose 当已验收行走。
- 普通与异色形态尽量共享模型、贴图尺寸和 UV 布局；差异由同布局重绘或 resolver aspect 覆盖表达。
- 发光、半透明和逐帧效果通过专用贴图图层与 resolver 接线表达；不要把所有效果烘进普通底图。
- Cobblemon 使用 Bedrock Geometry 数据，但运行在自己的 Java 渲染与 resolver 系统中。不要未经验证照搬基岩版材质、剔除或实体定义假设。

## Blockbench MCP 执行顺序

1. 读取项目状态并记录模型格式、纹理分辨率、骨骼层级、UUID/名称、动画和选择状态。
2. 在 MCP 中建立组件清单：主轮廓、连接关系、材质、可动部件、实体块或平面方案。
3. 按“根骨骼 → body/torso → head/eyes/jaw → limbs/tail/wings → 装饰平面”的依赖顺序编辑；同一项目的写操作不要并发。
4. 在 MCP 中检查正面、侧面、背面和斜角；测试站立、行走、睡眠、战斗或任务要求的关键姿态。
5. 检查 UV 与 PNG 实际尺寸、纹理方向、镜像、透明边缘和图层语义。全身材质初贴后做整体结构重绘；保持同几何、同 UV 与同镜位，以关闭/开启编辑器光照对照，避免把灯光效果误当作已画进底图的体积。
6. 导出后重读 `.geo.json`、PNG 和 resolver。可运行 `scripts/audit_asset_pair.py` 做只读结构检查，再以 Blockbench 预览和游戏内表现作为最终依据。

## 完成条件

- 轮廓、比例、像素组织和关键姿态符合参考与 Cobblemon 语料风格。
- 骨骼父子关系、轴心、UV、贴图分辨率及 resolver 引用一致。
- 普通/异色/地区或性别形态没有非预期串线；发光、半透明和动画图层语义正确。
- 未覆盖用户未授权的现场编辑；磁盘导出与 MCP 当前项目一致。
- 已清理不再需要的临时脚本与重复测试资产；保留可恢复快照、可编辑样板、必要验收报告和证据，不把交付物当临时垃圾删除。
