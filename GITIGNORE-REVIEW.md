# Git publication size review

Prepared on 2026-11-01. Git CLI 2.56.0.windows.4 ARM64 and Git LFS 3.8.1 are
installed as a normal Windows installation; Git is on the machine PATH.

The previous tracked payload was 2,324,857,967 bytes. This policy
omits 296 optional/generated files totalling 917,703,102 bytes
(917.7 MB), leaving approximately
1.407 GB before new documentation.

The original SolidWorks release ZIP contains only 41 robot part files and
16 assemblies. It includes no SolidWorks program or installer. Forty-two
expanded members match the archive CRC/size; 15 differ. The original archive
is retained locally and recoverable through its recorded URL and SHA256.

The ignore rules cover the optional CAD release archive, Rufus executable/source
archive, generated reconstruction previews, duplicate robot mesh conversions,
duplicate HAT STEP exports, a large generated MuJoCo scene dump, compiled firmware
test outputs, and unused vendor 3D models. All notices and the five custom models
used by the current HAT are retained. Native working CAD and all known inputs to
the existing 17-stage verification suite remain included.

No local payload was deleted. DEFERRED-ASSETS.json records exact paths/hashes
and restoration notes. The full package under outputs/microduck-assets remains
unchanged. The last commit was undone with a mixed reset; its Git history was
saved outside this repository in a bundle. Bulky data was already in the initial
unpublished commit, so the lean publication must use a new root commit; merely
adding .gitignore or a later deletion would still upload the older objects.

Any Git LFS objects already accepted by GitHub during the interrupted attempt
are not purged by this local cleanup. No remote history is force-pushed.
