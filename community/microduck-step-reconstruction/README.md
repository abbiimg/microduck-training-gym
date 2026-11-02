# Microduck STEP 3D 模型（AI 逆向 STL）

**Microduck STEP 3D Models — AI-assisted STL Reverse Engineering**

> **不得商用｜转载保留署名及许可｜修改后分享须注明修改并沿用相同许可｜不得冒充原创。** 合规非商业 Fork 与转载是允许的。详见[使用与转载说明](REUSE_POLICY.md)。
>
> **Non-commercial only. Retain attribution and licence notices; mark shared modifications and share alike. Do not misrepresent authorship.** Compliant non-commercial forks and redistribution are permitted. See the [reuse policy](REUSE_POLICY.md).

[中文](#中文说明) · [English](#english) · [改进参数 / Technical notes](03_REVERSE_ENGINEERING.md) · [全部三视图 / CAD views](docs/CAD_VIEWS.md)

![30 件最终修复 STEP / 30 final repaired STEP parts](docs/previews/parts_overview.png)

![最终 STEP 三视图：镜头座 / Final STEP CAD views: lens holder](docs/previews/m12_lens_holder_cad_views.png)

## 中文说明

这是一套根据 **Pollen Robotics Microduck 的公开 STL 网格**，使用 AI 辅助编写自动化方法、识别几何并多轮修复得到的 STEP 模型。为主要以 STL 形式提供的模型资料补充 STEP 版本，方便大家学习、研究和进行二次修改。

**这是第三方逆向整理成果，不是官方原始 CAD，也不是 SolidWorks 原生特征树。**

### 下载与目录

点击 GitHub 的 **Code → Download ZIP** 下载全部内容，也可以进入对应目录下载单件。**下载时请点一下右上角的小星星 ⭐，感谢支持！** Star 是鼓励，不是下载门槛。

| 内容 | 位置 | 说明 |
|---|---|---|
| 最初用于逆向的 STL | [01_STL_original](01_STL_original/) | 30 种单件，毫米坐标；保留此次逆向输入的原始字节 |
| 最终修复 STEP | [02_STEP_final](02_STEP_final/) | 30 种单一有效实体，与 STL 一一对应 |
| 逆向与改进参数 | [03_REVERSE_ENGINEERING.md](03_REVERSE_ENGINEERING.md) | 逐件对照、几何参数、修复方法与已知局限，中英文 |
| CAD 三视图 | [docs/CAD_VIEWS.md](docs/CAD_VIEWS.md) | 每件的俯视、主视、右视及轴测图；PNG 和 SVG |
| 校核数据 | [docs/model_manifest.json](docs/model_manifest.json) | 单位、数量、SHA-256、偏差、体积和切削测试记录 |

**单位均为 mm。** 上游仿真资产原以米表示；逆向输入阶段已乘以 1000 转为毫米。本目录中的 STL 和 STEP 导入后不要再次放大 1000 倍。文件名 `x2` 表示参考装配数量为 2，文件里仍是一个零件。共 **30 种单件、参考装配数量 36 件**，不含电机、轴承、电子件或完整约束装配体。

### 本次改善

| 零件 | 之前的逆向 STEP 面数 → 最终面数 | 之前的 STEP 大小 → 最终大小 |
|---|---:|---:|
| M12 镜头座 | 491 → **53** | 7.73 MB → **0.21 MB** |
| 髋偏航转横滚件 | 269 → **66** | 4.11 MB → **0.41 MB** |
| 下颚 | 523 → **131** | 7.61 MB → **3.42 MB** |
| 左 / 右脚底 | 各 95 → **81** | 各 9.31 MB → **约 1.34 MB** |
| 头部下壳 | 1501 → **1239** | 9.99 MB → **9.83 MB** |

这不是把每个 STL 三角片直接封装成 STEP。工作包含平面合并、圆柱与圆锥等解析几何恢复、局部参数化重建、样条曲面重拟合、边界曲线恢复和实体修复。不同零件的简化程度不同。

最终 30 件均通过记录中的实体有效性和局部布尔切削检查；相对输入 STL 的**最大已测采样偏差约 0.0226 mm**。这里的面数比较是“较早逆向 STEP 与最终 STEP”之间的比较，不能把 STL 三角片数与 CAD 面数直接混为一谈。完整数字见[技术说明](03_REVERSE_ENGINEERING.md)。

### 碎面和使用说明

**有一些 STEP 仍存在大量碎面。** 在本次自动化逆向中，复杂自由曲面、圆角与相交边界很难完全避免分面。我已经尽可能做了多轮优化，在保留形状精度的前提下减少面数和曲面复杂度，谢谢理解，也欢迎大家继续改进。

目前髋部连接件、左右躯干壳和头部下壳仍各有上千面；15 件 STEP 仍超过 1000 KB。文件变小不等于恢复了原始设计意图，也不能保证每个局部都适合直接改尺寸。

将 STEP 作为实体导入 CAD 后，可尝试切除、增加结构、移动面或重新建立特征。原始草图、尺寸约束、装配约束和设计特征树没有恢复。采样偏差不是连续曲面的严格误差上限，也不是打印或加工精度保证；装配配合、材料、收缩与公差请结合实物检查。

### 许可与致谢

**不得用于商业用途。** 本发布的模型、衍生 STEP、图片与文档按 **[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)** 非商业共享：请署名、注明修改，并以相同许可证分享衍生作品。完整条款见 [LICENSE](LICENSE)，来源与版本见 [NOTICE.md](NOTICE.md)。

感谢 [Pollen Robotics](https://github.com/pollen-robotics/microduck_rl) 的 Microduck 原始模型，以及 [microduck-replica 社区资料](https://github.com/fanhao375/microduck-replica) 的整理工作。这是独立社区项目，不代表原作者认可或提供支持。

---

## English

This repository provides **AI-assisted reverse-engineered STEP models based on the publicly available Pollen Robotics Microduck STL meshes**. AI was used to help develop automated geometry reconstruction and repair methods. The goal is to supplement the STL-based resources with STEP solids that are easier to study, adapt and modify.

**These are independent reconstructions, not official source CAD or recovered SolidWorks feature trees.**

### Download and contents

Choose **Code → Download ZIP** on GitHub, or open a model directory to download an individual part. **If you download or find this useful, please leave a star ⭐. Thank you!** Starring is appreciated, not required for access.

- [01_STL_original](01_STL_original/): the 30 original millimetre STL inputs used for this reverse-engineering work, preserved byte for byte.
- [02_STEP_final](02_STEP_final/): the corresponding 30 repaired STEP solids.
- [03_REVERSE_ENGINEERING.md](03_REVERSE_ENGINEERING.md): bilingual reconstruction notes, measured parameters, before/after comparisons and limitations.
- [docs/CAD_VIEWS.md](docs/CAD_VIEWS.md): top, front, right and isometric views of every final STEP, in PNG and SVG.
- [docs/model_manifest.json](docs/model_manifest.json): model mapping, quantities, SHA-256 hashes and numerical audit results.

**All delivered coordinates are in millimetres.** The upstream metre-scale simulation assets were scaled by 1000 before reverse engineering. Do not apply that conversion again. An `x2` filename suffix means two instances are needed in the reference assembly; each file still contains one part. The set covers **30 distinct parts / 36 reference instances**, not the motors, bearings, electronics or a fully constrained assembly.

### Improvements and validation

This work includes plane merging, recovery of analytic cylinders and cones, local parametric reconstruction, adaptive spline fitting, boundary-curve reconstruction and solid repair. It is not a one-CAD-face-per-STL-triangle wrapper.

Compared with an earlier reverse-engineered STEP set, the lens holder went from **491 to 53 faces**, the yaw-to-roll connector from **269 to 66**, the jaw from **523 to 131**, and each sole from **95 to 81**. These are CAD-to-CAD face counts; STL triangle counts are a different measure.

All 30 delivered files passed the recorded solid-validity and local Boolean-cut checks. The largest observed deviation across the recorded surface and additional random samples was **approximately 0.0226 mm** against the input STL. See the [technical notes](03_REVERSE_ENGINEERING.md) for exact measurements and their limits.

### Remaining fragmented faces

**Some STEP models still contain many fragmented faces.** Complex freeform surfaces, fillets and intersecting boundaries were difficult to reconstruct without fragmentation in this automated workflow. I have made repeated efforts to reduce the complexity while preserving the measured shape. Thank you for understanding; further community improvements are welcome.

The hip connector, both trunk shells and the lower head shell still exceed 1000 faces each, and 15 STEP files are still larger than 1000 KB. Smaller file size does not mean the original design intent has been recovered.

The STEP solids can be used for direct editing, Boolean operations and rebuilding features, subject to your CAD tool and the local geometry. Original sketches, dimensional constraints, assembly constraints and feature histories are not included. Sampled deviations are not rigorous continuous-surface error bounds or manufacturing tolerances. Check physical fit, materials, shrinkage and required tolerances before relying on modified parts.

### Non-commercial sharing and attribution

**No commercial use.** The models, derivative STEP files, images and documentation in this release are shared under **[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)**: provide attribution, indicate changes, and distribute adaptations under the same licence. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).

Thanks to [Pollen Robotics](https://github.com/pollen-robotics/microduck_rl) for the original Microduck geometry and the [microduck-replica community](https://github.com/fanhao375/microduck-replica) for its reference material. This independent project is not endorsed or supported by the original authors.
