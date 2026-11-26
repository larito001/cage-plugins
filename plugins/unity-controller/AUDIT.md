# Historical read-only review for 0.3.0 (2026-11-25)

For the current 0.6.0 project-edit policy, see [Allowed operations](view/index.html).

Reviewed installed MCP for Unity 10.3.0, not tool readOnlyHint labels alone.

## Added

ManageScript.validate reads the existing file; basic/standard parse and inspect syntax. It does not use create/update directory creation, Emit, or execution.
ManageScene.ValidateScene mutates only when autoRepair is true. Both spelling variants are guarded, and auto_repair=false is always forwarded.
PhysicsValidationOps builds warning lists from component state; it does not repair objects or step physics.
FrameTimingOps captures transient measurement data only. FrameDebuggerOps.GetEvents reads existing events; Enable/Disable methods remain blocked.
The three graphics resources delegate to GetStats, ListFeatures and ListVolumes. Tool-group/custom-tool resources enumerate definitions without invoking tools.

## Still excluded

- Screenshot/UI capture: writes image files; rendering can alter temporary rendering state.
- Profiler counter collection: starts recorders and queues a player-loop update; conservative exclusion.
- Test enumeration/run: test discovery can invoke project test-data providers; not treated as purely declarative reading.
- Raw batches/custom execution/menu/C#: cannot establish a read-only boundary; use the local validated batch instead.
- Prefab URI templates/arbitrary paths: not added; existing get_info/get_hierarchy tools remain available.
- Normal upstream logging/caches and user-defined callbacks are outside this operation filter; no OS-level zero-write guarantee.

## Source fingerprints

- `Tools/ManageScript.cs` SHA-256 `153a80b6b67679234db810ae688533e9e5d530681eaa7a53d65bf7b8e2fe864f`
- `Tools/ManageScene.cs` SHA-256 `ffb881138efacb10892de864973e2c11de124ee06ce61dcfce29ae863efa6b18`
- `Tools/Physics/PhysicsValidationOps.cs` SHA-256 `3943c5e39c1acdba97f3a04b2fa6565066fd921adb212d55fd6af2b6e8ea8cca`
- `Tools/Profiler/Operations/FrameTimingOps.cs` SHA-256 `68d764db810745f1bde5ad07b7616f47003a00facf2f899470cb59d76ca10add`
- `Tools/Profiler/Operations/FrameDebuggerOps.cs` SHA-256 `a16f7e60166a8749190390dcb07d7659942237fb7bc1135c089a5bc2a8b39df2`
- `Resources/Scene/VolumesResource.cs` SHA-256 `c8b2988aacbf3204ce5892bff6ca5b91ffa49536bf3421859c8c8ed5d0cbb316`
- `Resources/Scene/RenderingStatsResource.cs` SHA-256 `c04a24de2fcfeb8291b70f21148318bdc1d5197ab3e4f73273a004362ed250bc`
- `Resources/Scene/RendererFeaturesResource.cs` SHA-256 `cee359531db503e4a76dbabbfce27d6d1f3e9e7272b94482818b6427583fdf40`
