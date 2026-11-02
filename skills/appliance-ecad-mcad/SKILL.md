---
name: appliance-ecad-mcad
description: Coordinate KiCad PCBs, SolidWorks enclosures, and Blender assembly reviews using a shared mechanical contract. Use for appliance development, PCB-to-enclosure fit, mounting patterns, component-height and connector clearances, revisioned ECAD/MCAD exports, and enclosure feedback to KiCad. Use blender-solidworks-transfer for transfers without electronics integration.
---

# Appliance ECAD / MCAD bridge

Develop the electrical and mechanical design together while preserving each application's native source. KiCad owns the schematic, nets, footprints, routing, board outline and mounting holes. SolidWorks owns the enclosure, fasteners, standoffs and mechanical assemblies. Blender owns visualization and spatial review; mesh edits do not silently redefine KiCad copper or native CAD.

The installed `appliance_bridge` MCP supplements the existing KiCad, Blender and SolidWorks servers. Discover current tool schemas. The bridge tools are `inspect_pcb_mechanics`, `export_pcb_package`, `check_pcb_design_rules`, `check_pcb_enclosure_fit`, and `send_enclosure_feedback_to_pcb`. If the current chat predates installation, restart Codex to load the new server. Source and integration tests are maintained under the chat workspace's `appliance-bridge/` and `work/` folders; generated demo files live in `outputs/appliance-bridge-demo/`.

## Establish the project

For a new appliance, obtain the function, power source, board/enclosure limits, interfaces, mounting hardware and manufacturing process before treating any prototype as the finished design. Separate the actual appliance requirements from setup fixtures. Do not infer a complete electrical design from a mechanically valid empty PCB.

Keep a project folder with native KiCad project/schematic/PCB, native SolidWorks parts/assembly, a Blender review file, exchange artifacts, and versioned JSON contracts. Never overwrite another project's open document or use a stale export as the latest board. Use explicit absolute paths.

## Shared mechanical contract

1. Save the PCB, then call `inspect_pcb_mechanics` with a deliberate XY origin and optional `envelopes_path`. Mounting candidates are H-numbered footprints with drilled pads. Verify their role; other NPTH pads may belong to connectors. Missing component envelopes or models must remain unknown.
2. Component envelopes use mechanical-frame millimeters, include top/bottom placement and actual maximum height, and need provenance from the part model or datasheet. Include connector mating/insertion space, cable bend space, batteries, moving parts and other required access volumes when applicable. Conservative envelopes are acceptable when labeled. Do not invent dimensions to make a fit pass.
3. Call `export_pcb_package`. It creates assembly STEP/GLB, board-only STEP/STL, and `mechanical-contract.json` with source/model/envelope hashes. STEP goes to SolidWorks; GLB goes directly to Blender. Do not convert a PCB mesh back into KiCad circuitry.
4. The contract frame is X right, Y upward, nominal PCB top Z=0; nominal board bottom is minus its full thickness. KiCad coordinates map as x=KiCadX-originX, y=originY-KiCadY. KiCad 10's exported 3D datum is different: apply the explicit `kicad_export_to_mechanical_translation_mm` to the imported root assembly exactly once. Native GLB imports into Blender in meters; STEP imports into SolidWorks in mm. Validate bounds and an asymmetric location, not just appearance.
5. The verified KiCad 10.0.7 fixture exported a 1.6 mm nominal PCB as 1.51 mm substrate with the component starting at 1.595 mm in export space. The contract's -1.6 mm Z shift aligns the nominal top. Copper/mask omissions and model offsets explain the remaining small differences; do not scale the substrate to the nominal thickness. Check actual output on a new exporter version or stackup.

## Enclosure and fit

Use `enclosure.json` with schema `appliance-enclosure/v1` and explicit `units: mm`. It contains a rectangular `cavity_bounds_mm` [min XYZ,max XYZ], minimum clearance, mounting-alignment tolerance, fastener radial clearance, standoffs (reference, center, outer radius, fastener diameter, support-top Z), optional obstacle AABBs, and required connector/access-volume AABBs. These are design inputs, not universal manufacturing allowances.

Link it to the saved native CAD using `source_cad`, `source_cad_sha256`, and measured `source_cad_bounds_mm` from SolidWorks `model_info`. Record exported enclosure STL path/hash under `mesh_export`, with its explicit coordinate policy. If using `same_axes_translation_only`, compare mesh size to native CAD size and reconcile only the measured translation. SolidWorks may translate STL to positive space; never assume STL preserves the part origin. Reject scale/axis discrepancies rather than aligning by eye.

Build/edit native enclosure features from the contract and preserve the native project. Use `doc_open` to import the KiCad STEP; it may be an assembly even for one PCB. Preserve child components, save their native files, and verify that the final assembly's references exist. Place the PCB root using its recorded transform; keep the enclosure in the shared mechanical frame.

Run both checks:

- `check_pcb_enclosure_fit` verifies source/model/export/CAD revisions, conservative cavity/access/obstacle clearances, hole alignment, fastener clearance, support height and support inside the board polygon. A changed PCB/model/envelope/CAD must trigger a fresh package. `UNVERIFIED` is not a fit pass.
- SolidWorks `asm_interference` checks actual assembled solids. Use `includeCoincident=false` for intended support contact, then inspect contact locations and minimum distances separately. Zero interference alone does not prove clearance, screw engagement, connector access, assembly sequence or a tolerance stack-up.

Blender reviews must use the actual exported geometry and explicit transforms. The installed bridge's `blender_scene.py` demonstrates import, revision checks, world-space bounds and a review render. For another appliance, inspect the source geometry and adapt presentation settings; the demo's component-height coloring is cosmetic, not reference mapping. Save a new review copy. Do not clear an existing scene.

## Feedback and electrical checks

When enclosure constraints change, update the measured CAD contract and call `send_enclosure_feedback_to_pcb`. It writes cavity and standoff references on Dwgs.User in a NEW PCB copy; it never moves holes, pads, tracks, nets or Edge.Cuts. Review the references, make the authorized changes in native ECAD, reroute as needed, and regenerate the package. A stale source or existing feedback file is refused.

Use `check_pcb_design_rules` for the complete native PCB DRC report, including unrouted items. The original KiCad MCP's `run_drc_check.success` means the command executed, not that no violations exist. Also run schematic ERC and verify schematic/PCB consistency for a real circuit. Read severity and counts; a project without a schematic cannot establish electrical completeness. Component pinouts, ratings, power dissipation and required electrical clearances remain electrical design requirements.

Deliver native files, contract, exchange package, measured mechanical checks, electrical reports and a preview. State exactly what passed and what remains unverified. A mechanical-fit fixture is not an electrically functional or manufacturing-qualified appliance.

## Verified local reference

The setup fixture is a 60x40 mm board, 1.6 mm nominal thickness, four 3.2 mm holes, an explicitly synthetic component-height block, and a native open-top SolidWorks enclosure. Verified on KiCad 10.0.7, Blender 5.2.3, and SolidWorks 2026: PCB DRC positive/shorted negative controls; native STEP import and hole radii/positions; conservative fit and failure controls; exact assembly interference (zero nominal, collision detected after an intentional move); transformed Blender placement; and feedback copy preserving board outline and holes. No real circuit, lid, connector, thermal or electrical performance was validated by that fixture.

## Scripted parametric components

For CadQuery or build123d generators, use the installed parametric-mechanical-design skill. Its engines run in separate Python environments. Share the real PCB contract and parameter JSON with the generator, preserve its source, and import its STEP output into the master SolidWorks assembly. Preserve native mates there; keep Blender as the review layer. Regeneration invalidates dependent export/fit receipts, so rerun revision checks, clearances and interference before claiming a fit. Do not replace PCB requirements with the coupon example.
