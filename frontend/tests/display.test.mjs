import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/display.ts", import.meta.url), "utf8");
const javascript = ts.transpile(source, { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 });
const helpers = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`);

test("smoothness score range stays ordered at the lower bound", () => {
  assert.equal(helpers.textureScoreRange("smooth", 0), "0–3 / 100");
});

test("smoothness score range stays centered for the midpoint", () => {
  assert.equal(helpers.textureScoreRange("smooth", 50), "47–53 / 100");
});

test("smoothness score range preserves a typical higher value", () => {
  assert.equal(helpers.textureScoreRange("smooth", 92), "89–95 / 100");
});

test("smoothness score range stays within its upper bound", () => {
  assert.equal(helpers.textureScoreRange("smooth", 100), "97–100 / 100");
});

test("fine texture range matches the simulated fine completion target", () => {
  assert.equal(helpers.textureScoreRange("fine", 92), "72–80 / 100");
});

test("backend naive timestamps are parsed as UTC, not local time", () => {
  assert.equal(helpers.parseBackendTimestamp("2026-06-01T12:00:00"), Date.UTC(2026, 5, 1, 12));
});

test("explicit timestamp offsets are preserved", () => {
  assert.equal(helpers.parseBackendTimestamp("2026-06-01T17:30:00+05:30"), Date.UTC(2026, 5, 1, 12));
});

test("negative timestamp offsets are preserved", () => {
  assert.equal(helpers.parseBackendTimestamp("2026-06-01T08:00:00-04:00"), Date.UTC(2026, 5, 1, 12));
});

test("elapsed time and display use the UTC instant accurately", () => {
  const start = "2026-06-01T12:00:00";
  const now = Date.UTC(2026, 5, 1, 12, 1, 12);
  assert.equal(helpers.elapsedSeconds(start, now), 72);
  assert.equal(helpers.formatDuration(helpers.elapsedSeconds(start, now)), "01:12");
});

test("interlock updates preserve the complete simulated state payload", () => {
  const state = { jar_present: true, lid_locked: true, attachment_present: true };
  assert.deepEqual(helpers.updateInterlockState(state, "lid_locked", false), {
    jar_present: true, lid_locked: false, attachment_present: true,
  });
  assert.deepEqual(helpers.unsafeInterlockLabels({ ...state, jar_present: false, attachment_present: false }), [
    "Jar present", "Attachment present",
  ]);
  assert.deepEqual(helpers.unsafeInterlockLabels(state), []);
});

test("adaptive pulse patterns are returned only for valid adaptive event values", () => {
  assert.equal(helpers.adaptivePulsePattern("adaptive", { pulse_pattern: "2s on / 2s rest" }), "2s on / 2s rest");
  assert.equal(helpers.adaptivePulsePattern("adaptive", null), null);
  assert.equal(helpers.adaptivePulsePattern("adaptive", {}), null);
  assert.equal(helpers.adaptivePulsePattern("adaptive", { pulse_pattern: null }), null);
  assert.equal(helpers.adaptivePulsePattern("adaptive", { pulse_pattern: 42 }), null);
  assert.equal(helpers.adaptivePulsePattern("info", { pulse_pattern: "ignored" }), null);
});

test("event severity safely handles absent and invalid backend values", () => {
  assert.equal(helpers.safeEventSeverity("critical"), "critical");
  assert.equal(helpers.safeEventSeverity("future-level"), "future-level");
  assert.equal(helpers.safeEventSeverity(null), "Info");
  assert.equal(helpers.safeEventSeverity(42), "Info");
  assert.equal(helpers.safeEventSeverity("  "), "Info");
});
