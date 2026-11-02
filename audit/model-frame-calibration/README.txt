SYNTHETIC EXPORTER CALIBRATION FIXTURE

This asymmetric box fixture establishes the KiCad10.0.7 STEP model frame for
zero and nonzero top/bottom angles. It is not robot component geometry or
physical-fit evidence.

Files are byte-preserved from the original work fixture, including the absolute
model path in fixture.kicad_pcb and the original script's output-path convention.
Regeneration requires choosing a new output directory and updating the fixture
model path. The original script stages are shape (CadQuery), board (pcbnew), and
inspect (CadQuery). Between board and inspect, export with KiCad CLI:
  pcb export step --user-origin 0x0mm --output <fixture.step> <fixture.kicad_pcb>

See ../kicad-model-frame-calibration.json for recorded inputs, results and hashes.

