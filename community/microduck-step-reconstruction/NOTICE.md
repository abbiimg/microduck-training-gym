# 来源、署名与修改 / Attribution and modifications

## 原始模型 / Original geometry

原始机器人设计和 STL 几何：**Pollen Robotics，Microduck**。
Original robot design and STL geometry: **Pollen Robotics, Microduck**.

- 上游 / Upstream: https://github.com/pollen-robotics/microduck_rl
- 固定输入版本 / Input revision: `29e887ecfbf5d37144759e5a9f8a176dfb83d547`
- 模型目录 / Model tree: https://github.com/pollen-robotics/microduck_rl/tree/29e887ecfbf5d37144759e5a9f8a176dfb83d547/src/mjlab_microduck/robot/microduck
- 项目主页 / Project home: https://github.com/pollen-robotics/microduck

上游 README 将代码标为 Apache-2.0，将 **3D model files** 单独标为 **Creative Commons BY-SA-NC**。不能把代码的 Apache-2.0 许可直接当作模型许可。本发布使用规范名称 **CC BY-NC-SA 4.0**，与参考社区项目采用的版本一致；保留上游署名和非商业、相同方式共享要求。

The upstream README labels the code Apache-2.0 and separately labels the **3D model files** **Creative Commons BY-SA-NC**. The code licence must not be substituted for the model licence. This release uses the canonical **CC BY-NC-SA 4.0** designation, consistent with the reference community project's version, while retaining upstream attribution and the non-commercial/share-alike requirements.

## 社区参考 / Community reference

- 项目 / Project: https://github.com/fanhao375/microduck-replica
- 参考版本 / Reference revision: `0a50a5a5b147dc2f897236bc167c8d4d455df8b4`

感谢社区整理装配、分类与来源资料。本发布没有使用社区实物照片；新的 CAD 三视图直接从本发布 STEP 计算，前后对比图由本次逆向工作生成。

Thanks to the community for its assembly, classification and provenance references. No community build photographs are included. New CAD sheets are computed from this release's STEP files; comparison images were generated during this reconstruction work.

## 本发布所做修改 / Changes in this release

本仓库的 STEP 逆向修复、校核、图册和整理发布：**tianjin66 及本仓库贡献者**。这一署名不取代 Pollen Robotics 的原始模型署名。转载时按许可证保留提供的署名、来源及修改说明；可参考[转载署名示例](REUSE_POLICY.md)。

STEP reconstruction, repairs, validation, CAD sheets and publication in this repository: **tianjin66 and this repository's contributors**. This credit does not replace attribution to Pollen Robotics for the original geometry. Retain supplied attribution, sources and change notices as required by the licence; see the [attribution example](REUSE_POLICY.md).

1. 上游米尺度 STL 在逆向输入阶段换算为毫米，并采用可读文件名。此处 01_STL_original 保存该输入版本，几何不再修改。
2. 用 AI 辅助自动化方法逆向成 STEP，经过几何识别、局部重建、曲面合并与边界修复；保留采样与编辑校核记录。
3. 整理双语说明、模型映射和最终 CAD 三视图。

1. Upstream metre-scale STL coordinates were converted to millimetres and assigned readable names before reconstruction. 01_STL_original preserves that input snapshot without further geometry edits.
2. AI-assisted automation reconstructed STEP solids with geometry recognition, local rebuilding, surface merging and boundary repair. Sampled validation and editing results are included.
3. This release adds bilingual documentation, a model manifest and final CAD view sheets.

发布日期 / Release date: **2026-09-09**. STEP geometry snapshot: **2026-09-08**.

**非商业用途；署名；相同方式共享。 / Non-commercial use; attribution; share alike.**
完整许可 / Full licence: [LICENSE](LICENSE).
本项目不声称拥有原始模型的独占权利，也不代表原作者背书。
This project claims no exclusive rights to the original geometry and implies no endorsement by its original authors.
