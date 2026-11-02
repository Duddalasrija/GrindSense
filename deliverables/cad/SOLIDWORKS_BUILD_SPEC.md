# GrindSense conceptual SOLIDWORKS build specification

**Purpose:** produce a concept assembly for the Round 2 progress video. This is not a production design, manufacturing drawing, safety analysis, or verified fit study. All dimensions below are starting assumptions for a visual model only.

## Suggested top-level envelope

- Base housing: about 170 mm diameter × 205 mm tall.
- Jar body: about 118 mm outside diameter × 155 mm tall, with a small taper toward the base.
- Lid: about 124 mm diameter × 22 mm tall.
- Blade hub: about 18 mm diameter × 22 mm tall; four simple blades around the hub.
- Suggested overall assembled height: about 380 mm. Keep all dimensions visibly marked **ILLUSTRATIVE**.

## Native part documents

1. **MotorHousing.SLDPRT** - rounded cylindrical lower shell, shallow top shoulder, top drive-coupler placeholder, front control panel. Use a simple revolved/extruded body and fillets; keep the underside closed for this visual concept.
2. **MixerJar.SLDPRT** - tapered cup body, bottom collar, small handle. A thin-wall shell is optional; prioritize a clean silhouette over manufacturing detail.
3. **BladeAssembly.SLDPRT** - central hub plus four broad, rounded blades at two heights. This is a visual placeholder; do not use it for fabrication.
4. **Lid.SLDPRT** - shallow lid disc, central fill-cap boss, and a short alignment skirt.

## Assembly and presentation

- **GrindSense_Concept.SLDASM** - mate the jar collar to the housing top, place the blade hub on the jar axis, and seat the lid on the jar rim.
- Use a named exploded configuration separating lid, jar, blade assembly, and housing along the vertical axis.
- Save one shaded isometric screenshot and one exploded screenshot with a neutral background.
- Add a note on every exported view: **CONCEPTUAL ONLY - ILLUSTRATIVE DIMENSIONS - NOT FOR MANUFACTURE**.

## Proposed locations to label

- **Current sensing:** proposed in the motor electrical path inside the base, shown only as a callout; no wiring detail required for the concept render.
- **Temperature:** proposed near the motor stator inside the housing.
- **Vibration:** proposed on the motor mount or rigid inner housing.
- **Acoustic pickup:** proposed on an inner wall of the housing, isolated from direct blade contact.
- **Jar presence:** proposed at the jar-to-base seat.
- **Lid lock:** proposed at the lid/jar engagement point.
- **Attachment presence:** proposed at the drive interface.

Use dotted callout leaders and label all locations **PROPOSED SENSOR / INTERLOCK**. None of these are connected to the current software simulation.

## CAD completion gate

- [ ] Four native `.SLDPRT` documents saved and reopen successfully.
- [ ] Assembly `.SLDASM` saved and components visibly positioned.
- [ ] Exploded configuration saved and readable.
- [ ] Sensor/interlock callouts included and marked proposed.
- [ ] Two screenshots exported from the actual SOLIDWORKS model.
- [ ] Dimensions and visual proportions reviewed by the team before they are described as intended design dimensions.
