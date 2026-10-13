# RE Mesh Editor BlendShape 0.70.6 — RE4R Face Integration

基于用户提供的 Dimcirui `RE-Mesh-Editor-BlendShape-0.70.5.zip` 制作的本地派生版，由 funnyguyz 整合 RE4 九接收口和保留三渲二法线功能。**不是 Dimcirui 官方 0.70.6 发布。** 原作者 NSA Cloud、Ridog8、Dimcirui 的署名、原 LICENSE 和未涉及的功能保留。

## 下载

[派生版预发布 v0.70.6-re4r.1](https://github.com/Funnyguysmz/RE-Mesh-Editor-BlendShape/releases/tag/v0.70.6-re4r.1)。下载插件 ZIP，不要把 GitHub Source code ZIP 当作安装包。

## 安装与导出

在 Blender 插件设置里停用旧的 RE Mesh Editor，安装这个 ZIP 后启用 `RE-Mesh-Editor-BlendShape (RE4R Face Integration)`，避免同时启用两份注册相同 operator 的插件。原安装和原 ZIP 可留作回退。派生版本的安装包对应此仓库 tag。上游内置更新器仍指向 Dimcirui；使用本派生版时保持自动更新关闭，从本仓库 Release 手动更新。

导出 RE4 `.mesh.221108797` 时，`Export Shapekeys?` 选择非 `No`，然后按需要设置两个新增开关：

| 开关 | 用途 |
|---|---|
| `Add RE4 Mouth Receivers (9)` | 在自定义形态键前补 9 个指定的原生修正信号接收通道。无需手建零位移 Shape Keys。非零形变使用同名接收口会被拒绝。 |
| `Keep RE4 Toon Normals (No Fins)` | 写入 packed 位移和自定义法线，省去 normalRecalc 和 fins。每个键使用该顶点导出的基础法线方向。 |

两项默认关闭，以保留 0.70.5 的 RE4 默认行为。RE4 的法线布局由新增专用开关决定；通用 `MODE1` / `KEEPNORMALS` 选项在 RE4 只负责启用形态键导出。选择 `No` 时两个开关均不生效。其他游戏不采用这些 RE4 开关。批量导出拥有相同选项并按集合保存。

如果集合已有自定义 JSON 属性 `RE4_native_taps`，继续支持显式名单；勾选 mouth9 时以内置九项覆盖该次导出的名单。接收口加在 LOD0 第一个有有效形态键的 viscon group；无有效形变时拒绝单独生成接收口。高 LOD 沿用原版的兼容布局限制。

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

- 0.70.5 原版与 0.70.6 两开关关闭的实际导出 MESH **逐字节相同**。
- 四种开关组合导出、回读通过：85/94 通道，所有基础几何/UV/权重/法线/索引相同，9 个接收口位移为零，法线 payload 与最终基础法线字节一致。
- 新法线布局导回 Blender 并再导出通过；批量导出加载并保存两项选项，结果与单次导出一致；`No` 模式正确排除形态键。
- RE4 原生 chd000 no-recalc 样本四个 LOD 位移解码有限，非零位移与独立样本解析交叉核对。
- 实际 94 通道名称/hash 与维护对话交付的 System mouth9 profile 匹配。
- MESH/MDF/贴图配对的 Toolkit 检查与最终 ZIP 检查记录摘要见 `reports/private_validation_summary.json`。Toolkit 检查基础资源；法线 payload 另外通过新解析器及直接字节检查。
- 随原版复制的 DLL 仅打包，测试用审计钩子阻止加载，没有运行。

**游戏证据分开记录：** 用户已反馈此前独立 85 通道自定义法线实验“没问题”。本次集成导出器的 94 通道＋9 接收口＋法线组合已通过离线验证，尚未收到这一新包的游戏反馈。任意模型、不同表情法线的混合、其他游戏新增回归均未据此宣称验证完成。

## 法线能力边界

本版本保存同一顶点原有的法线方向，适用于保持稳定的三渲二光照；不生成每个表情不同的几何法线。导入兼容 RE4 的 float16/recalc 与 packed/no-recalc 位移布局。原生样本里的独立逐表情法线没有转成 Blender 的逐形态键法线编辑数据；若需保留每个表情不同的法线，需另做流程。

packed 格式会有量化误差；本次实际小玉导出中各形态键与 float16 对照的最大差异低于 0.1 mm。保持法线不会取消引擎的阴影、遮挡、材质高光和场景灯光。

## 许可与来源

本仓库是 [Dimcirui/RE-Mesh-Editor-BlendShape](https://github.com/Dimcirui/RE-Mesh-Editor-BlendShape) 的 Fork，基线提交 `5c0ac95bcda08a36fe149523c986b89a77725ec6`（0.70.5）。保留 NSA Cloud、Ridog8、Dimcirui 的历史和署名。funnyguyz 于 2026-10-13 增加上述 RE4 功能和公开测试/打包。插件继续使用原 `LICENSE.GPL`（GPLv3）；随包第三方组件按原声明许可，详见 `THIRD_PARTY_NOTICES.md`。这是派生版，不是作者官方 0.70.6。

## 重建和测试

需要 Python 3 和 Blender 4.3.2。`python build_editor.py` 使用公开文件清单生成插件 ZIP，不依赖本机绝对路径。`python prepare_delivery.py` 检查 ZIP 中每个文件和源码的字节与哈希。

合成测试不需要任何游戏/模型资源：

```sh
# 从基线 tag/提交准备测试对照（在仓库根执行）
git archive 5c0ac95bcda08a36fe149523c986b89a77725ec6 --output=upstream-baseline.zip
python -m zipfile -e upstream-baseline.zip output/upstream
blender --background --factory-startup --python-exit-code 1 --python verify_blender.py -- --upstream
blender --background --factory-startup --python-exit-code 1 --python verify_blender.py
python build_editor.py
python prepare_delivery.py
```

生成测试网格保留在被忽略的 `output/`，不纳入安装包。`reports/synthetic_blender.json` 记录公开可重现结果。真实模型和原生样本仅保留不含资产或本机路径的历史验证摘要，不能据此宣称任意模型或其他游戏已验证。
