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
