import { describe, expect, it } from "vitest";
import { extractConflictEvaluationId, extractErrorMessage } from "./client";

function axiosError(status: number, detail: unknown): unknown {
  return { isAxiosError: true, response: { status, data: { detail } } };
}

describe("extractErrorMessage", () => {
  it("returns string detail as-is", () => {
    expect(extractErrorMessage(axiosError(400, "خطای اعتبارسنجی"))).toBe("خطای اعتبارسنجی");
  });

  it("returns message from structured detail (e.g. 409 duplicate evaluation)", () => {
    expect(
      extractErrorMessage(axiosError(409, { message: "پرونده باز وجود دارد", evaluation_id: 7 }))
    ).toBe("پرونده باز وجود دارد");
  });

  it("falls back to generic message for unknown shapes", () => {
    expect(extractErrorMessage(new Error("boom"))).toBe("خطایی غیرمنتظره رخ داد");
    expect(extractErrorMessage(axiosError(422, [{ loc: ["body"], msg: "x" }]))).toBe(
      "خطایی غیرمنتظره رخ داد"
    );
    expect(extractErrorMessage(undefined)).toBe("خطایی غیرمنتظره رخ داد");
  });
});

describe("extractConflictEvaluationId", () => {
  it("returns the open evaluation id from a 409", () => {
    expect(
      extractConflictEvaluationId(axiosError(409, { message: "x", evaluation_id: 42 }))
    ).toBe(42);
  });

  it("returns null for non-409 or missing id", () => {
    expect(extractConflictEvaluationId(axiosError(400, { evaluation_id: 42 }))).toBeNull();
    expect(extractConflictEvaluationId(axiosError(409, { message: "x" }))).toBeNull();
    expect(extractConflictEvaluationId(new Error("boom"))).toBeNull();
  });
});
