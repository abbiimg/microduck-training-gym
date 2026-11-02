# 原始 STL → 最终 STEP：逆向改进参数 / Reverse-engineering notes

[返回首页 / Home](README.md) · [全部三视图 / All CAD views](docs/CAD_VIEWS.md)

## 数据范围 / Scope

本发布保留 30 件实际用于逆向的毫米 STL，逐字节复制最终修复 STEP。逆向前的米→毫米换算是唯一针对所提供“原始 STL”版本的前处理；此处“原始”指本次逆向输入，不是上游米尺度文件的逐字节副本。

The 30 millimetre STL inputs and final STEP files are preserved byte for byte. “Original STL” means the input snapshot used here, after the earlier metre-to-millimetre conversion; it does not mean byte-identical upstream metre-scale assets.

最后一轮检查了全部 30 件，进一步改善此前超过 1000 KB 的 19 件；其余 11 件沿用已校核版本。最终 STEP 总量 77,772,474 字节；此前 30 件 STEP 共 145,604,177 字节。这里的前后对比不是 STL 和 STEP 文件大小的对比。

The last pass inspected all 30 parts and further improved the 19 earlier STEP files larger than 1000 KB. The remaining 11 retained their previously audited versions. Total STEP size changed from 145,604,177 to 77,772,474 bytes. This comparison is between two STEP releases, not between STL and STEP.

## 方法与校核参数 / Methods and checks

| 项目 / Item | 参数与含义 / Parameter and meaning |
|---|---|
| 单位 / Units | mm；不改变各零件原有坐标系 / Original per-part coordinate frame retained |
| 几何构建 / Reconstruction | 平面合并、解析曲面识别、局部参数化、样条重拟合、边界及实体修复 / Plane merging, analytic surfaces, local parametric rebuilding, spline fitting, boundary and solid repair |
| 验收采样偏差 / Sampled deviation acceptance | < 0.025 mm；本批实测最大 0.0225577748 mm / Largest observed in this release: 0.0225577748 mm |
| 体积差验收 / Volume difference acceptance | < 0.5% 绝对值 / Absolute difference below 0.5% |
| 校核显示网格 / Audit tessellation | 新版额外校核使用 0.0005 mm 线性偏转 / New additional audits used 0.0005 mm linear deflection |
| 双向表面采样 / Bidirectional sampling | STL 和重建表面的顶点、三角形中心；各方向另加 20,000 个随机样本 / Surface vertices and triangle centres plus 20,000 additional random samples per direction |
| 实体检查 / Solid check | 每文件 1 个有效实体 / One valid solid per file |
| 编辑测试 / Edit test | 局部减去边长 0.4 mm 的方块，检查布尔结果有效 / Subtract a local 0.4 mm cube and check validity |
| 三视图 / CAD sheets | 最终 STEP 直接计算，一般显示网格偏转 0.01 mm；右壳使用精确遮挡线和 0.003 mm 曲线采样；第三角布局 / Final STEP, normally 0.01 mm display deflection; right shell uses exact hidden-line removal with 0.003 mm curve sampling; third-angle layout |

以上偏差是采样结果，不是连续曲面的严格 Hausdorff 上界；图纸仅供展示，不含加工公差。视图使用固定全局轴：主视沿 −Y、俯视沿 +Z、右视沿 +X，不额外旋转零件坐标。

These are sampled deviations, not a proven continuous-surface Hausdorff bound. The sheets are reference views without manufacturing tolerances. Views use the fixed source axes: front from −Y, top from +Z, right from +X.

## 重点几何参数 / Selected reconstructed dimensions

参数由 STL 测量和拟合得到，不是原厂公差或已恢复的草图约束。更详细数值见对应的审计 JSON。

Parameters were measured or fitted from STL; they are not factory tolerances or recovered sketch constraints. Detailed values are included in the per-part audit JSON.

| 零件 / Part | 重建参数 / Rebuilt parameters |
|---|---|
| M12 镜头座 / Lens holder | 外框 16 × 7.8 × 16 mm；内开口 14.2 × 6.8 × 14.2 mm；耳孔 X = ±10 mm、孔径 2 mm；套筒外半径 7.6 mm、内孔半径 5.8 mm；边缘圆角 0.2 mm。/ Outer frame, inner opening, lug centres and Ø2 holes, sleeve radii and R0.2 edges. Part name does not imply a modeled M12 thread. |
| yaw2roll | 底板 23 × 25.8 × 2.5 mm；加强筋厚 1.35 mm；背板厚 3 mm；背部下 / 上圆角 R5 / R2。/ Base plate, ribs, back wall and R5 / R2 back radii. |
| 左右上腿 / Upper legs | 恢复 3° 拔模圆锥壁；每件控制点 80,567 → 6,084，面数 160 → 163。/ Restored 3° drafted cone walls; fewer controls with three additional face boundaries. |
| 躯干底板 / Trunk base | 57 × 36 mm，板厚 1 mm；两孔 Ø19 mm、四孔 Ø2.3 mm；圆角槽 6 × 12 mm、R2；定位柱底径 1.8 mm、高 2 mm、拔模 3°。/ Plate, large and small holes, rounded slot and drafted locating pins. |

## 19 件进一步修复对比 / 19-part repair comparison

“之前”专指较早的逆向 STEP。控制点数是所有样条曲面的控制点之和；面数增加有时用于稳定狭长曲面或恢复合理分界。KB = 1024 字节。

“Before” refers to the earlier reverse-engineered STEP. Control points are summed over spline surfaces. A few additional faces can improve narrow-surface stability or restore meaningful boundaries. KB = 1024 bytes.

| 零件 / Part | CAD 面数 / Faces | 样条控制点 / Control points | STEP KB | 最大采样偏差 / Max sampled mm |
|---|---:|---:|---:|---:|
| bottom_head_shell | 1501 → 1239 | 89,629 → 72,472 | 9756.2 → 9600.6 | 0.016824 |
| face_part | 237 → 178 | 11,637 → 10,692 | 3647.2 → 1256.1 | 0.013041 |
| foot_left | 543 → 473 | 57,025 → 40,255 | 6693.6 → 5696.2 | 0.012816 |
| foot_right | 543 → 473 | 57,025 → 40,255 | 6757.8 → 5718.6 | 0.012513 |
| hip_l | 1190 → 1081 | 65,653 → 54,205 | 8793.3 → 7573.3 | 0.015059 |
| jaw | 523 → 131 | 42,084 → 30,214 | 7435.9 → 3336.6 | 0.013038 |
| jaw_soft | 42 → 46 | 57,530 → 13,800 | 8379.4 → 1550.8 | 0.020311 |
| left_shell | 1648 → 1599 | 89,687 → 62,773 | 9592.5 → 9421.2 | 0.018082 |
| leg | 171 → 158 | 18,470 → 5,266 | 3894.0 → 1253.3 | 0.019968 |
| m12_lens_holder | 491 → 53 | 70,367 → 24 | 7553.5 → 200.4 | 0.007413 |
| power_support | 343 → 327 | 7,905 → 5,326 | 3789.7 → 1008.4 | 0.010436 |
| right_shell | 1685 → 1632 | 90,991 → 68,659 | 9802.2 → 9648.2 | 0.017631 |
| soft_mouth_top | 81 → 84 | 27,408 → 18,089 | 3948.2 → 2260.3 | 0.019569 |
| sole_left | 95 → 81 | 56,791 → 10,062 | 9091.1 → 1304.4 | 0.022558 |
| sole_right | 95 → 81 | 56,791 → 10,062 | 9091.4 → 1304.8 | 0.022332 |
| top_head_shell | 453 → 368 | 90,628 → 90,977 | 8674.1 → 8475.9 | 0.022476 |
| upper_leg_left | 160 → 163 | 80,567 → 6,084 | 7688.5 → 880.3 | 0.020794 |
| upper_leg_right | 160 → 163 | 80,567 → 6,084 | 9408.7 → 882.6 | 0.020794 |
| yaw2roll | 269 → 66 | 10,316 → 366 | 4015.0 → 398.4 | 0.013715 |

下颚的边界样条从 1720 条减至 109 条；下头壳将 2852 条实际共线的样条边恢复为直线。部分文件另通过合并重复几何定义与有界数字精度减少存储，这一部分不计作面数改善。

The jaw reduced degree-one spline boundaries from 1720 to 109. The lower head shell recovered 2852 collinear spline edges as analytic lines. Some files also share duplicate geometry definitions or use bounded decimal precision; storage-only savings are not counted as face reduction.

## 全部 30 件 / All 30 parts

STL 列为三角片数量；STEP 列为 B-rep 曲面数量，两者不是同一种计数。尺寸列按原坐标系 X × Y × Z 表示测得的外形包围尺寸。

STL counts triangles; STEP counts B-rep faces. These are different quantities. Dimensions are measured extents along the original X × Y × Z axes.

| 零件 / Part | 数量 / Qty | STL triangles | STEP faces | X × Y × Z mm | Max sampled mm | CAD / Audit |
|---|---:|---:|---:|---|---:|---|
| 左脚踝 / ankle_left | 1 | 4,978 | 159 | 39.489 × 36.500 × 25.500 | 0.014862 | [三视图](docs/previews/ankle_left_cad_views.png) · [JSON](docs/audits/ankle_left.json) |
| 右脚踝 / ankle_right | 1 | 4,976 | 159 | 39.489 × 36.500 × 25.500 | 0.014862 | [三视图](docs/previews/ankle_right_cad_views.png) · [JSON](docs/audits/ankle_right.json) |
| PCB锁扣 / banana_pcb_locker | 1 | 1,388 | 38 | 54.052 × 3.800 × 6.652 | 0.012590 | [三视图](docs/previews/banana_pcb_locker_cad_views.png) · [JSON](docs/audits/banana_pcb_locker.json) |
| 髋部轴承压盖 / bearing_roll | 2 | 2,420 | 21 | 23.000 × 3.000 × 40.000 | 0.009022 | [三视图](docs/previews/bearing_roll_cad_views.png) · [JSON](docs/audits/bearing_roll.json) |
| 头部下壳 / bottom_head_shell | 1 | 20,970 | 1239 | 91.763 × 116.748 × 20.136 | 0.016824 | [三视图](docs/previews/bottom_head_shell_cad_views.png) · [JSON](docs/audits/bottom_head_shell.json) |
| 面部件 / face_part | 1 | 11,412 | 178 | 87.651 × 12.500 × 44.626 | 0.014303 | [三视图](docs/previews/face_part_cad_views.png) · [JSON](docs/audits/face_part.json) |
| 左脚 / foot_left | 1 | 19,922 | 473 | 40.086 × 54.000 × 16.909 | 0.012816 | [三视图](docs/previews/foot_left_cad_views.png) · [JSON](docs/audits/foot_left.json) |
| 右脚 / foot_right | 1 | 19,952 | 473 | 40.086 × 54.000 × 16.909 | 0.012513 | [三视图](docs/previews/foot_right_cad_views.png) · [JSON](docs/audits/foot_right.json) |
| 髋部连接件 / hip_l | 2 | 20,970 | 1081 | 32.450 × 34.501 × 19.016 | 0.015059 | [三视图](docs/previews/hip_l_cad_views.png) · [JSON](docs/audits/hip_l.json) |
| 下颚件 / jaw | 1 | 9,918 | 131 | 91.420 × 68.710 × 29.448 | 0.013038 | [三视图](docs/previews/jaw_cad_views.png) · [JSON](docs/audits/jaw.json) |
| 下颚柔性候选件 / jaw_soft | 1 | 6,726 | 46 | 87.675 × 32.234 × 8.439 | 0.020311 | [三视图](docs/previews/jaw_soft_cad_views.png) · [JSON](docs/audits/jaw_soft.json) |
| 躯干左壳 / left_shell | 1 | 20,970 | 1599 | 33.714 × 80.887 × 41.691 | 0.018082 | [三视图](docs/previews/left_shell_cad_views.png) · [JSON](docs/audits/left_shell.json) |
| 小腿连接件 / leg | 2 | 14,776 | 158 | 7.950 × 20.000 × 58.000 | 0.019968 | [三视图](docs/previews/leg_cad_views.png) · [JSON](docs/audits/leg.json) |
| M12镜头座 / m12_lens_holder | 1 | 10,992 | 53 | 24.000 × 14.800 × 16.000 | 0.007413 | [三视图](docs/previews/m12_lens_holder_cad_views.png) · [JSON](docs/audits/m12_lens_holder.json) |
| 嘴舵机支架 / motor_support | 1 | 3,616 | 118 | 73.500 × 54.200 × 18.800 | 0.011715 | [三视图](docs/previews/motor_support_cad_views.png) · [JSON](docs/audits/motor_support.json) |
| 颈部连接件 / neck | 2 | 1,468 | 16 | 2.000 × 20.000 × 11.000 | 0.001870 | [三视图](docs/previews/neck_cad_views.png) · [JSON](docs/audits/neck.json) |
| 颈部俯仰件 / neck_pitch | 1 | 7,120 | 111 | 35.000 × 18.006 × 27.693 | 0.012819 | [三视图](docs/previews/neck_pitch_cad_views.png) · [JSON](docs/audits/neck_pitch.json) |
| 眼部件 / noenoeil | 1 | 984 | 28 | 30.000 × 9.500 × 30.000 | 0.014277 | [三视图](docs/previews/noenoeil_cad_views.png) · [JSON](docs/audits/noenoeil.json) |
| 电池支架 / power_support | 1 | 12,832 | 327 | 54.500 × 17.003 × 83.491 | 0.010436 | [三视图](docs/previews/power_support_cad_views.png) · [JSON](docs/audits/power_support.json) |
| 躯干右壳 / right_shell | 1 | 20,970 | 1632 | 31.764 × 80.898 × 41.693 | 0.017631 | [三视图](docs/previews/right_shell_cad_views.png) · [JSON](docs/audits/right_shell.json) |
| 柔性上喙候选件 / soft_mouth_top | 1 | 7,870 | 84 | 87.820 × 32.569 × 3.276 | 0.019569 | [三视图](docs/previews/soft_mouth_top_cad_views.png) · [JSON](docs/audits/soft_mouth_top.json) |
| 左脚底接触件 / sole_left | 1 | 15,788 | 81 | 41.098 × 54.008 × 12.908 | 0.022558 | [三视图](docs/previews/sole_left_cad_views.png) · [JSON](docs/audits/sole_left.json) |
| 右脚底接触件 / sole_right | 1 | 15,902 | 81 | 41.098 × 54.008 × 12.908 | 0.022332 | [三视图](docs/previews/sole_right_cad_views.png) · [JSON](docs/audits/sole_right.json) |
| 头部上壳 / top_head_shell | 1 | 16,120 | 368 | 91.760 × 122.691 × 46.337 | 0.022476 | [三视图](docs/previews/top_head_shell_cad_views.png) · [JSON](docs/audits/top_head_shell.json) |
| 躯干底板 / trunk_base | 1 | 3,698 | 32 | 57.000 × 36.000 × 3.000 | 0.009041 | [三视图](docs/previews/trunk_base_cad_views.png) · [JSON](docs/audits/trunk_base.json) |
| 左上腿 / upper_leg_left | 1 | 12,250 | 163 | 28.000 × 47.659 × 60.997 | 0.020794 | [三视图](docs/previews/upper_leg_left_cad_views.png) · [JSON](docs/audits/upper_leg_left.json) |
| 右上腿 / upper_leg_right | 1 | 12,250 | 163 | 28.000 × 47.659 × 60.997 | 0.020794 | [三视图](docs/previews/upper_leg_right_cad_views.png) · [JSON](docs/audits/upper_leg_right.json) |
| 上腿加固板 / upper_leg_rigidity_plate | 2 | 3,600 | 46 | 1.000 × 45.000 × 58.058 | 0.010956 | [三视图](docs/previews/upper_leg_rigidity_plate_cad_views.png) · [JSON](docs/audits/upper_leg_rigidity_plate.json) |
| 髋偏航转横滚件 / yaw2roll | 2 | 12,404 | 66 | 23.000 × 25.800 × 20.500 | 0.013715 | [三视图](docs/previews/yaw2roll_cad_views.png) · [JSON](docs/audits/yaw2roll.json) |
| 头部偏航横滚件 / yaw_roll_motion | 1 | 5,814 | 87 | 34.000 × 35.900 × 22.500 | 0.008566 | [三视图](docs/previews/yaw_roll_motion_cad_views.png) · [JSON](docs/audits/yaw_roll_motion.json) |

## 仍需改善 / Remaining work

| 零件 / Part | 当前面数 / Faces | 说明 / Note |
|---|---:|---|
| 头部下壳 / bottom_head_shell | 1239 | 仍有大量碎面，不能视为简洁的原始 CAD / Still fragmented; not clean original design CAD |
| 髋部连接件 / hip_l | 1081 | 仍有大量碎面，不能视为简洁的原始 CAD / Still fragmented; not clean original design CAD |
| 躯干左壳 / left_shell | 1599 | 仍有大量碎面，不能视为简洁的原始 CAD / Still fragmented; not clean original design CAD |
| 躯干右壳 / right_shell | 1632 | 仍有大量碎面，不能视为简洁的原始 CAD / Still fragmented; not clean original design CAD |

15 件 STEP 仍大于 1000 KB。自由曲面和边界仍可进一步重建；不要把“有效实体”“切削通过”理解为每个尺寸都能直接参数化修改。

15 STEP files remain above 1000 KB. Further freeform-surface and boundary reconstruction is possible. A valid solid and a passed cut test do not imply that every dimension can be edited parametrically.

## CAD 展示 / CAD previews

![下颚最终三视图 / Final jaw CAD views](docs/previews/jaw_cad_views.png)

![脚底最终三视图 / Final sole CAD views](docs/previews/sole_left_cad_views.png)

![下颚前后真实边界对比 / Jaw boundary comparison](docs/previews/jaw_before_after.png)

前后对比图为透明线框，包含背面边界；三视图则用最终 STEP 计算遮挡关系。全部 30 件见[图册](docs/CAD_VIEWS.md)。

The before/after image is a transparent wireframe including rear edges; the CAD sheets compute visibility from the final STEP. See the [complete 30-part gallery](docs/CAD_VIEWS.md).
