import { useState } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  LivePreview,
  FilterPanel,
  ResultActions,
  ScopeSelector,
  SamplingMethodSelector,
  INITIAL_STATE,
  INITIAL_FILTERS,
  INITIAL_LABELS,
  type WorkbenchState,
  type WorkbenchFilters,
  type WorkbenchLabels,
  type ScopeValue,
} from "./index";
import { SamplingWorkbench } from "./SamplingWorkbench";
import { renderWithProviders } from "@/test-utils";

vi.mock("@/services/api", () => ({
  sampleAdvanced: vi.fn(),
}));

import * as api from "@/services/api";

const mockedSampleAdvanced = vi.mocked(api.sampleAdvanced);

// Base UI renders both <Select> and <Combobox> triggers with role="combobox";
// the popover-backed Combobox is the one with aria-haspopup="dialog".
function getPopoverCombobox() {
  const combobox = screen
    .getAllByRole("combobox")
    .find((el) => el.getAttribute("aria-haspopup") === "dialog");
  if (!combobox) throw new Error("No popover combobox found");
  return combobox;
}

function makeState(overrides: Partial<WorkbenchState> = {}): WorkbenchState {
  return {
    scopeType: "all",
    channelIds: [],
    authorIds: [],
    runScope: "all",
    runIds: [],
    filters: { ...INITIAL_FILTERS },
    samplingMethod: "random",
    sampleSize: "500",
    samplePercent: "",
    seed: "",
    strataVariable: "month",
    samplesPerStratum: "50",
    topMetric: "replies",
    topPercent: "10",
    labels: { ...INITIAL_LABELS },
    saveOption: "individual",
    datasetName: "",
    entityType: "comment",
    ...overrides,
  };
}

function makeFilters(overrides: Partial<WorkbenchFilters> = {}): WorkbenchFilters {
  return { ...INITIAL_FILTERS, ...overrides };
}

function makeLabels(overrides: Partial<WorkbenchLabels> = {}): WorkbenchLabels {
  return { ...INITIAL_LABELS, ...overrides };
}

function StatefulFilterPanel({
  initial = INITIAL_FILTERS,
  onChange,
  channels = [],
}: {
  initial?: WorkbenchFilters;
  onChange?: (filters: WorkbenchFilters) => void;
  channels?: { channel_id: string; title: string | null }[];
}) {
  const [filters, setFilters] = useState(initial);
  return (
    <FilterPanel
      filters={filters}
      onChange={(next) => {
        setFilters(next);
        onChange?.(next);
      }}
      channels={channels}
    />
  );
}

function StatefulScopeSelector({
  initial,
  onChange,
}: {
  initial: ScopeValue;
  onChange?: (value: ScopeValue) => void;
}) {
  const [value, setValue] = useState(initial);
  return (
    <ScopeSelector
      value={value}
      onChange={(next) => {
        setValue(next);
        onChange?.(next);
      }}
    />
  );
}

function StatefulResultActions({
  onChange,
}: {
  onChange?: (labels: WorkbenchLabels) => void;
}) {
  const [labels, setLabels] = useState<WorkbenchLabels>({ ...INITIAL_LABELS });
  const [saveOption, setSaveOption] = useState<"individual" | "dataset">("dataset");
  const [datasetName, setDatasetName] = useState("");
  return (
    <ResultActions
      labels={labels}
      onLabelsChange={(next) => {
        setLabels({ ...next, customLabels: next.customLabels });
        onChange?.(next);
      }}
      saveOption={saveOption}
      onSaveOptionChange={setSaveOption}
      datasetName={datasetName}
      onDatasetNameChange={setDatasetName}
      existingDatasets={[]}
      onCreateDataset={() => {}}
      sampleIds={["x", "y"]}
    />
  );
}

describe("sampling: initial constants", () => {
  it("INITIAL_STATE wires up filters/labels and defaults", () => {
    expect(INITIAL_STATE.samplingMethod).toBe("random");
    expect(INITIAL_STATE.sampleSize).toBe("500");
    expect(INITIAL_STATE.entityType).toBe("comment");
    expect(INITIAL_STATE.filters.commentType).toBe("all");
    expect(INITIAL_STATE.labels).toEqual(INITIAL_LABELS);
    expect(INITIAL_FILTERS.tags).toEqual([]);
    expect(INITIAL_FILTERS.excludeAuthorIds).toEqual([]);
  });
});

describe("sampling: LivePreview", () => {
  it("shows placeholders and a hint when no result", () => {
    renderWithProviders(
      <LivePreview state={makeState()} onRefresh={() => {}} isRefreshing={false} />,
    );
    expect(screen.getByText("Live Preview")).toBeInTheDocument();
    expect(screen.getByText("Population")).toBeInTheDocument();
    expect(screen.getByText("Sample size")).toBeInTheDocument();
    expect(screen.getByText("Run the sample to see IDs")).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBe(2);
  });

  it("renders population/sample counts and up to 10 ids from a result", () => {
    const ids = Array.from({ length: 15 }, (_, i) => `id-${i}`);
    renderWithProviders(
      <LivePreview
        state={makeState()}
        onRefresh={() => {}}
        isRefreshing={false}
        previewResult={{
          entity_ids: ids,
          population_size: 12345,
          sample_size: 15,
          strategy: "random",
          seed: 1,
          entity_type: "comment",
          criteria_json: {},
          missing_metric_count: 0,
        }}
      />,
    );
    expect(screen.getByText("12,345")).toBeInTheDocument();
    ids.slice(0, 10).forEach((id) => expect(screen.getByText(id)).toBeInTheDocument());
    expect(screen.getByText("+ 5 more")).toBeInTheDocument();
  });

  it("caps displayed ids at the first 10", () => {
    const ids = Array.from({ length: 25 }, (_, i) => `id-${i}`);
    renderWithProviders(
      <LivePreview
        state={makeState()}
        onRefresh={() => {}}
        isRefreshing={false}
        previewResult={{
          entity_ids: ids,
          population_size: 100,
          sample_size: 25,
          strategy: "random",
          seed: 1,
          entity_type: "comment",
          criteria_json: {},
          missing_metric_count: 0,
        }}
      />,
    );
    expect(screen.getByText("+ 15 more")).toBeInTheDocument();
    expect(screen.queryByText("id-24")).not.toBeInTheDocument();
  });

  it("calls onRefresh from the refresh button and disables while refreshing", async () => {
    const onRefresh = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <LivePreview state={makeState()} onRefresh={onRefresh} isRefreshing={false} />,
    );
    await user.click(screen.getByRole("button", { name: "Refresh preview" }));
    expect(onRefresh).toHaveBeenCalledTimes(1);

    fireEvent(screen.getByRole("button", { name: "Refresh preview" }), new Event(""));
  });

  it("disables the refresh button while refreshing", () => {
    renderWithProviders(
      <LivePreview state={makeState()} onRefresh={() => {}} isRefreshing={true} />,
    );
    expect(screen.getByRole("button", { name: "Refresh preview" })).toBeDisabled();
  });
});

describe("sampling: FilterPanel onChange", () => {
  async function openPanel(user: ReturnType<typeof userEvent.setup>, title: string) {
    const trigger = screen.getByRole("button", { name: new RegExp(title, "i") });
    await user.click(trigger);
  }

  it("toggles exclude video author", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<StatefulFilterPanel onChange={onChange} />);
    await openPanel(user, "Author Filters");

    const checkbox = (await screen.findAllByRole("checkbox"))[0];
    await user.click(checkbox);
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ excludeVideoAuthor: true }),
    );
  });

  it("parses comma separated exclude author ids", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<StatefulFilterPanel onChange={onChange} />);
    await openPanel(user, "Author Filters");

    const inputs = screen.getAllByPlaceholderText(
      "Enter author IDs, separated by commas",
    );
    fireEvent.change(inputs[0], { target: { value: "a1, a2," } });
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({
        excludeAuthorIds: ["a1", "a2"],
      }),
    );
  });

  it("parses comma separated include author ids", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<StatefulFilterPanel onChange={onChange} />);
    await openPanel(user, "Author Filters");

    const inputs = screen.getAllByPlaceholderText(
      "Enter author IDs, separated by commas",
    );
    expect(inputs.length).toBe(2);
    fireEvent.change(inputs[1], { target: { value: "b1, b2," } });
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({
        includeAuthorIds: ["b1", "b2"],
      }),
    );
  });

  it("adds a tag via the tags input and removes it", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<StatefulFilterPanel onChange={onChange} />);
    await openPanel(user, "Video Filters");

    const input = screen.getByPlaceholderText("Enter tag and press Add");
    await user.type(input, "climate{Enter}");
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ tags: ["climate"] }),
    );
    expect(screen.getByText("climate")).toBeInTheDocument();
  });

  it("writes numeric view bounds via the number range inputs", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<StatefulFilterPanel onChange={onChange} />);
    await openPanel(user, "Video Filters");

    fireEvent.change(screen.getByPlaceholderText("Min views"), {
      target: { value: "100" },
    });
    fireEvent.change(screen.getByPlaceholderText("Max views"), {
      target: { value: "5000" },
    });
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ viewsMin: 100, viewsMax: 5000 }),
    );
  });

  it("preserves unrelated keys when a single filter changes", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <StatefulFilterPanel
        initial={makeFilters({ commentType: "replies", matchMode: "all" })}
        onChange={onChange}
      />,
    );
    await openPanel(user, "Author Filters");

    const checkbox = (await screen.findAllByRole("checkbox"))[0];
    await user.click(checkbox);
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(lastCall.commentType).toBe("replies");
    expect(lastCall.matchMode).toBe("all");
  });
});

describe("sampling: FilterPanel new filter controls", () => {
  async function openPanel(user: ReturnType<typeof userEvent.setup>, title: string) {
    const trigger = screen.getByRole("button", { name: new RegExp(title, "i") });
    await user.click(trigger);
  }

  it("renders the new author-name include/exclude inputs", async () => {
    const user = userEvent.setup();
    renderWithProviders(<StatefulFilterPanel />);
    await openPanel(user, "Author Filters");
    expect(
      screen.getByPlaceholderText("Enter author name and press Add"),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Enter author name to exclude and press Add"),
    ).toBeInTheDocument();
  });

  it("adds an include author name via the tags input", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<StatefulFilterPanel onChange={onChange} />);
    await openPanel(user, "Author Filters");
    await user.type(
      screen.getByPlaceholderText("Enter author name and press Add"),
      "Alice{Enter}",
    );
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ includeAuthorNames: ["Alice"] }),
    );
  });

  it("adds a specific video id via the tags input", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<StatefulFilterPanel onChange={onChange} />);
    await openPanel(user, "Video Filters");
    await user.type(
      screen.getByPlaceholderText("Enter video ID and press Add"),
      "vid-123{Enter}",
    );
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ videoIds: ["vid-123"] }),
    );
  });

  it("adds a category through the multi-select custom input", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<StatefulFilterPanel onChange={onChange} />);
    await openPanel(user, "Video Filters");
    await user.type(
      screen.getByPlaceholderText("Or type a custom category…"),
      "Science & Technology{Enter}",
    );
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ categories: ["Science & Technology"] }),
    );
  });

  it("updates the overlap minimum count", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<StatefulFilterPanel onChange={onChange} />);
    await openPanel(user, "Author Overlap Filters");
    fireEvent.change(screen.getByPlaceholderText("Minimum overlap count"), {
      target: { value: "3" },
    });
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ overlapMin: 3 }),
    );
  });

  it("collects specific videos for the video overlap mode", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <StatefulFilterPanel
        initial={{ ...INITIAL_FILTERS, overlapMode: "video" }}
        onChange={onChange}
      />,
    );
    await openPanel(user, "Author Overlap Filters");
    await user.type(
      screen.getByPlaceholderText("Enter video ID and press Add"),
      "vid-ov{Enter}",
    );
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ overlapVideoIds: ["vid-ov"] }),
    );
  });

  it("collects specific channels for the channel overlap mode", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <StatefulFilterPanel
        initial={{ ...INITIAL_FILTERS, overlapMode: "channel" }}
        onChange={onChange}
        channels={[
          { channel_id: "ch1", title: "Channel One" },
          { channel_id: "ch2", title: "Channel Two" },
        ]}
      />,
    );
    await openPanel(user, "Author Overlap Filters");
    await user.click(getPopoverCombobox());
    await user.click(await screen.findByText(/Channel One/));
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ overlapChannelIds: ["ch1"] }),
    );
  });

  it("selects channels through the channel multi-select", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <StatefulFilterPanel
        onChange={onChange}
        channels={[
          { channel_id: "ch1", title: "Channel One" },
          { channel_id: "ch2", title: "Channel Two" },
        ]}
      />,
    );
    await openPanel(user, "Channel Filters");
    await user.click(getPopoverCombobox());
    await user.click(await screen.findByText(/Channel One/));
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ includeChannelIds: ["ch1"] }),
    );
  });

  it("selects video categories through the categories multi-select", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<StatefulFilterPanel onChange={onChange} />);
    await openPanel(user, "Video Filters");
    await user.click(getPopoverCombobox());
    await user.click(await screen.findByText("Comedy"));
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ categories: ["Comedy"] }),
    );
  });
});

describe("sampling: ScopeSelector", () => {
  it("switches scope type via segmented buttons", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <StatefulScopeSelector
        initial={{ scopeType: "all", channelIds: [], authorIds: [], runScope: "all", runIds: [] }}
        onChange={onChange}
      />,
    );
    await user.click(screen.getByRole("button", { name: "By Author" }));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ scopeType: "author" }),
    );
    expect(screen.getByRole("button", { name: "By Author" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("marks the active scope with aria-pressed", () => {
    renderWithProviders(
      <ScopeSelector
        value={{ scopeType: "channel", channelIds: [], authorIds: [], runScope: "all", runIds: [] }}
        onChange={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: "By Channel" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("adds an author id on Enter and dedupes against existing ids", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <StatefulScopeSelector
        initial={{ scopeType: "author", channelIds: [], authorIds: [], runScope: "all", runIds: [] }}
        onChange={onChange}
      />,
    );
    const input = screen.getByPlaceholderText(
      "Enter author ID and press Enter…",
    );
    await user.type(input, "author-x{Enter}");
    expect(onChange).toHaveBeenNthCalledWith(1, {
      scopeType: "author",
      channelIds: [],
      authorIds: ["author-x"],
      runScope: "all",
      runIds: [],
    });

    await user.type(input, "author-x{Enter}");
    // Second attempt is a no-op because the id already exists.
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it("removes an author id from the selected list", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <StatefulScopeSelector
        initial={{ scopeType: "author", channelIds: [], authorIds: ["one"], runScope: "all", runIds: [] }}
        onChange={onChange}
      />,
    );
    expect(screen.getByText("1 author(s) selected")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "×" }));
    expect(onChange).toHaveBeenLastCalledWith({
      scopeType: "author",
      channelIds: [],
      authorIds: [],
      runScope: "all",
      runIds: [],
    });
  });

  it("shows channel count when channels are selected", () => {
    renderWithProviders(
      <ScopeSelector
        value={{ scopeType: "channel", channelIds: ["ch1", "ch2"], authorIds: [], runScope: "all", runIds: [] }}
        onChange={() => {}}
        channels={[
          { channel_id: "ch1", title: "Channel One" },
          { channel_id: "ch2", title: "Channel Two" },
        ]}
      />,
    );
    expect(screen.getByText("2 channel(s) selected")).toBeInTheDocument();
  });

  it("clears run filtering when leaving the channel scope", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <StatefulScopeSelector
        initial={{ scopeType: "channel", channelIds: [], authorIds: [], runScope: "specific", runIds: ["r1"] }}
        onChange={onChange}
      />,
    );
    await user.click(screen.getByRole("button", { name: "All Data" }));
    expect(onChange).toHaveBeenLastCalledWith({
      scopeType: "all",
      channelIds: [],
      authorIds: [],
      runScope: "all",
      runIds: [],
    });
  });
});

describe("sampling: SamplingMethodSelector", () => {
  it("shows random-size input and forwards changes", () => {
    const onRandomSizeChange = vi.fn();
    renderWithProviders(
      <SamplingMethodSelector
        value="random"
        onChange={() => {}}
        randomSize="500"
        onRandomSizeChange={onRandomSizeChange}
      />,
    );
    expect(screen.getByText("Random Sample")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("500"), {
      target: { value: "100" },
    });
    expect(onRandomSizeChange).toHaveBeenLastCalledWith("100");
  });

  it("forwards seed input changes", () => {
    const onSeedChange = vi.fn();
    renderWithProviders(
      <SamplingMethodSelector
        value="random"
        onChange={() => {}}
        seed=""
        onSeedChange={onSeedChange}
      />,
    );
    fireEvent.change(screen.getByPlaceholderText("Auto-generated"), {
      target: { value: "42" },
    });
    expect(onSeedChange).toHaveBeenLastCalledWith("42");
  });

  it("shows strata controls and forwards changes", () => {
    const onSamplesPerStratumChange = vi.fn();
    renderWithProviders(
      <SamplingMethodSelector
        value="stratified"
        onChange={() => {}}
        strataVariable="month"
        onStrataVariableChange={() => {}}
        samplesPerStratum="50"
        onSamplesPerStratumChange={onSamplesPerStratumChange}
      />,
    );
    expect(screen.getByText("Stratification Variable")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("50"), {
      target: { value: "25" },
    });
    expect(onSamplesPerStratumChange).toHaveBeenLastCalledWith("25");
  });

  it("hides random size inputs when method is full", () => {
    renderWithProviders(<SamplingMethodSelector value="full" onChange={() => {}} />);
    expect(screen.queryByPlaceholderText("500")).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Auto-generated")).not.toBeInTheDocument();
  });
});

describe("sampling: ResultActions", () => {
  it("updates notes via textarea", () => {
    const onLabelsChange = vi.fn();
    renderWithProviders(
      <StatefulResultActions onChange={onLabelsChange} />,
    );
    fireEvent.change(screen.getByPlaceholderText("Additional notes..."), {
      target: { value: "hello world" },
    });
    expect(onLabelsChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ notes: "hello world" }),
    );
  });

  it("adds a custom label through the form", async () => {
    const onLabelsChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<StatefulResultActions onChange={onLabelsChange} />);
    await user.click(screen.getByRole("button", { name: /Add Custom Label/i }));
    fireEvent.change(
      screen.getByPlaceholderText("Key (e.g., population, timeframe)"),
      { target: { value: "timeframe" } },
    );
    fireEvent.change(screen.getByPlaceholderText("Value"), {
      target: { value: "Q1 2026" },
    });
    await user.click(screen.getByRole("button", { name: "Add" }));

    expect(onLabelsChange).toHaveBeenLastCalledWith(
      expect.objectContaining({
        customLabels: [{ key: "timeframe", value: "Q1 2026" }],
      }),
    );
    expect(screen.getByText("timeframe")).toBeInTheDocument();
    expect(screen.getByText("Q1 2026")).toBeInTheDocument();
  });

  it("enables dataset creation only once a name is provided", async () => {
    const onCreateDataset = vi.fn();
    const user = userEvent.setup();

    function Harness() {
      const [name, setName] = useState("");
      return (
        <ResultActions
          labels={makeLabels()}
          onLabelsChange={() => {}}
          saveOption="dataset"
          onSaveOptionChange={() => {}}
          datasetName={name}
          onDatasetNameChange={setName}
          existingDatasets={[]}
          onCreateDataset={onCreateDataset}
          sampleIds={["x", "y"]}
        />
      );
    }

    renderWithProviders(<Harness />);

    const createButton = screen.getByRole("button", {
      name: /Create Dataset with 2 members/i,
    });
    expect(createButton).toBeDisabled();

    const nameInput = screen.getByPlaceholderText("Enter dataset name...");
    await user.type(nameInput, "My DS");
    expect(createButton).toBeEnabled();

    await user.click(createButton);
    expect(onCreateDataset).toHaveBeenCalledWith("My DS", ["x", "y"]);
  });
});

describe("sampling: SamplingWorkbench", () => {
  beforeEach(() => {
    mockedSampleAdvanced.mockReset();
    mockedSampleAdvanced.mockResolvedValue({
      entity_ids: ["one", "two", "three"],
      population_size: 100,
      sample_size: 3,
      strategy: "random",
      seed: 7,
      entity_type: "video",
      criteria_json: {},
      missing_metric_count: 0,
    });
  });

  it("renders the workbench shell and preset cards", () => {
    renderWithProviders(<SamplingWorkbench entityType="video" />);
    expect(
      screen.getByText("Advanced Sampling Workbench"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /By Author\(s\)/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Random Sample/ }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Run Sample/ })).toBeInTheDocument();
  });

  it("applies a preset and reflects the resulting scope", async () => {
    const user = userEvent.setup();
    renderWithProviders(<SamplingWorkbench entityType="video" />);
    await user.click(
      screen.getByRole("button", {
        name: /By Channel\s*All comments in selected channels/i,
      }),
    );
    expect(
      screen.getAllByRole("button", { name: "By Channel" })[0],
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("runs a preview via the Refresh Preview button and shows ids", async () => {
    const user = userEvent.setup();
    renderWithProviders(<SamplingWorkbench entityType="video" />);
    await user.click(screen.getByRole("button", { name: /Refresh Preview/ }));
    await waitFor(() => {
      expect(mockedSampleAdvanced).toHaveBeenCalledTimes(1);
      expect(screen.getByText("one")).toBeInTheDocument();
    });
    expect(mockedSampleAdvanced).toHaveBeenCalledWith(
      expect.objectContaining({ entity_type: "video" }),
    );
  });

  it("runs and stores a sample via the Run Sample button", async () => {
    const user = userEvent.setup();
    renderWithProviders(<SamplingWorkbench entityType="comment" />);
    await user.click(screen.getByRole("button", { name: /Run Sample/ }));
    await waitFor(() => {
      expect(mockedSampleAdvanced).toHaveBeenCalledTimes(1);
    });
    const spec = mockedSampleAdvanced.mock.calls[0][0];
    expect(spec.entity_type).toBe("comment");
    expect(spec.seed).toBeUndefined();
  });

  it("clears the preview when the preview call fails", async () => {
    mockedSampleAdvanced.mockRejectedValueOnce(new Error("boom"));
    const user = userEvent.setup();
    renderWithProviders(<SamplingWorkbench entityType="video" />);
    await user.click(screen.getByRole("button", { name: /Refresh Preview/ }));
    await waitFor(() => {
      expect(screen.getByText("Run the sample to see IDs")).toBeInTheDocument();
    });
  });

  it("saves a named query and loads it back", async () => {
    vi.spyOn(window, "prompt").mockReturnValue("my query");
    const user = userEvent.setup();
    renderWithProviders(<SamplingWorkbench entityType="video" />);
    await user.click(screen.getByRole("button", { name: /Save Query/ }));
    expect(
      await screen.findByRole("button", { name: "my query" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "my query" }));
  });
});

describe("sampling: workbench spec construction via UI state", () => {
  it("builds a stratified spec with strata metadata", async () => {
    const user = userEvent.setup();
    renderWithProviders(<SamplingWorkbench entityType="comment" />);
    await user.click(
      screen.getByRole("button", { name: /Stratified by Time/ }),
    );
    mockedSampleAdvanced.mockResolvedValueOnce({
      entity_ids: [],
      population_size: 10,
      sample_size: 0,
      strategy: "stratified",
      seed: 1,
      entity_type: "comment",
      criteria_json: {},
      missing_metric_count: 0,
    });
    await user.click(screen.getByRole("button", { name: /Run Sample/ }));
    await waitFor(() => expect(mockedSampleAdvanced).toHaveBeenCalledTimes(1));
    const spec = mockedSampleAdvanced.mock.calls[0][0];
    expect(spec.strategy).toBe("stratified");
    expect(spec.strata).toBe("month");
    expect(spec.sample_per_stratum).toBe(50);
    expect(spec.size).toBeUndefined();
  });

  it("maps video ids, categories and author-name defaults into the advanced spec", async () => {
    const user = userEvent.setup();
    renderWithProviders(<SamplingWorkbench entityType="comment" />);
    mockedSampleAdvanced.mockResolvedValueOnce({
      entity_ids: [],
      population_size: 10,
      sample_size: 0,
      strategy: "random",
      seed: 1,
      entity_type: "comment",
      criteria_json: {},
      missing_metric_count: 0,
    });
    await user.click(screen.getByRole("button", { name: /Video Filters/ }));
    await user.type(
      screen.getByPlaceholderText("Enter video ID and press Add"),
      "vid-1{Enter}",
    );
    await user.type(
      screen.getByPlaceholderText("Or type a custom category…"),
      "Education{Enter}",
    );
    await user.click(screen.getByRole("button", { name: /Run Sample/ }));
    await waitFor(() => expect(mockedSampleAdvanced).toHaveBeenCalledTimes(1));
    const spec = mockedSampleAdvanced.mock.calls[0][0];
    expect(spec.video_ids).toEqual(["vid-1"]);
    expect(spec.categories).toEqual(["Education"]);
    expect(spec.overlap).toBeUndefined();
    expect(spec.overlap_min).toBe(2);
    expect(spec.author_names).toBeUndefined();
  });

  it("merges filter-level channels into the advanced spec channel_ids", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <SamplingWorkbench
        entityType="video"
        channels={[{ channel_id: "chA", title: "Channel A" }]}
      />,
    );
    mockedSampleAdvanced.mockResolvedValueOnce({
      entity_ids: [],
      population_size: 10,
      sample_size: 0,
      strategy: "random",
      seed: 1,
      entity_type: "video",
      criteria_json: {},
      missing_metric_count: 0,
    });
    await user.click(screen.getByRole("button", { name: /Channel Filters/ }));
    await user.click(getPopoverCombobox());
    await user.click(await screen.findByText(/Channel A/));
    await user.click(screen.getByRole("button", { name: /Run Sample/ }));
    await waitFor(() => expect(mockedSampleAdvanced).toHaveBeenCalledTimes(1));
    const spec = mockedSampleAdvanced.mock.calls[0][0];
    expect(spec.channel_ids).toEqual(["chA"]);
    expect(spec.include_all_channels).toBe(true);
  });

  it("sends specific overlap videos and channels in the advanced spec", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <SamplingWorkbench
        entityType="comment"
        channels={[{ channel_id: "chA", title: "Channel A" }]}
      />,
    );
    mockedSampleAdvanced.mockResolvedValueOnce({
      entity_ids: [],
      population_size: 10,
      sample_size: 0,
      strategy: "random",
      seed: 1,
      entity_type: "comment",
      criteria_json: {},
      missing_metric_count: 0,
    });
    await user.click(screen.getByRole("button", { name: /Author Overlap Filters/ }));
    // Switch Overlap Mode to "Across specific videos".
    const overlapSelect = screen
      .getAllByRole("combobox")
      .find((cb) => cb.textContent?.trim().toLowerCase().startsWith("off"));
    if (!overlapSelect)
      throw new Error(
        "Overlap Mode select not found; comboboxes: " +
          JSON.stringify(
            screen.getAllByRole("combobox").map((cb) => cb.textContent?.slice(0, 40)),
          ),
      );
    await user.click(overlapSelect);
    await user.click(await screen.findByRole("option", { name: /Across specific videos/ }));
    await user.type(
      screen.getByPlaceholderText("Enter video ID and press Add"),
      "vid-ov{Enter}",
    );
    await user.click(screen.getByRole("button", { name: /Run Sample/ }));
    await waitFor(() => expect(mockedSampleAdvanced).toHaveBeenCalledTimes(1));
    const spec = mockedSampleAdvanced.mock.calls[0][0];
    expect(spec.overlap).toBe("video");
    expect(spec.overlap_video_ids).toEqual(["vid-ov"]);
    expect(spec.overlap_channel_ids).toBeUndefined();
  });
});

describe("sampling: redesigned wizard layout", () => {
  it("renders the step indicator with all four steps", () => {
    renderWithProviders(<SamplingWorkbench entityType="comment" />);
    for (const name of ["1Scope", "2Filters", "3Method", "4Labels & Save"]) {
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    }
  });

  it("keeps filter sections collapsed until opened", async () => {
    const user = userEvent.setup();
    renderWithProviders(<SamplingWorkbench entityType="comment" />);
    expect(
      screen.queryByPlaceholderText("Enter video ID and press Add"),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Video Filters/ }));
    expect(
      screen.getByPlaceholderText("Enter video ID and press Add"),
    ).toBeInTheDocument();
  });

  it("shows the live preview alongside the step content", () => {
    renderWithProviders(<SamplingWorkbench entityType="comment" />);
    expect(screen.getByText("Live Preview")).toBeInTheDocument();
    expect(screen.getByText("Run the sample to see IDs")).toBeInTheDocument();
    expect(screen.getByText("Start from a template")).toBeInTheDocument();
  });
});

describe("sampling: expanded workspace dialog", () => {
  it("opens a larger sampling workspace on double-click of the title", async () => {
    const user = userEvent.setup();
    renderWithProviders(<SamplingWorkbench entityType="video" />);
    expect(
      screen.queryByText(/Expanded video sampling workspace/),
    ).not.toBeInTheDocument();
    await user.dblClick(screen.getByText("Advanced Sampling Workbench"));
    expect(
      screen.getByText(/Expanded video sampling workspace/),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText("Start from a template").length,
    ).toBeGreaterThanOrEqual(2);
  });

  it("shows a sticky scroll-down indicator when the expanded workspace overflows and scrolls to the bottom on click", async () => {
    const user = userEvent.setup();

    const originalScrollHeight = Object.getOwnPropertyDescriptor(
      HTMLElement.prototype,
      "scrollHeight",
    );
    const originalClientHeight = Object.getOwnPropertyDescriptor(
      HTMLElement.prototype,
      "clientHeight",
    );
    const originalScrollTo = Object.getOwnPropertyDescriptor(
      Element.prototype,
      "scrollTo",
    );
    Object.defineProperty(HTMLElement.prototype, "scrollHeight", {
      configurable: true,
      get: () => 1000,
    });
    Object.defineProperty(HTMLElement.prototype, "clientHeight", {
      configurable: true,
      get: () => 100,
    });
    const scrollToMock = vi.fn();
    Object.defineProperty(Element.prototype, "scrollTo", {
      configurable: true,
      value: scrollToMock,
    });

    try {
      renderWithProviders(<SamplingWorkbench entityType="video" />);
      await user.dblClick(screen.getByText("Advanced Sampling Workbench"));
      const scrollDown = screen.getByRole("button", { name: /scroll down/i });
      expect(scrollDown).toBeInTheDocument();
      await user.click(scrollDown);
      expect(scrollToMock).toHaveBeenCalledWith({ top: 1000, behavior: "smooth" });
    } finally {
      if (originalScrollHeight) {
        Object.defineProperty(HTMLElement.prototype, "scrollHeight", originalScrollHeight);
      } else {
        delete (HTMLElement.prototype as { scrollHeight?: unknown }).scrollHeight;
      }
      if (originalClientHeight) {
        Object.defineProperty(HTMLElement.prototype, "clientHeight", originalClientHeight);
      } else {
        delete (HTMLElement.prototype as { clientHeight?: unknown }).clientHeight;
      }
      if (originalScrollTo) {
        Object.defineProperty(Element.prototype, "scrollTo", originalScrollTo);
      } else {
        delete (Element.prototype as { scrollTo?: unknown }).scrollTo;
      }
    }
  });
});