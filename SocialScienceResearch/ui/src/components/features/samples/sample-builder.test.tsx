import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test-utils";
import { SampleBuilder } from "@/components/features/samples/sample-builder";

vi.mock("@/services/samples", () => ({
  useCreateSample: vi.fn(),
}));

import { useCreateSample } from "@/services/samples";

const mockUseCreateSample = vi.mocked(useCreateSample);

const TEST_TIMEOUT = 20000;

async function openAttributePicker(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByText("Add attribute…"));
}

async function pickAttribute(
  user: ReturnType<typeof userEvent.setup>,
  label: string,
) {
  await openAttributePicker(user);
  await user.click(await screen.findByText(label));
  await user.click(screen.getByRole("button", { name: "Add" }));
}

describe("SampleBuilder", () => {
  beforeEach(() => {
    mockUseCreateSample.mockReset();
    mockUseCreateSample.mockReturnValue({ mutate: vi.fn(), isPending: false } as never);
  });

  it(
    "submits criteria_json built from predefined attributes",
    async () => {
      const user = userEvent.setup();
      const mutate = vi.fn();
      mockUseCreateSample.mockReturnValue({ mutate, isPending: false } as never);

      renderWithProviders(<SampleBuilder open onOpenChange={() => {}} />);
      await screen.findByRole("dialog");

      await user.type(
        screen.getByRole("spinbutton", { name: "Population size" }),
        "1000",
      );

      await pickAttribute(user, "Video ID");
      await user.type(
        screen.getByRole("textbox", { name: "video_id value" }),
        "dQw4w9WgXcQ",
      );

      await pickAttribute(user, "Min likes");
      await user.type(
        screen.getByRole("spinbutton", { name: "min_likes value" }),
        "100",
      );

      await user.click(screen.getByRole("button", { name: /Save sample/ }));

      await waitFor(() => expect(mutate).toHaveBeenCalledTimes(1));
      const input = mutate.mock.calls[0][0];
      expect(input.criteria_json).toEqual({ video_id: "dQw4w9WgXcQ", min_likes: 100 });
      expect(input.member_ids).toEqual([]);
      expect(input.population_size).toBe(1000);
    },
    TEST_TIMEOUT,
  );

  it(
    "drops empty attribute values on submit",
    async () => {
      const user = userEvent.setup();
      const mutate = vi.fn();
      mockUseCreateSample.mockReturnValue({ mutate, isPending: false } as never);

      renderWithProviders(<SampleBuilder open onOpenChange={() => {}} />);
      await screen.findByRole("dialog");

      await user.type(
        screen.getByRole("spinbutton", { name: "Population size" }),
        "500",
      );

      await pickAttribute(user, "Channel handle");

      await user.click(screen.getByRole("button", { name: /Save sample/ }));

      await waitFor(() => expect(mutate).toHaveBeenCalledTimes(1));
      const input = mutate.mock.calls[0][0];
      expect(input.criteria_json).toBeUndefined();
    },
    TEST_TIMEOUT,
  );

  it(
    "coerces dates, booleans and select values correctly",
    async () => {
      const user = userEvent.setup();
      const mutate = vi.fn();
      mockUseCreateSample.mockReturnValue({ mutate, isPending: false } as never);

      renderWithProviders(<SampleBuilder open onOpenChange={() => {}} />);
      await screen.findByRole("dialog");

      await user.type(
        screen.getByRole("spinbutton", { name: "Population size" }),
        "1000",
      );

      await pickAttribute(user, "Date from");
      await user.type(screen.getByLabelText("date_from value"), "2024-01-01");

      await pickAttribute(user, "Live only");
      await user.click(
        screen.getByRole("checkbox", { name: "Live only (live_only)" }),
      );

      await pickAttribute(user, "Sampling strategy");
      await user.click(screen.getByText("Choose…"));
      await user.click(await screen.findByText("Stratified"));

      await user.click(screen.getByRole("button", { name: /Save sample/ }));

      await waitFor(() => expect(mutate).toHaveBeenCalledTimes(1));
      const input = mutate.mock.calls[0][0];
      expect(input.criteria_json).toEqual({
        date_from: "2024-01-01",
        live_only: true,
        sampling_strategy: "stratified",
      });
    },
    TEST_TIMEOUT,
  );

  it(
    "toasts an error for invalid raw JSON and skips the mutation",
    async () => {
      const user = userEvent.setup();
      const mutate = vi.fn();
      mockUseCreateSample.mockReturnValue({ mutate, isPending: false } as never);

      renderWithProviders(<SampleBuilder open onOpenChange={() => {}} />);
      await screen.findByRole("dialog");

      await user.type(
        screen.getByRole("spinbutton", { name: "Population size" }),
        "500",
      );
      await user.click(
        screen.getByRole("checkbox", { name: "Use raw JSON for criteria" }),
      );
      fireEvent.change(screen.getByLabelText("Raw criteria JSON"), {
        target: { value: "{not valid json" },
      });
      await user.click(screen.getByRole("button", { name: /Save sample/ }));

      await waitFor(() => {
        expect(screen.getByText("Invalid criteria JSON")).toBeInTheDocument();
      });
      expect(mutate).not.toHaveBeenCalled();
    },
    TEST_TIMEOUT,
  );
});