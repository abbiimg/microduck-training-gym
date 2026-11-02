---
name: microduck-training-gym
description: Set up and validate MicroDuck training with Isaac Lab, Newton, and RSL-RL, or iterate robot size, limbs, and mechanical design through SolidWorks and Blender into revised simulation and retraining. Supports RTX Spark Windows ARM64 through WSL2; physical hardware operation requires a separate explicit request.
---

# MicroDuck training gym

Reuse an existing working environment before installing another copy. For this user's RTX Spark installation, read [the tested baseline](references/rtx-spark.md) for paths, commands, and limitations. Treat that baseline as dated evidence; inspect the current machine before modifying it.

For local robot meshes, Blender files, SolidWorks exchange geometry, KiCad sources, or asset-completeness questions, read [the local asset inventory](references/local-assets.md) first. It identifies the prepared package and important missing original CAD/electronics sources.

For PCB candidate verification, electrical simulation, or controller/firmware mocks, read [the PCB testing reference](references/pcb-testing.md). It records the isolated local tools and the distinction between tested firmware logic, component models, exact board coverage, and physical acceptance.

## Mechanical design and retraining

For resizing, adding/removing limbs, changing mass distribution, or mechanical co-design, read [the design iteration workflow](references/design-iteration.md). Use this skill to coordinate the robot description, simulation task, and policy; use the companion `blender-solidworks-transfer` skill for verified geometry exchange, and `parametric-mechanical-design` when reproducible CAD generation is useful. Resolve those siblings from the personal skills directory and read their SKILL.md before applying them. Use `appliance-ecad-mcad` only if the change includes PCB/electronics fit.

Keep a revisioned mechanical/robot contract linking editable CAD, per-link geometry, articulated description, actuator assumptions, task configuration, and checkpoints. CAD mates, Blender rigs, STL files, and a rendered robot do not by themselves establish a dynamically valid robot. Preserve the working baseline; create separate variant assets and task IDs. A new morphology requires validation and potentially a new policy interface, not just an asset-path substitution.

## Choose and inspect the runtime

Distinguish **RTX Spark on Windows ARM64** from **DGX Spark on Linux ARM64**. Do not assume x86 Windows packages support native ARM training, or that a native simulator installation is necessary for Newton-based training.

Inspect OS/CPU architecture, GPU/driver, available storage, installed Isaac Lab/Sim, and existing WSL distributions. On Windows, inspect `wsl --list --verbose` and test CUDA inside the selected distribution. Prefer the already tested WSL gym when available. Do not replace distributions or alter unrelated workloads.

When installing/upgrading, verify current official installation requirements, versions, download checksums, repository branches, and CLI help. The original tutorial's `develop` branch was absent during this setup; `main` contained MicroDuck. Avoid assuming that historical branch names or versions remain valid.

Sources:
- https://huggingface.co/blog/nvidia/microduck-isaac-lab-sim-to-real
- https://github.com/isaac-sim/IsaacLab
- https://developer.nvidia.com/blog/using-ai-agents-to-teach-robots-like-microduck-to-walk-in-simulation/
- https://docs.isaacsim.omniverse.nvidia.com/latest/installation/download.html

## Install or repair

For Linux/WSL, use the repository's uv-managed Python environment and its declared dependencies, including build tools when native wheels need compilation. Read repository instructions before editing source. Verify both MicroDuck task registrations before training.

On an already validated installation, use `uv run --no-sync` to avoid unexpectedly changing dependencies. Synchronize explicitly when repairing or adding required extras. Video recording needs the `video` extra. Do not silently change dependency versions to solve a download failure.

For a Windows standalone Isaac Sim installation, resolve the official archive and checksum, verify before extraction, preserve existing installations, and run post-install checks. A directory junction can replace the examples symlink when Windows lacks symlink privilege. Respect applicable license acknowledgment and installer requirements; skill use does not carry prior EULA agreement or permission to override failed checks to another machine or future task.

A compatibility-check failure and a successful concrete scene test are different findings. Report both. If the user authorizes a launch despite a failed check, a concrete cube/physics/camera test is available at `scripts/windows_scene_smoke.py`; run it using the installed Isaac Sim `python.bat`, with `--output-dir` pointing to the task's output folder. This helper launches a simulator and creates test artifacts. It is not a MicroDuck walking-policy test. Obtain the necessary authorization before invoking it.

## Verify observable behavior

Use a small bounded training test first (32 environments and 3 PPO iterations were sufficient here). Check:

1. CUDA tensor work succeeds on the intended GPU.
2. Both flat and rough MicroDuck tasks and backlash presets enumerate.
3. Each requested training task completes learning iterations and saves a checkpoint; inspect NaN-state metrics and errors.
4. Reopen the saved checkpoint and confirm actor/critic state and iteration data.
5. Load a selected policy for playback. Distinguish `pretrained` from `latest` and record which was used.
6. When visual verification is requested, record a bounded clip and inspect actual frames. Process startup alone does not prove rendering.
7. Validate an exported ONNX model. The tested policy interface was 61 observations and 14 actions; verify against current task configuration rather than imposing those dimensions on all future policies.

ONNX exports can reference a separate `.onnx.data` file. Copy the full export set or load the original with external weights and save a self-contained model using `onnx.save_model(..., save_as_external_data=False)`. Validate the delivered copy.

Short smoke tests prove installation, not learned walking quality or obstacle-course success. Describe new checkpoints accordingly. Full training should use the user-requested budget; do not start unbounded training merely to test installation.

## Troubleshoot and deliver

Use [the RTX Spark reference](references/rtx-spark.md) for demonstrated CDN, WSL rendering, and Windows-checker issues. Treat workarounds as conditional, reversible changes; retain logs and restore temporary network changes.

Provide launchers or exact commands tied to the verified installation, checkpoint locations, test results, and remaining limitations. Keep a working WSL gym distinct from native Windows simulator validation and from physical-robot readiness. Do not control hardware, purchase cloud compute, or imply a trained policy is safe to deploy without a separate request and validation.
