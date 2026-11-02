---
name: parametric-mechanical-design
description: Create and regenerate mechanical parts and assemblies with the installed CadQuery and build123d Python libraries, then exchange geometry with SolidWorks and Blender. Use for CAD-as-code, configurable mechanisms, parameterized component families, and scripted enclosure or bracket generation. Use appliance-ecad-mcad for PCB integration and blender-solidworks-transfer for ordinary app-to-app transfers.
---

# Parametric mechanical design

Use CadQuery or build123d as a reproducible geometry generator. Preserve Python source and a parameter file as the design definition. Preserve native SolidWorks assembly mates, drawings and checks in SolidWorks; use Blender for geometry review and rendering.

For MicroDuck size or limb variants intended for simulation/retraining, also read the sibling `microduck-training-gym/SKILL.md` and its `references/design-iteration.md`. Generate separately identified rigid links and their joint/mounting frames; keep hardware dimensions distinct from body-scale parameters. Return masses/inertias with units and provenance to the robot contract. CAD component placement does not automatically create simulator joints or a compatible control policy.

## Installed engines

Read [the local runtime reference](references/local-runtime.md) before execution. CadQuery 2.8.0 and build123d 0.13.0 are installed in SEPARATE Python environments because their released OpenCascade packages conflict. Run each with its own absolute Python executable. Do not install either into Blender's Python, KiCad's Python, the MCP runtime, or the other engine's environment. These are Python CAD libraries; a separate graphical editor was not installed.

Choose CadQuery for workplane/selector workflows and assemblies requiring its constraint solver. Choose build123d for explicit geometry, algebraic/builder composition, and labeled joint-based placement. Respect the user's engine preference. build123d joint connections reposition components; do not describe them as a continuously solved mechanical linkage. Use native SolidWorks mates and motion tools when persistent mechanism relationships are required.

## Author and regenerate

- Keep named parameters in millimeters/degrees, with explicit origins, axes, configuration name, and component identifiers. Validate physical limits before building (positive thickness, usable hole and wall sizes, intended clearance). Derive repeated dimensions from shared inputs rather than scattering literals through scripts.
- Make generators deterministic: component functions accept parameters and return shapes; regenerate derived files after changes. Distinguish geometry parameters from export tessellation tolerances and from engineering allowances.
- For electronics-related parts, read the actual appliance mechanical contract for the PCB outline, mounting positions, thickness, connector/access volumes and component envelopes. Do not substitute the installation test fixture. Include PCB/model/parameter hashes in the derived geometry manifest.
- Validate solids with the engine's native validity checks, dimensions, analytic volumes where practical, body count, and intersection/clearance tests. Test at least a representative changed parameter set for a new reusable generator; verify that relevant geometry actually changes.
- Keep components separate and named in the assembly. Check the solver's resulting placements, not merely whether solve() returned. CadQuery Axis constraints default to opposed directions; use an explicit angle (for example param=0 for co-directed axes) and verify the resulting orientation. Use selector-compatible component identifiers such as letters/digits/underscores and unique names across simultaneously imported variants. In build123d verify joint-derived locations. Regenerate/reposition when inputs change; exported files do not carry the generator's live relationships.

## Exchange and verification

Export STEP for SolidWorks and a clearly unit-labeled mesh or glTF/GLB for Blender. Preserve the CAD source script and parameter JSON; STEP imports do not reconstruct the Python program, a native SolidWorks feature history, or all assembly constraints.

Record generator/library versions, source and parameter hashes, units, component frames, expected bounds/volumes, mesh tolerances, and output hashes. Verify a STEP reimport for body count, dimensions and volume before using it downstream. Prefer an explicit source-to-destination transform over changing scene units or centering geometry by eye.

Use the installed SolidWorks MCP's `doc_open`, `model_info`, `asm_component_list`, and `doc_save` to validate the generated STEP, inspect the resulting part/assembly structure, and preserve native copies when requested. Imported assemblies may create child documents; save their references as well. For persistent mechanical motion build/retain native mates in the master SolidWorks assembly. Run interference and relevant minimum-distance checks after parameter updates.

Use `blender-solidworks-transfer` for app-to-app units, axes and import/export details. Import each generated mesh into a new collection/scene without clearing existing work. A millimeter STL needs explicit conversion to physical Blender units. Use world-space/evaluated coordinates for dimensions and volume; imported scale can live in the object transform. glTF/GLB uses meters and may convert axes: check an asymmetric feature and a known dimension. Meshes are visualization/export derivatives, not authoritative manufacturing history.

Use `appliance-ecad-mcad` when a PCB is involved. Feed generated mechanical constraints back through that workflow, then regenerate exports and rerun both electrical and mechanical checks. Never overwrite ECAD routing or hole placements merely because a generated enclosure changed.

## Verified starter generator

`scripts/generate_fit_coupon.py` is a small reusable example, not a complete mechanism or finished appliance. It accepts `--engine cadquery|build123d`, `--params <JSON>`, and `--output-dir <directory>`. Parameters are width_mm, depth_mm, plate_mm, hole_diameter_mm, pin_diameter_mm, and pin_height_mm. It generates a holed plate and smaller pin, checks placement/nonintersection/volumes, exports STEP/STL, reimports STEP, and writes a manifest. It regenerates its derived files in the explicitly chosen output directory; use a dedicated generated directory.

Run the script using the selected engine's Python executable from the local runtime reference. Copy/adapt it into the actual project when it helps; keep that project's source and parameters with its deliverables. For arbitrary mechanisms, implement the required geometry and engineering checks rather than treating a passed coupon as qualification.

Official references: https://cadquery.readthedocs.io/ and https://build123d.readthedocs.io/.
