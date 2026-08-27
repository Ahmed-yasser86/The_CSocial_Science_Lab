import { test, expect } from "@playwright/test";

// N2 / WS7 — Lab family selector exposes the audience (commenter) network view.
// This smoke test only needs the frontend: with no collection run selected the
// audience view renders its "select a run" empty state without hitting the API.
test.describe("Audience network family (N2)", () => {
  test("family toggle switches the Lab to the audience network view", async ({
    page,
  }) => {
    await page.goto("/network/full");

    await expect(
      page.getByRole("heading", { name: "Full network analytics" }),
    ).toBeVisible();

    const audienceToggle = page.getByRole("button", {
      name: "Audience (commenters)",
    });
    await expect(audienceToggle).toBeVisible();

    await audienceToggle.click();

    await expect(
      page.getByText("Select a collection run"),
    ).toBeVisible();

    // Projection control is present once a run is scoped; here we only assert
    // the toggle wiring by switching back to the recommendation family.
    await page.getByRole("button", { name: "Recommendation" }).click();
    await expect(page.getByText("Network slice")).toBeVisible();
  });
});
