---
name: blender-solidworks-transfer
description: Import, export, and transfer 3D models between Blender and SolidWorks using their MCP servers. Use for Blender-to-SolidWorks or SolidWorks-to-Blender geometry exchange, unit and orientation checks, STL transfers, and CAD-format conversion. Does not handle 2D drawing sheets or promise preservation of parametric history through meshes.
---

# Blender ↔ SolidWorks transfer

Carry out the requested transfer and verify the destination geometry. Interpret “3D drawings” as models unless the request refers to drawing sheets, dimensions, or views. Use the installed Blender and SolidWorks MCP servers; discover current tool schemas before calling them. The selected profile is `ahujasid/mcp-for-blender` (published `mcp-for-blender` 2.2.4 package) and `soheil-mp/solidworks-mcp` (0.1.0, commit `49f545c586e2e1bd12f99ecddf1813369bd0f778`). Tool discovery alone is not a live application test.

## Choose the transfer

- Default to binary STL for basic shape transfer in either direction. It transfers tessellated surfaces, not materials, textures, assembly mates, animation, or feature history. State this limitation when it matters to the requested result.
- Keep the native `.blend`, `.SLDPRT`, or `.SLDASM` source. Use STEP as an additional CAD master when exact CAD geometry is needed. Blender does not provide a standard native STEP reader/writer: verify an installed converter/add-on before choosing this route. A STEP file made from a mesh does not restore the original analytic surfaces or design intent.
- For multiple parts, export separate named files plus a manifest of their transforms when identity matters. A single STL can combine bodies and lose assembly structure.
- If the user needs editable dimensions or a feature tree from Blender, explain the reconstruction/recognition work and determine its scope. FeatureWorks is conditional on installed capabilities and geometry; do not promise automatic parametric reconstruction from STL.
- Use an explicit user destination. Otherwise place deliverables in the current workspace's `outputs/3d-transfer/` folder. Use absolute paths and new filenames to preserve existing files.

## Inspect before transferring

1. Resolve the source model or named selection, transfer direction, and destination. If several open documents or selections are plausible, ask one focused question. Do not silently export every scene object.
2. Blender: call `get_addon_status` once, then `get_scene_info`; use `execute_blender_code` for world-space bounds, evaluated meshes, units, and export/import. SolidWorks: use `sw_status` and `doc_list`, select the requested document with `doc_activate`, then query `model_info` or assembly components as appropriate. Existing user documents are read-only to this server unless explicitly adopted for editing; export does not require adopting them.
3. Record physical dimensions, part/object count, unit convention, transforms, and a recognizable orientation. Scene display units alone do not establish STL units. Preserve the source selection and active object after temporary export operations.
4. Verify application connectivity separately from MCP tool discovery. A server can list tools even when its desktop application is absent. For SolidWorks, confirm the full CAD application and `SldWorks.Application` COM registration; eDrawings, Composer Player, PDM, and Manage clients do not provide that CAD automation interface. For Blender, confirm the running instance exposes the enabled add-on server. If disconnected, diagnose app presence versus app/add-on startup before proceeding. Do not reinstall working integrations as a first response.

## Units and orientation

STL stores coordinates without a unit declaration. Agree on millimeters by default and record that convention beside the file. For an existing STL, use supplied units or a known dimension; ask if scale cannot be inferred reliably.

In Blender, physical meters = world-space coordinate distance × `scene.unit_settings.scale_length`. When exporting STL coordinates in millimeters, one explicit convention is `global_scale = scale_length * 1000` with `use_scene_unit=False`. When importing millimeter STL into an existing Blender scene, use `global_scale = 0.001 / scale_length` with `use_scene_unit=False`. Verify the actual operator properties first and apply the conversion exactly once. Do not change a whole scene's unit scale just to make one import look right.

Current Blender versions use `bpy.ops.wm.stl_export` and `bpy.ops.wm.stl_import`; inspect their RNA properties for the installed version. Older versions may use `export_mesh.stl` / `import_mesh.stl`. Do not assume an exporter is installed because its format is familiar.

The selected SolidWorks server reports millimeters. `doc_open` imports STL with millimeter coordinates and requests solid bodies, then reports the actual body type, volume, and extents. `model_export` verifies the output header, triangle count, unit convention, and extents; read its `details` and warnings. It temporarily changes and restores import/export preferences. COM fallback code uses meters for many raw coordinates: explicitly convert if needed. Never claim dimensions are verified merely because a tool returned success.

Blender is normally Z-up and SolidWorks commonly uses Y-up. Establish the requested front/up directions from the source. Use one documented rotation at the transfer boundary when needed, preserve handedness, and verify an asymmetric feature. Do not rotate twice or silently mirror the model.

## SolidWorks → Blender

1. Identify the active configuration and assembly scope. Inspect export tessellation settings for the requested accuracy; do not silently accept a coarse mesh for precision work.
2. Call `model_export` with an absolute `.stl` path; set `stlBinary=true` and an appropriate `stlQuality` (or custom deviation/angle). Read the actual returned path, since SolidWorks may capitalize the extension. Verify the reported units, dimensions, and nonempty file. Export `.step` too when a CAD master is requested. Native saves use `doc_save`, not the export tool.
3. Import the STL through Blender Python with the explicit unit conversion and axis mapping. Track new objects by comparing object identities before/after import, rather than assuming the active object is the full result. Put imported objects in a named collection without clearing the existing scene.
4. Compare dimensions and inspect the result. Save a new `.blend` copy if requested; do not rebind or overwrite an unrelated open project.

## Blender → SolidWorks

1. Export only the intended evaluated geometry, including the relevant modifiers. Check boundaries, non-manifold edges, normals, and disconnected shells. A closed manifold mesh is needed for a reliable solid import; open geometry may become surfaces or graphics. Repair only within the user's intended scope, using duplicates for destructive edits.
2. Export binary STL with explicit millimeter coordinates and the chosen orientation. Preserve source transforms and selection. Verify file size and triangle count; do not decimate detailed geometry without a task-based reason.
3. Call `doc_open` with the absolute path. The selected server temporarily disables 3D Interconnect and imports STL in mm. Check `imported.solidBodies`, surface/mesh counts, volume, and extents; do not treat a graphics-only result as an editable solid.
4. Confirm dimensions and requested editability with `model_info`. Save the imported result using `doc_save` with `mode="as"` and a new native path when requested. Feature recognition is not exposed by this profile: do not invent a recognition tool or promise a recovered parametric tree.

## Verify and deliver

- Confirm destination object/body counts and physical dimensions after unit/axis conversion. Compare a known dimension or matched oriented extents; axis-aligned bounds can change after rotation. Use an engineering tolerance appropriate to the task and distinguish tessellation deviation from scale error.
- Inspect a destination view, especially holes, thin walls, curved surfaces, and asymmetric features. Use Blender `look` or SolidWorks `view_screenshot`. A screenshot complements dimensional checks.
- For solid/manufacturing use, verify closed geometry and a valid solid; compare volume when available. Graphics-only imports do not pass a solid-body requirement.
- A real SolidWorks STL round trip left nearly coincident vertex seams in Blender. On an imported copy, diagnose boundaries and duplicate vertices before repair. A bounded weld followed by normal recalculation can close numerical seams; choose the tolerance below meaningful feature size and recheck dimensions/volume. The verified test used 0.00001 mm, not a universal repair tolerance. Compute mesh volume from world-transformed vertices: STL import may retain its scale in the object transform.
- Write a small adjacent JSON manifest: source/destination files and apps, objects/configuration, format, STL coordinate units, Blender unit scale, applied scale/axis mapping, dimensions before/after, tessellation settings when known, and limitations. Mark unavailable checks as unverified.
- Deliver clickable absolute links, the destination app/document, and any remaining limitation. If import failed, retain the source/export and report the specific failed step. Stop after a focused correction and recheck if the same blocker persists; do not repeatedly modify geometry or global preferences without new evidence.

## Sources

Consult current official documentation when installed-version behavior is uncertain:
- Blender STL import/export: https://docs.blender.org/manual/en/latest/files/import_export/stl.html
- SolidWorks mesh import/export: https://help.solidworks.com/2026/english/SolidWorks/sldworks/c_stl_files.htm


## MicroDuck design iterations

For MicroDuck resizing, limb changes, or geometry intended for robot retraining, also read the sibling `microduck-training-gym/SKILL.md` and its `references/design-iteration.md`. That skill coordinates the articulated robot and training task. Preserve one named object/part per rigid link, link-local frames and assembly transforms, and separate visual from collision geometry. A flattened STL transfers appearance but does not preserve joints, inertia, actuator models, or policy mappings. Follow the robot contract's explicit axis/unit conversion rather than assuming CAD mates or Blender bones become simulator joints. Export editable CAD and per-link geometry; validate the imported articulation separately before claiming it is ready for training.

## CadQuery and build123d sources

Use parametric-mechanical-design when geometry is generated parametrically with CadQuery or build123d. Keep Python sources and parameter JSON authoritative for those generated parts, STEP for CAD exchange, and a unit-labeled mesh/glTF derivative for Blender. Use each library's separate installed Python environment. STEP does not preserve generator code, native SolidWorks feature history or all mates; validate component frames, dimensions, bodies and volume after regeneration. For PCB-based assemblies also use ppliance-ecad-mcad.
