"use client";

import { Plus, Minus, HelpCircle, Tags, BookMarked, Download } from "lucide-react";
import { useState, type ComponentType, type ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const METHODOLOGIES = [
  "Random sampling",
  "Stratified sampling",
  "Quota sampling",
  "Snowball sampling",
  "Convenience sampling",
  "Custom",
];

function HelpTooltip({ content }: { content: string }) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span className="inline-flex cursor-help" aria-label="Help" tabIndex={0} />
        }
      >
        <HelpCircle className="size-3.5 shrink-0 text-muted-foreground cursor-help" />
      </TooltipTrigger>
      <TooltipContent side="right" className="max-w-64">
        <p>{content}</p>
      </TooltipContent>
    </Tooltip>
  );
}

interface CustomLabel {
  key: string;
  value: string;
}

export interface ResultActionsProps {
  labels: {
    researchQuestion: string;
    methodology: string;
    notes: string;
    customLabels: CustomLabel[];
  };
  onLabelsChange: (labels: {
    researchQuestion: string;
    methodology: string;
    notes: string;
    customLabels: CustomLabel[];
  }) => void;
  saveOption: "individual" | "dataset";
  onSaveOptionChange: (option: "individual" | "dataset") => void;
  datasetName: string;
  onDatasetNameChange: (name: string) => void;
  existingDatasets: { name: string; id: string }[];
  onCreateDataset: (name: string, sampleIds: string[]) => void;
  sampleIds: string[];
}

function SectionLabel({ children }: { children: string }) {
  return (
    <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
      {children}
    </h4>
  );
}

function SaveOptionCard({
  icon: Icon,
  title,
  description,
  selected,
  children,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  description: string;
  selected: boolean;
  children?: ReactNode;
}) {
  return (
    <div
      data-selected={selected || undefined}
      className={cn(
        "flex flex-col gap-2 rounded-xl border p-4 transition-colors",
        selected
          ? "border-primary/50 bg-primary/[0.04]"
          : "border-border bg-background hover:bg-muted/40"
      )}
    >
      <div className="flex items-start gap-3">
        <span
          className={cn(
            "flex size-9 shrink-0 items-center justify-center rounded-lg",
            selected ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
          )}
        >
          <Icon className="size-4" aria-hidden />
        </span>
        <div className="flex-1">
          <p className="text-sm font-semibold">{title}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
        </div>
      </div>
      {selected && children ? <div className="pt-1">{children}</div> : null}
    </div>
  );
}

export function ResultActions({
  labels,
  onLabelsChange,
  saveOption,
  onSaveOptionChange,
  datasetName,
  onDatasetNameChange,
  existingDatasets,
  onCreateDataset,
  sampleIds,
}: ResultActionsProps) {
  const [customLabels, setCustomLabels] = useState<CustomLabel[]>(labels.customLabels);
  const [newLabelKey, setNewLabelKey] = useState("");
  const [newLabelValue, setNewLabelValue] = useState("");
  const [showNewLabel, setShowNewLabel] = useState(false);

  function updateLabels(updates: Partial<typeof labels>) {
    onLabelsChange({ ...labels, ...updates });
  }

  function addCustomLabel() {
    if (newLabelKey.trim() && newLabelValue.trim()) {
      setCustomLabels([...customLabels, { key: newLabelKey.trim(), value: newLabelValue.trim() }]);
      updateLabels({ customLabels: [...customLabels, { key: newLabelKey.trim(), value: newLabelValue.trim() }] });
      setNewLabelKey("");
      setNewLabelValue("");
      setShowNewLabel(false);
    }
  }

  function removeCustomLabel(index: number) {
    const updated = customLabels.filter((_, i) => i !== index);
    setCustomLabels(updated);
    updateLabels({ customLabels: updated });
  }

  function handleCreateDataset() {
    if (datasetName.trim() && sampleIds.length > 0) {
      onCreateDataset(datasetName.trim(), sampleIds);
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Tags className="size-4" aria-hidden />
          </span>
          <div>
            <CardTitle className="text-base font-semibold">
              Labels & Save Options
              <HelpTooltip content="Add metadata to your sample for reproducibility and organization" />
            </CardTitle>
            <CardDescription>
              Document the sample for reproducibility, then choose how it is stored.
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-7">
        <div className="space-y-3">
          <SectionLabel>Research Labels</SectionLabel>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <Label className="text-sm font-medium">Research Question</Label>
                <HelpTooltip content="Enter the research question this sample investigates" />
              </div>
              <Input
                value={labels.researchQuestion ?? ""}
                onChange={(e) => updateLabels({ researchQuestion: e.target.value })}
                placeholder="e.g. How does comment engagement differ across channels?"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <Label className="text-sm font-medium">Methodology</Label>
                <HelpTooltip content="The sampling methodology used" />
              </div>
              <Select value={labels.methodology ?? ""} onValueChange={(val) => updateLabels({ methodology: val ?? "" })}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select or type custom..." />
                </SelectTrigger>
                <SelectContent>
                  {METHODOLOGIES.map((m) => (
                    <SelectItem key={m} value={m}>
                      {m}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5 lg:col-span-2">
              <div className="flex items-center gap-2">
                <Label className="text-sm font-medium">Notes</Label>
                <HelpTooltip content="Any additional notes about this sample" />
              </div>
              <Textarea
                value={labels.notes}
                onChange={(e) => updateLabels({ notes: e.target.value })}
                placeholder="Additional notes..."
                rows={3}
                className="min-h-20"
              />
            </div>
          </div>
        </div>

        <div className="space-y-3">
          <SectionLabel>Custom Labels</SectionLabel>
          {customLabels.length > 0 && (
            <div className="space-y-1.5">
              {customLabels.map((label, index) => (
                <div key={index} className="flex items-center gap-2">
                  <span className="font-mono text-xs bg-muted/50 px-2 py-0.5 rounded">
                    {label.key}
                  </span>
                  <span className="text-xs text-muted-foreground">=</span>
                  <span className="font-mono text-xs bg-muted/50 px-2 py-0.5 rounded flex-1 truncate">
                    {label.value}
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-xs"
                    onClick={() => removeCustomLabel(index)}
                    className="text-destructive hover:text-destructive/80"
                  >
                    <Minus className="size-3.5" />
                  </Button>
                </div>
              ))}
            </div>
          )}

          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setShowNewLabel(true)}
            className="w-full justify-start"
          >
            <Plus className="size-3.5 mr-1.5" />
            Add Custom Label
          </Button>

          {showNewLabel && (
            <div className="space-y-2 p-3 rounded-md border bg-muted/30">
              <div className="grid grid-cols-2 gap-2">
                <Input
                  value={newLabelKey}
                  onChange={(e) => setNewLabelKey(e.target.value)}
                  placeholder="Key (e.g., population, timeframe)"
                />
                <Input
                  value={newLabelValue}
                  onChange={(e) => setNewLabelValue(e.target.value)}
                  placeholder="Value"
                />
              </div>
              <div className="flex gap-2">
                <Button type="button" size="sm" onClick={addCustomLabel}>
                  Add
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => setShowNewLabel(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>

        <div className="space-y-3 border-t pt-6">
          <SectionLabel>Save As</SectionLabel>
          <RadioGroup value={saveOption} onValueChange={onSaveOptionChange as (val: "individual" | "dataset") => void} className="grid gap-3">
            <RadioGroupItem value="individual" className="grid w-full">
              <SaveOptionCard
                icon={Download}
                title="Individual Sample"
                description="Save as a standalone sample in the library."
                selected={saveOption === "individual"}
              />
            </RadioGroupItem>

            <RadioGroupItem value="dataset" className="grid w-full">
              <SaveOptionCard
                icon={BookMarked}
                title="Add to Dataset"
                description="Combine with other samples into a dataset."
                selected={saveOption === "dataset"}
              >
                <div className="space-y-3">
                  <div className="space-y-1.5">
                    <Label className="text-xs font-medium">Dataset Name</Label>
                    <Input
                      value={datasetName}
                      onChange={(e) => onDatasetNameChange(e.target.value)}
                      placeholder="Enter dataset name..."
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs font-medium">Or Select Existing</Label>
                    <Select
                      value=""
                      onValueChange={(val) => {
                        if (val) {
                          // Select existing dataset
                        }
                      }}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select existing dataset..." />
                      </SelectTrigger>
                      <SelectContent>
                        {existingDatasets.map((d) => (
                          <SelectItem key={d.id} value={d.id}>
                            {d.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <Button type="button" size="sm" onClick={handleCreateDataset} disabled={!datasetName.trim()}>
                    Create Dataset with {sampleIds.length} members
                  </Button>
                </div>
              </SaveOptionCard>
            </RadioGroupItem>
          </RadioGroup>
        </div>
      </CardContent>
    </Card>
  );
}