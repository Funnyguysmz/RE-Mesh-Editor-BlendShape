# RE Mesh Editor BlendShape 0.70.6 — RE4R Face Integration re4r.2

基于 Dimcirui 上游 0.70.6 的公开派生版，由 funnyguyz 整合 RE4 九接收口和保留三渲二法线功能。2026-10-14 合入上游表面转动、Static Normals、locked keys 烘焙及三角化法线修复。**不是 Dimcirui 官方 0.70.6 发布。** 原作者 NSA Cloud、Ridog8、Dimcirui 的署名、原 LICENSE 和未涉及的功能保留。

## 下载

[派生版预发布 v0.70.6-re4r.2](https://github.com/Funnyguysmz/RE-Mesh-Editor-BlendShape/releases/tag/v0.70.6-re4r.2)。下载插件 ZIP，不要把 GitHub Source code ZIP 当作安装包。

## 安装与导出

在 Blender 插件设置里停用旧的 RE Mesh Editor，安装这个 ZIP 后启用 `RE-Mesh-Editor-BlendShape (RE4R Face Integration)`，避免同时启用两份注册相同 operator 的插件。原安装和原 ZIP 可留作回退。派生版本的安装包对应此仓库 tag。上游内置更新器仍指向 Dimcirui；使用本派生版时保持自动更新关闭，从本仓库 Release 手动更新。

导出 RE4 `.mesh.221108797` 时，`Export Shapekeys?` 选择非 `No`，然后按需要设置两个新增开关：

| 开关 | 用途 |
|---|---|
| `Add RE4 Mouth Receivers (9)` | 在自定义形态键前补 9 个指定的原生修正信号接收通道。无需手建零位移 Shape Keys。非零形变使用同名接收口会被拒绝。 |
| `Keep RE4 Toon Normals (No Fins)` | 写入 packed 位移和自定义法线，省去 normalRecalc 和 fins。每个键使用该顶点导出的基础法线方向。 |

两项默认关闭，以保留上游 0.70.6 的 RE4 默认行为。RE4 的法线布局由新增专用开关决定；通用 `MODE1` / `KEEPNORMALS` / 新默认 `KEEPNORMALS_SURFACE` 选项在 RE4 只负责启用形态键导出，旧配置和调用值继续支持。选择 `No` 时两个开关均不生效。其他游戏不采用这些 RE4 开关。批量导出拥有相同选项并按集合保存。

如果集合已有自定义 JSON 属性 `RE4_native_taps`，继续支持显式名单；勾选 mouth9 时以内置九项覆盖该次导出的名单。接收口加在 LOD0 第一个有有效形态键的 viscon group；无有效形变时拒绝单独生成接收口。高 LOD 沿用原版的兼容布局限制。

## 上游 0.70.6 法线模式与 RE4 的区别

| 功能 | 合并后的作用 |
|---|---|
| `Keep Normals (surface turn)`，新增通用默认 | 支持逐键法线的其他游戏沿几何表面转动 authored normals。RE4 的普通导出键仍由专用开关选择布局，不会改写为逐键表面转动法线。 |
| `Keep Normals (as in Blender)` | 保留旧 `KEEPNORMALS` 调用与配置值。在 RE4 中和另外两个非 `No` 选项一样启用形态键。 |
| Shape Keys 面板逐键 `Static Normals`，含 All/None | 支持逐键法线的游戏可保持指定导出键法线。RE4 普通导出键的标记不改变每键最终基础法线合同。 |
| locked keys 烘焙 | 启用形态键导出时，未标 Static 的 locked key 沿真实表面转动基础 authored normals；标 Static 的 locked key 只烘焙位置。它会改变 RE4 最终基础法线，随后由专用开关重复到所有键。 |
| 四边形/n-gon 三角化保护 | RE4 与共用导出路径受益，保留原 authored corner normals，避免三角化引起额外摆动。 |
| `Keep RE4 Toon Normals (No Fins)` | 仍为默认关闭的独立开关。开启后 packed 11/10/11 位移 + int8 法线，`unknFlag=0`、`normalRecalcOffset=0`，每键重复最终基础自定义法线。 |

`No` 仍忽略两个 RE4 开关并排除形态键记录；这是静态网格导出路径，当前 Blender 键值会烘焙进网格，不能把它理解为同一套 locked/Static 形态键导出规则。此次不新增 RE4 逐表情不同法线模式，也不改变九信号、名称/hash 或运行时模型 profile 合同。

## 做模型时仍需完成的准备

1. 保留可用的 MMD/VRC Shape Keys，模型大小、位置、材质、骨架按 RE4 替换规范适配。
2. 采用这条路线的面部网格统一绑定 `Head`，不再为眼皮、嘴角刷表情骨权重。保留原生表情骨和角色需要的骨架，脚本仍需读取游戏的原生运动信号。
3. 三渲二脸部先设置圆柱化/其他自定义法线。开关只保留已有方向，不会自动把普通法线改成卡通法线，也不会删除模型里已有的 fins。
4. 配好该模型的 ShapeKey System profile，将游戏语义映射到实际导出的形态键名称/hash。导出器不自动推断任意 MMD/VRC 嘴型含义，也不生成新模型的完整映射表。

这条路线依旧需要运行时映射：游戏面部骨运动和九个原生通道权重 → 表情语义 → 模型 Shape Keys。九个接收口的位置增量为零，法线模式下其法线记录与基础顶点一致；它们用于接收权重信号，不复制里昂的原生脸部形变。

## 九信号合同

九个名字按以下顺序前置，每项都以 `Face__geo__p000_cbs.crct_` 为前缀：

1. `jaw_openExtreme`
2. `mouth_purse_L_U`
3. `mouth_purse_L_D`
4. `mouth_purse_R_U`
5. `mouth_purse_R_D`
6. `mouth_funnel_L_U`
7. `mouth_funnel_L_D`
8. `mouth_funnel_R_U`
9. `mouth_funnel_R_D`

它们是零位移权重接收口，不能替代模型自己的嘴型键。需 [ShapeKey System](https://github.com/Funnyguysmz/RE4R-ShapeKey-System) 的 mouth9 适配及该模型的 profile；Shinnano、Xiaoyu 配置不能直接作为任意模型通用配置。面捕来源可用 [RhyLive Face](https://github.com/Funnyguysmz/RE4R-RhyLive-Face)，GUI 由 [Studio](https://github.com/Funnyguysmz/RE4R-ShapeKey-Studio) 维护。导出器不修改这些运行时。

## 验证范围

当前合并版的公开可重现检查：

- 合成键 + 九个零位移接收口，四种开关组合的基础几何/UV/法线/索引一致；no-recalc 每一条键和接收口法线记录与最终基础法线字节一致。
- 新默认模式、两开关关闭的实际 RE4 导出与上游 **0.70.6** 字节相同。
- packed 再导入再导出、批量参数保存、No 模式、同名非零接收口拒绝通过；旧 MODE1/KEEPNORMALS 与新默认值保持调用兼容。
- 上游 20 项公开合成检查通过，包括 Static 操作、重命名、All/None、locked 烘焙和表面转动数学对照。
- 24 项新增 RE4 法线回归通过，包括两个真实形变键 + 九接收口、RE4 各选择器一致性、locked Static 影响、四边形/五边形三角化及最终法线字节。
- 所有测试阻止执行随包 native 库；插件包与当前 tag 源码逐条字节核对。见 `reports/synthetic_blender.json`、`reports/upstream_0706_normals.json`、`reports/package_check.json`、`reports/upstream_provenance.json`。

**历史证据单独保留：** re4r.1 曾完成实际模型 85/94 通道四组合、基础资源 Toolkit 检查和原生 chd000 四 LOD 离线核对，摘要在 `reports/re4r.1/` 与 `reports/private_validation_summary.json`。这不是本合并版的新实测；测试资产未上传。用户认可此前独立 85 通道法线实验的反馈仅作为历史。本次 re4r.2 以及 94 通道集成组合仍待新的游戏反馈，不宣称任意模型或其他游戏运行验证完成。

## 法线能力边界

本版本保存同一顶点原有的法线方向，适用于保持稳定的三渲二光照；不生成每个表情不同的几何法线。导入兼容 RE4 的 float16/recalc 与 packed/no-recalc 位移布局。原生样本里的独立逐表情法线没有转成 Blender 的逐形态键法线编辑数据；若需保留每个表情不同的法线，需另做流程。

packed 格式会有量化误差；历史 re4r.1 小玉导出中各形态键与 float16 对照的最大差异低于 0.1 mm；当前合成导出量化误差另有公开回归。保持法线不会取消引擎的阴影、遮挡、材质高光和场景灯光。

## 许可与来源

本仓库是 [Dimcirui/RE-Mesh-Editor-BlendShape](https://github.com/Dimcirui/RE-Mesh-Editor-BlendShape) 的 Fork，当前上游基线 `c030c89f95e6f20c697c402d21b7bae7ec8a52e9`（tag `v0.70.6`）；历史 re4r.1 基于 0.70.5，保留原 tag 和附件。保留 NSA Cloud、Ridog8、Dimcirui 的历史和署名。funnyguyz 于 2026-10-13 增加 RE4 功能，2026-10-14 合入上游 0.70.6 并扩充公开回归；上游原说明保留为 `README_UPSTREAM.md`。插件继续使用原 `LICENSE.GPL`（GPLv3）；随包第三方组件按原声明许可，详见 `THIRD_PARTY_NOTICES.md`。这是派生版，不是作者官方 0.70.6。

## 重建和测试

需要 Python 3 和 Blender 4.3.2。`python build_editor.py` 使用公开文件清单生成插件 ZIP，不依赖本机绝对路径。`python prepare_delivery.py` 检查 ZIP 中每个文件和源码的字节与哈希。

合成测试不需要任何游戏/模型资源：

```sh
# 从基线 tag/提交准备测试对照（在仓库根执行，先建立目录）
python -c "from pathlib import Path; Path('output/re4r.2').mkdir(parents=True, exist_ok=True)"
git archive c030c89f95e6f20c697c402d21b7bae7ec8a52e9 --output=output/re4r.2/upstream-baseline.zip
python -m zipfile -e output/re4r.2/upstream-baseline.zip output/re4r.2/upstream
blender --background --factory-startup --python-exit-code 1 --python verify_blender.py -- --upstream
blender --background --factory-startup --python-exit-code 1 --python verify_blender.py
blender --background --factory-startup --python-exit-code 1 --python tests/test_re4r_0706_normals.py
python build_editor.py
python prepare_delivery.py
```

生成测试网格保留在被忽略的 `output/`，不纳入安装包。`reports/synthetic_blender.json` 记录公开可重现结果。真实模型和原生样本仅保留不含资产或本机路径的历史验证摘要，不能据此宣称任意模型或其他游戏已验证。

新包和清单在 `output/re4r.2/`，旧 `output/` 包保持不变。`0.70.6-upstream-to-re4r.2.patch` 是当前插件差异；旧 `0.70.5-to-0.70.6.patch` 是历史 re4r.1 差异。
