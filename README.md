# MicroDuck training gym and design assets

Private working snapshot prepared on **2026-11-01**. This repository contains
MicroDuck CAD, PCB recovery projects, component models, simulation/training
artifacts, audit evidence, and four reusable personal skills.

## Start here

- [Latest package and remaining gaps](MODEL-PLACEMENT-PROGRESS.txt)
- [End-to-end status](END-TO-END-STATUS.txt)
- [17-stage software-check evidence](audit/pcb-tools/software-stack-result.json)
- [Recorded Isaac training run](simulation/validation-runs/2026-10-26_14-57-39_pcb_pipeline_baseline/validation.json)

Recorded checks are dated evidence from the source workstation. The bounded
Isaac run proves integration; it does not establish a reliable walking policy.
Manufacturing and physical reproduction remain unqualified. The canonical
XL330/Feetech choice and revised-IMU copper recovery remain open.

## Clone the published assets

GitHub Desktop supports this repository's Git LFS files. For command-line Git:

```sh
git lfs install
git clone <this-repository-url>
cd microduck-training-gym
git lfs pull
python tools/verify_publication.py
```

Use a Git/LFS clone rather than relying on GitHub's source ZIP. LFS stores CAD,
meshes, archives, media and policy weights separately from their Git pointers.
See [GitHub's LFS documentation](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage).

## Editing and reuse

- `editing/kicad-models-attached/`: five native KiCad review projects with local
  footprint models, assembly STEP/GLB exports and Blender review scenes. Keep
  each complete folder together; models use `${KIPRJMOD}` paths.
- `editing/kicad-cache-repaired/wire_hub_1V0A/`: separate engineering repair of
  the stale GND cache. This revision has no added 3D models; compare its audit.
- `editing/blender/`, `editing/solidworks/`, `community/SolidWorks-XL330-v1.1/`:
  robot meshes, exchange geometry and the community native CAD reconstruction.
- `simulation/`: USD assets and recorded training/export/replay evidence.
- `tools/`: recovery, generation and validation tools. Native KiCad/pcbnew,
  CadQuery/OCP, Blender and the documented WSL Isaac/PCB environments are
  separate prerequisites; their installed runtimes are not embedded here.
- `skills/`: MicroDuck, ECAD/MCAD, Blender/SolidWorks transfer and parametric
  CAD skills. Copy the desired folders into your personal skills directory and
  adapt machine-specific paths and application connections before reuse.

Tracked asset layout and payload bytes are preserved. Reviewed optional payloads are deferred as described below. Many historical scripts and
reports record absolute source-workstation paths. Consult the skill references
for the tested Windows ARM64 / WSL setup rather than assuming those paths exist
on a new machine. Review author/recovered frames before mechanical fit checks.

## Provenance and terms

Selected files from seven pinned source repositories are preserved as **plain file snapshots**, with their
original LICENSE/NOTICE files. [SOURCE-REPOSITORIES.json](SOURCE-REPOSITORIES.json)
records the original URLs and exact commits. Third-party terms remain attached
to each source; there is no blanket license for the whole collection. Robot
mesh derivatives include CC BY-NC-SA 4.0 material; some other source terms are
incomplete. Preserve notices and review rights before any public redistribution.

The original [asset-manifest.json](asset-manifest.json) remains historical
validation evidence, including entries for local caches and optional payloads
omitted from Git. [PUBLICATION-EXCLUSIONS.json](PUBLICATION-EXCLUSIONS.json) and
[DEFERRED-ASSETS.json](DEFERRED-ASSETS.json) document those omissions.
[PUBLICATION-MANIFEST.json](PUBLICATION-MANIFEST.json)
is the hash inventory for the files actually published in this snapshot.

All physical hardware operation, flashing and deployment require a separate
request and validation. No GitHub publication changes the package's recorded
hardware-readiness limits.

## Lean Git publication

See [GITIGNORE-REVIEW.md](GITIGNORE-REVIEW.md) and
[DEFERRED-ASSETS.json](DEFERRED-ASSETS.json). Original CAD release archives,
unused vendor models, optional Rufus binaries and regenerable duplicate exports
stay on the source workstation but are not included in this Git snapshot.
The 57 native working SolidWorks files, baseline Blender scene, current KiCad
model projects, source board STEP files, recovered component geometry, policy
artifacts and known 17-stage verification inputs remain included.

Restore exact deferred files from the retained full package when required:

```sh
python tools/restore_deferred_assets.py --source /path/to/microduck-assets
```

For the original author CAD release ZIP alone, this explicit command downloads
the recorded release and verifies its SHA256:

```sh
python tools/restore_deferred_assets.py --download-original-cad
```

The release ZIP is CAD-only (41 parts and 16 assemblies), with no SolidWorks
program or installer. Fifteen expanded working CAD files differ from that
release; its original URL/hash are retained so both versions remain recoverable.
Some optional export/build tools need deferred inputs restored or regenerated;
the current 17-stage verification receipts retain their known file inputs.
