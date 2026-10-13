# RE4R Face Integration 0.70.6 — derivative prerelease

Fork of Dimcirui RE Mesh Editor BlendShape 0.70.5, preserving NSA Cloud, Ridog8 and Dimcirui credits and GPLv3. Changes by funnyguyz, 2026-10-13. Not an official upstream 0.70.6 release.

Adds opt-in nine zero-displacement RE4 mouth receivers and packed/no-recalc exports preserving final base custom normals. Both switches default off; NO mode ignores them. Includes import support for float16/recalc and packed/no-recalc RE4 layouts. Does not generate toon normals, rebind weights or delete fins. A model-specific ShapeKey System profile and mouth9 runtime adapter are required.

Public synthetic tests pass all four modes, byte-identical default export against 0.70.5, batch persistence, NO mode, reimport/reexport, base-normal bytes and nonzero-name conflict rejection. The ZIP is checked byte-for-byte against the tagged source. Bundled libraries are unchanged and were not executed.

Historical real-model evidence: four 85/94-channel combinations and native four-LOD sample passed offline checks. User accepted the earlier standalone 85-channel normal experiment. The new integrated 94-channel receiver/normal combination still awaits separate in-game feedback; this is a prerelease. No game or private model assets are included.

Install the plugin ZIP from Assets in Blender 4.3.2 after disabling the other RE Mesh Editor instance. Keep upstream automatic update disabled; obtain this derivative manually from this fork. See README for the nine-signal contract, model preparation, portable build and tests. Third-party notices remain supplied unchanged; original README is retained as README_UPSTREAM.md.
