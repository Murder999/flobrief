import { expect, test } from "@playwright/test";

import { ApiError, formatApiErrorMessage } from "../lib/api-client";

test.describe("API error formatting", () => {
  test("keeps ordinary string messages intact", () => {
    expect(formatApiErrorMessage("Gönderim başarısız.", 400)).toBe(
      "Gönderim başarısız."
    );
  });

  test("extracts messages from nested error objects", () => {
    expect(
      formatApiErrorMessage(
        { detail: { code: "invalid_state", message: "Brief onaya gönderilemez." } },
        409
      )
    ).toBe("Brief onaya gönderilemez.");
  });

  test("formats FastAPI validation errors with their field locations", () => {
    expect(
      formatApiErrorMessage(
        [
          { loc: ["body", "email"], msg: "Field required", type: "missing" },
          {
            loc: ["body", "items", 0, "name"],
            msg: "String should have at least 1 character",
            type: "string_too_short",
          },
        ],
        422
      )
    ).toBe(
      "email: Field required; items.0.name: String should have at least 1 character"
    );
  });

  test("never exposes an object coercion as the user-facing message", () => {
    const detail = { unexpected: { nested: true } };
    const error = new ApiError(422, detail, detail);

    expect(error.message).toBe("Check the highlighted fields and try again.");
    expect(error.message).not.toContain("[object Object]");
    expect(error.detail).toBe(detail);
  });
});
