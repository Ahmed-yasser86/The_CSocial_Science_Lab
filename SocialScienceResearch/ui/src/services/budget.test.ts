import { describe, expect, it } from "vitest";
import {
  formatInterval,
  formatRatePerSecond,
} from "@/services/budget";

describe("budget formatting helpers", () => {
  it("formats rate as req/s and handles a zero interval", () => {
    expect(formatRatePerSecond(0.5)).toBe("2.00 req/s");
    expect(formatRatePerSecond(0)).toBe("—");
    expect(formatRatePerSecond(0.1)).toBe("10.00 req/s");
  });

  it("formats interval with sensible precision and handles zero", () => {
    expect(formatInterval(0.5)).toBe("0.50s");
    expect(formatInterval(2)).toBe("2.0s");
    expect(formatInterval(0)).toBe("—");
  });
});
