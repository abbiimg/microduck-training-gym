# Tested RTX Spark baseline

Verified October 26, 2026. Recheck current state before reuse.

## Local installation

- Windows 11 ARM64, ASUS ProArt P14 H7407BA; RTX Spark N1X; driver 617.42.
- Existing WSL2 distribution: `NVIDIA-Workbench`, Linux aarch64.
- Isaac Lab: `/home/workbench/robotics/IsaacLab`.
- uv: `/home/workbench/.local/bin/uv`; Python 3.12; PyTorch `2.11.0+cu130`.
- Repository revision: `dae8b7991461931e977b8bbef258ff98eba6237d` on `main` at setup time.
- Native Windows Isaac Sim: `C:\isaacsim`, version 6.2.0 Windows x86_64 under ARM emulation.
- Original setup artifacts: the originating chat's `outputs` folder under the user's Documents/Codex workspace. Discover its current location rather than hardcoding a username.

Inside the Linux checkout:

```bash
/home/workbench/.local/bin/uv run --no-sync isaaclab list_envs --keyword MicroDuck --show_presets

# Bounded installation test; repeat with Rough in place of Flat as needed.
/home/workbench/.local/bin/uv run --no-sync isaaclab train \
  --rl_library rsl_rl --task IsaacContrib-Velocity-Flat-MicroDuck \
  --num_envs 32 --max_iterations 3 presets=backlash

# Published trained policy, not the new smoke-test checkpoint.
/home/workbench/.local/bin/uv run --no-sync isaaclab play \
  --rl_library rsl_rl --task IsaacContrib-Velocity-Flat-MicroDuck \
  --checkpoint pretrained --num_envs 4 --viz newton_gl --real-time presets=backlash

# Bounded visual evidence; install the repository's video extra if missing.
/home/workbench/.local/bin/uv run --no-sync isaaclab play \
  --rl_library rsl_rl --task IsaacContrib-Velocity-Flat-MicroDuck \
  --checkpoint pretrained --num_envs 4 --viz newton_gl \
  --video --video_length 150 presets=backlash
```

From PowerShell, wrap an entire command in `wsl -d NVIDIA-Workbench -- bash -lc '...'`. Avoid inline shell variables across PowerShell/Bash quoting layers; use a script for multiline logic. Check current backend-specific help, e.g. `isaaclab play --rl_library rsl_rl --help`. This revision rejected `--headless`; training ran without a viewer by default.

Training logs/checkpoints are under `logs/rsl_rl/microduck_velocity_{flat,rough}_backlash`. Playback of a published checkpoint stores exports/video beside its downloaded checkpoint under `.pretrained_checkpoints`, not necessarily in `logs`.

The supplied full-training launchers requested 128 environments with default training duration; only the 32-environment, three-iteration runs were tested. Use `--checkpoint latest` when deliberately inspecting the user's own checkpoint.

## Results and limits

Both training tasks completed three PPO iterations, saved checkpoints, and reported no NaN-state terminations. The flat checkpoint reopened with actor, critic, optimizer state, and iteration 2. Published flat/backlash playback recorded 150 frames at 1920×1080 (3 seconds). Its self-contained ONNX export validated with input `[1,61]` and output `[1,14]`. These are installation checks, not policy-quality benchmarks.

WSLg lacked CUDA/OpenGL buffer interoperability. Warp emitted CUDA error 304, then successfully fell back to memory copies and produced the clip. This can slow rendering; it did not prevent GPU training. Do not call this a successful playback unless actual frames or other meaningful runtime evidence are available.

Windows' checker recognized the GPU/driver but rejected the ARM CPU and its reported 8 GB GPU budget against a 10 GB minimum. Linux CUDA exposed about 102 GiB. Do not generalize either report to all runtime memory availability.

The user explicitly accepted the EULA and requested a Windows launch despite that checker result in the setup chat. A native app reached startup completion. NVIDIA's empty-startup viewport callback test failed, but the concrete scene helper passed: 120 simulation steps, cube settled at z≈0.10 m, valid 640×480 camera image, exit 0. Native Windows MicroDuck policy integration was not separately tested. Initial extension/shader startup took minutes; cached startup was much faster.

## Demonstrated download recovery

NVIDIA CDN transfers intermittently stalled from Windows and WSL. Parallel range requests completed the 10.5 GB standalone archive; the assembled file matched NVIDIA's checksum. If reusing that technique, validate response ranges, part sizes, assembly order, and final checksum; preserve partial files on failure.

Some dependency wheels were fetched from PyPI only after comparing their SHA-256 hashes with the repository's original lockfile. The original lockfile was restored after installation; a dated mirror copy remained at `/home/workbench/robotics/uv.lock.pypi-mirror`. Revalidate before reusing it.

A temporary reachable CDN address and WSL MTU adjustment helped downloads during setup. Both were restored afterward. Do not reuse the dated IP, edit hosts, or change MTU by default. Diagnose current DNS/connectivity, prefer verified mirrors/retries, and scope any network workaround to the demonstrated problem.
