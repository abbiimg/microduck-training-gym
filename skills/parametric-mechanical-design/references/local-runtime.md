# Local CAD runtimes

Runtime registry: `C:/Users/abbii/Documents/Codex/tools/parametric-cad/runtime.json`.

- CadQuery Python: `C:/Users/abbii/Documents/Codex/tools/parametric-cad/cadquery/Scripts/python.exe`
- build123d Python: `C:/Users/abbii/Documents/Codex/tools/parametric-cad/build123d/Scripts/python.exe`

Call executables by absolute path; activation is optional. PowerShell example:

```powershell
& 'C:/Users/abbii/Documents/Codex/tools/parametric-cad/cadquery/Scripts/python.exe' '<project>/generator.py' --params '<project>/parameters.json'
```

Use the build123d executable for build123d scripts. The released engines currently require different OpenCascade distributions; keep them isolated, including when updating. A successful import alone is insufficient: regenerate a model and check native validity, exports, body counts and dimensions. Consult the runtime registry and per-environment requirements.lock.txt for the actual installation versions. Do not claim untested features based on package installation.

The installed SolidWorks and Blender MCP servers stay in their existing environments. CAD generation executes locally through the selected Python runtime and exchanges files with those apps; these libraries do not require adding another MCP server.
