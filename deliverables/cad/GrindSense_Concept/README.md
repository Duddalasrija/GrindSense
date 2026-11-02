# GrindSense concept CAD package

This package is a rapid, concept-level mixer-grinder visual prototype for Round 2.

## Main files

- `GrindSense_Concept_Model.SLDPRT` — opened and saved by SOLIDWORKS 2026 as an imported graphic mesh part. It contains the assembled concept as one visual body document.
- `GrindSense_Assembled_Concept.stl` — assembled concept mesh for viewing/importing.
- `GrindSense_Exploded_Concept.stl` — separated mesh layout for exploded-view illustration.
- `MotorHousing.stl`, `MixerJar.stl`, `BladeAssembly.stl`, `JarLid.stl` — separate concept component meshes.
- `ProposedSensors.stl` — proposed sensor/interlock markers.
- `GrindSense_Concept_Annotated.svg` — annotated presentation illustration and sensor placements.
- `MotorHousing.SLDPRT`, `MixerJar.SLDPRT` — imported graphic-body part documents saved from SOLIDWORKS.
- `GrindSense_Concept_Assembly.SLDASM` — saved assembly document containing the overall concept model as one fixed component.
- `build_concept.py` — repeatable generator for the concept STL geometry and annotated SVG.

All dimensions are illustrative millimetres and have not been checked against a real appliance, motor, manufacturing process, or safety standard. Sensor markers are proposals only. This is not a functional or validated physical prototype.

## SolidWorks limitation

The STL imports are graphic mesh bodies, not feature-based editable SolidWorks solids. The `.SLDASM` is a single-component visual assembly, not a multi-part assembly with mates. Blade, lid, and proposed sensors are STL only and have not been inserted as separate assembly components. The mesh and SVG provide a quick visual prototype; rebuild the geometry as feature-based parts and create a mated assembly before treating it as a production CAD design.

## Open and view in SOLIDWORKS

1. Choose **File → Open** and browse to this folder.
2. Select `GrindSense_Concept_Assembly.SLDASM` and choose **Open**.
3. Press **F** for Zoom to Fit. Drag with the middle mouse button to rotate and use the mouse wheel to zoom.
4. Open `MotorHousing.SLDPRT` or `MixerJar.SLDPRT` separately to inspect those imported concept meshes.
