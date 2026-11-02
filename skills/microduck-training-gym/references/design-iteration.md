# MicroDuck: mechanical design → simulation → policy iteration

Use for a requested morphology change. This is an orchestration workflow, not a tested automatic SolidWorks-to-Isaac exporter. The installed training baseline and generic Windows scene test have passed; a complete modified MicroDuck CAD-to-training round trip has not yet been demonstrated. Report capability and validation status separately.

For current PCB models, consult package `MODEL-PLACEMENT-PROGRESS.txt`: project-local models and native STEP/GLB/Blender review files are available. They preserve author per-instance local dimensions and calibrated footprint placements, not original vendor origins or qualified physical fit. Moving to a new board/harness or body revision invalidates previous enclosure clearances. Keep the pending XL330/Feetech protocol/actuator choice explicit before declaring one coherent physical robot and policy.

## Define one reproducible variant

Resolve the requested change: target dimensions or scale, preserved/replaced hardware, added links and joints, intended use of each limb, and the behavior to learn. Use known project context and inspect sources first; ask only for unresolved decisions that change the design. A cosmetic appendage, passive limb, and independently actuated limb have different simulation and policy consequences.

Locate the actual source geometry and license. Existing simulation USD does not prove editable SolidWorks files exist. If native CAD is unavailable, describe whether the work will use upstream CAD, a new parametric reconstruction, or a mesh-based prototype. Keep those provenance differences visible; do not call reconstructed CAD the original design.

Preserve the baseline and use a new variant ID/revision, e.g. `microduck_long_legs/r001`. Keep the working upstream robot and published policies intact. Put generated source, parameters, and derived artifacts in a dedicated project; retain the project location for subsequent iterations. Typical contents:

```text
variant/
  contract.json
  cad/                 editable parts/assembly or generator + parameters
  meshes/visual/       one or more named meshes per rigid link
  meshes/collision/    simplified per-link collision shapes
  robot/               URDF, MJCF, or authored articulated USD + dependencies
  task/                variant-specific Isaac Lab configuration
  runs/                run manifest, metrics, videos, checkpoint references
```

## Shared robot contract

Create/update `contract.json` from measured/derived data. It is a project contract rather than a fixed SDK schema. At minimum record:

| Record | Required meaning |
| --- | --- |
| Revision | variant ID, parent revision, source/license, generator/tool versions, source and output hashes |
| Coordinates | source/destination units, handedness, up/forward axes, explicit transforms, robot root frame |
| Parameters | actual changed dimensions; body scale separate from fixed servo, bearing, fastener, battery, sensor, and PCB envelopes |
| Rigid links | stable IDs, CAD component/object association, visual/collision paths, link frames, material/density or measured mass, COM, inertia tensor and its reference frame |
| Joints | stable name, parent/child, type, joint frames, normalized axis, sign convention, limits, damping/friction, default pose, active/passive/coupled status |
| Actuation | selected real/assumed motor and gearing; torque-speed/current/voltage limits, control mode/gains, latency and backlash; parameter provenance |
| Sensors/contact | foot/contact groups, IMU and camera frames, collision filters, ground/contact material assumptions |
| Policy interface | ordered observation terms with dimensions/normalization/history, ordered controlled joints, action semantics/scales/offsets, control timestep, policy architecture signature |
| Validation | measured checks and evidence paths for CAD, articulation, dynamics, training, evaluation; unknowns and failed checks remain explicit |

Use SI in the robot/simulation contract (m, kg, s, radians, N·m, kg·m²). CAD tools may return mm and kg·mm²: convert lengths by 10^-3 and inertia by 10^-6 exactly once. Record whether inertia is about COM or another origin; rotate the tensor into the declared frame and use the parallel-axis theorem when changing its reference point. Verify symmetry, physically plausible positive principal moments and inertia triangle inequalities; do not substitute the whole-assembly tensor for each link. Fixed-link merging must aggregate mass and inertia consistently.

## CAD and Blender roles

Read `blender-solidworks-transfer` before exchange. Verify live application connections before claiming app integration. Preserve user documents and selections; use new revisioned files/configurations for variants. The user's design request authorizes scoped edits, not unrelated changes or overwrites.

Use SolidWorks for editable dimensions, mounting interfaces, materials, mass properties, interference and motion-envelope checks. Use the installed tool schemas (`model_mass`, component/assembly inspection, exports) rather than assuming outputs use SI. Structural FEA is optional when loads justify it and the required add-in is available; locomotion simulation is not structural qualification.

Use Blender for scene/shape review, per-link mesh cleanup, visual materials, simplified collisions, and reviewing joint axes and swept volumes. Bones/constraints can help preview motion but do not replace the robot description. A Blender Rigid Body run is not the Isaac Lab training validation.

For repeatable dimension sweeps, use `parametric-mechanical-design` and its isolated CAD runtime. Retain generator code and parameter JSON. Prefer native CAD/STEP as a mechanical master and meshes as derivatives. Export each rigid link with known local coordinates and an assembly-transform manifest; never center each part independently without updating its frame. Use glTF/USD/mesh formats according to verified exporter support; do not assume Blender reads STEP or SolidWorks exports robot URDF out of the box.

Separate visual detail from convex/primitives/decomposed collision geometry appropriate to the chosen Newton solver. Confirm importer treatment of scale, materials, fixed joints, and collision approximations. Decorative meshes need not become collision shapes.

## Resizing

For uniform geometric similarity at fixed density, link mass scales as s³ and COM-centered inertia as s⁵. These are dimensional checks, not a hardware design rule: real motors, batteries, wall thicknesses, and fasteners are often not scaled. Recompute per-link mass and inertia from the actual revised assembly/materials and include off-the-shelf components.

Check torque/speed/current requirements against the selected motors and transmission, load-bearing sections, joint travel, foot contact/support, COM, cable routing, cooling and component clearances. Do not scale the original servo torque capability or reuse its calibrated BAM constants as if a physically larger motor had been selected. Label estimated actuator data; use measurements/datasheets when available.

Update reset height, standing pose, reach/clearance targets, contact offsets, terrain dimensions, command speeds, reward normalization, domain-randomization ranges, and timestep/control gains as warranted by the new dynamics. Test stability rather than imposing a universal scale factor on all control parameters.

## Added/removed limbs and joints

Define a connected articulation with unique link/joint names. Specify parent/child and correct local joint frames, limits, motor mounting, self-collision exclusions, and reset pose. Closed kinematic loops need explicit supported modeling; do not silently turn them into an unconstrained tree. Fixed, passive, mimic/coupled, and actively controlled joints are not interchangeable.

Update the variant's ordered joint/action mapping, actuator groups, proprioception, privileged critic observations, contact sensors, collision/termination body lists, rewards and curricula. The upstream task contains biped/foot and head assumptions; inspect its `flat_env_cfg.py`, `rough_env_cfg.py`, and `mdp/` implementations before reuse. Additional arms may need balance/energy rewards; additional legs can require gait/contact and support logic changes. Avoid classifying a deliberate new contact as a fall.

The backlash asset can contain passive joints in addition to the 14 commanded baseline joints. Distinguish simulator DOFs from policy actions and validate every name selection; do not set policy output size from total DOF count alone.

## Build and inspect the simulation asset

Author a robot description (URDF/MJCF or articulated USD) from the contract, including mass/inertia, joints, limits, collision shapes and mesh dependencies. CAD assembly constraints are not automatically a complete robot description. Use an existing exporter only after verifying availability and that it retains the required fields; otherwise generate the description explicitly and validate it.

For import/conversion, consult the installed Isaac Sim `skills/urdf-mjcf-to-usd-conversion/SKILL.md` and Newton conversion/actuator guidance as relevant. Locate installed-version APIs and read their instructions before use. Do not paste an unverified importer snippet or assume a PhysX asset's drives/contact settings become correct Newton BAM actuation after conversion.

Keep the variant's assets and environment in a separate user extension/project with distinct task IDs. Use the installed version's supported extension registration mechanism. Read repository/project instructions before implementing task code; do not alter the published baseline in place.

Before training, verify loaded asset bounds/units, total and per-link mass/COM/inertia, link/joint counts and names, axes/signs, default pose, limits, and visual-to-collision alignment. Exercise a small bounded command on each active joint, check passive/coupled responses and limits, then test gravity/standing/contact behavior at low parallelism. Check finite state, penetration, constraint drift and energy explosions. Inspect an actual rendered view and numeric telemetry. A successful import alone is insufficient.

## Policy adaptation and retraining

Compute a policy-interface signature from ordered observation/action semantics, shapes, normalization/history, timing, and architecture. Do not rely on tensor shape alone.

- With unchanged interface and only mechanical/dynamic changes, an old policy may initialize a fine-tuning experiment after a bounded evaluation. It is not evidence the revised body can walk.
- With reordered or changed observations/actions, topology, history, or network dimensions, train a fresh policy by default. Reuse weights only through an explicit documented mapping, validating shapes and joint semantics. Do not blindly resume an optimizer/checkpoint or load an incompatible ONNX policy.
- Reset/recalibrate normalization and domain-randomization assumptions where the revised observations/dynamics warrant it. Derive the actor/critic dimensions from actual environment output; baseline 61/14 is not universal.

First run task enumeration and bounded random/zero-action checks, then a small PPO smoke run that saves/reopens a checkpoint. Follow the training skill's existing checks. Start full training only within the requested experiment budget and monitor finite rewards/state, falls, contacts, torque/current limits and training throughput.

Record CAD/description/mesh/contract/task hashes, runtime versions, seeds, hyperparameters, initial checkpoint provenance and final policy signature with each run. Never reuse `latest` across variant directories without checking provenance. Attach the same signature to ONNX exports and any proposed runtime controller.

## Evaluate the design, then iterate

Compare each candidate against a preserved baseline using common seeded tasks, command schedules and terrain ranges. For fair design comparisons report training sample/time budgets and evaluation conditions, multiple seeds when needed, and whether terrain/speed is absolute or body-normalized. Report falls, tracking/completion, distance/speed, mechanical clearance violations, peak torques, energy estimates and runtime. Do not call simulated electrical energy or safety a measured hardware result.

Export review images/video plus a compact design/run manifest. Feed observed failures back into named CAD parameters or actuator/task changes, regenerate affected artifacts, and rerun the relevant checks. A CAD change invalidates downstream geometry/dynamics results until rebuilt; a policy-interface change invalidates old policy compatibility.

Distinguish design generation, geometry validation, physics validation, smoke training, trained-policy evaluation, manufacturability, and physical deployment in the result. Unknown component data can support a labeled simulation concept, but cannot establish physical feasibility. Do not fabricate missing motor ratings or claim successful hardware operation. Fabrication, purchasing, and running a physical robot remain separate user-directed steps.
