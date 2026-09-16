/**
 * Frontend smoke and utility unit tests for MIND-FLOW UI.
 *
 * Author: ChaChan26 <minhharry2006@gmail.com>
 * Copyright (c) 2026 ChaChan26. All rights reserved.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { getAuthHeaders } from "../app/hooks/useStaminaEngine";

describe("Frontend Auth Utilities", () => {
  beforeEach(() => {
    // Mock window.location
    delete (globalThis as any).window;
    (globalThis as any).window = {
      location: {
        search: "?token=test-secret-token",
      },
    };
  });

  it("should extract token from query parameters into X-MIND-FLOW-TOKEN header", () => {
    const headers = getAuthHeaders();
    expect(headers["X-MIND-FLOW-TOKEN"]).toBe("test-secret-token");
  });

  it("should merge with extra headers", () => {
    const headers = getAuthHeaders({ "Content-Type": "application/json" });
    expect(headers["Content-Type"]).toBe("application/json");
    expect(headers["X-MIND-FLOW-TOKEN"]).toBe("test-secret-token");
  });

  it("should handle empty query parameters gracefully", () => {
    (globalThis as any).window.location.search = "";
    const headers = getAuthHeaders();
    expect(headers["X-MIND-FLOW-TOKEN"]).toBeUndefined();
  });
});

