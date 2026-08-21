"use client";

import { useEffect, useMemo, useReducer, useState } from "react";
import {
  Plus,
  Trash2,
  CornerDownRight,
  Braces,
  Filter as FilterIcon,
} from "lucide-react";
import type {
  QueryCondition,
  QueryGroup,
  QueryGroupOp,
  QueryOperator,
  ResearchEntity,
  VariableMeta,
} from "@/lib/types";
import { useResearchOperators, useResearchVariables } from "@/services/queries";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Combobox } from "@/components/ui/combobox";
import { Badge } from "@/components/ui/badge";
import { LoadingState, ErrorState } from "@/components/features/state";
import { cn } from "@/lib/utils";

type Node = QueryCondition | QueryGroup;

export type QueryBuilderAction =
  | { type: "reset-root"; op: QueryGroupOp; conditions: Node[] }
  | { type: "add-condition"; path: number[] }
  | { type: "add-group"; path: number[] }
  | { type: "remove"; path: number[] }
  | { type: "set-group-op"; path: number[]; op: QueryGroupOp }
  | { type: "update-condition"; path: number[]; patch: Partial<QueryCondition> };

function emptyGroup(): QueryGroup {
  return { operator: "AND", conditions: [] };
}

function getGroup(root: QueryGroup, path: number[]): QueryGroup {
  let node: QueryGroup | Node = root;
  for (const index of path) {
    node = (node as QueryGroup).conditions[index];
  }
  return node as QueryGroup;
}

function replaceAtPath(root: QueryGroup, path: number[], next: Node): QueryGroup {
  if (path.length === 0) return next as QueryGroup;
  const cloned: QueryGroup = JSON.parse(JSON.stringify(root));
  let node = cloned;
  for (let i = 0; i < path.length - 1; i++) {
    node = node.conditions[path[i]] as QueryGroup;
  }
  node.conditions[path[path.length - 1]] = next;
  return cloned;
}

function isGroup(node: Node): node is QueryGroup {
  return "operator" in node && "conditions" in node;
}

function reducer(state: QueryGroup, action: QueryBuilderAction): QueryGroup {
  switch (action.type) {
    case "reset-root":
      return {
        operator: action.op,
        conditions: JSON.parse(JSON.stringify(action.conditions)),
      };
    case "add-condition": {
      const parent = getGroup(state, action.path);
      const next: QueryCondition = { variable: "", operator: "eq" };
      return replaceAtPath(state, action.path, {
        ...parent,
        conditions: [...parent.conditions, next],
      });
    }
    case "add-group": {
      const parent = getGroup(state, action.path);
      return replaceAtPath(state, action.path, {
        ...parent,
        conditions: [...parent.conditions, emptyGroup()],
      });
    }
    case "remove": {
      if (action.path.length === 0) return emptyGroup();
      const parentPath = action.path.slice(0, -1);
      const parent = getGroup(state, parentPath);
      const index = action.path[action.path.length - 1];
      return replaceAtPath(state, parentPath, {
        ...parent,
        conditions: parent.conditions.filter((_, i) => i !== index),
      });
    }
    case "set-group-op": {
      const node = getGroup(state, action.path);
      return replaceAtPath(state, action.path, { ...node, operator: action.op });
    }
    case "update-condition": {
      const node = getGroup(state, action.path) as unknown as QueryCondition;
      return replaceAtPath(state, action.path, { ...node, ...action.patch });
    }
    default:
      return state;
  }
}

const ENTITIES: ResearchEntity[] = ["video", "comment", "channel", "recommendation", "author"];
const GROUP_OPS: QueryGroupOp[] = ["AND", "OR", "NOT"];

export function QueryBuilder({
  initialRoot,
  initialEntity = "video",
  onChange,
}: {
  initialRoot?: QueryGroup | null;
  initialEntity?: ResearchEntity;
  onChange: (entity: ResearchEntity, root: QueryGroup) => void;
}) {
  const [entity, setEntity] = useState<ResearchEntity>(initialEntity);
  const [root, dispatch] = useReducer(
    reducer,
    initialRoot ?? emptyGroup(),
    (x) => JSON.parse(JSON.stringify(x)),
  );

  useEffect(() => {
    onChange(entity, root);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entity, root]);

  const variablesQuery = useResearchVariables(entity);
  const operatorsQuery = useResearchOperators();
  const variables = useMemo(
    () => variablesQuery.data ?? [],
    [variablesQuery.data],
  );
  const operators = useMemo(
    () => operatorsQuery.data ?? [],
    [operatorsQuery.data],
  );

  const variablesByType = useMemo(
    () => new Map(variables.map((v) => [v.name, v])),
    [variables],
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Label className="text-xs text-muted-foreground">Population entity</Label>
        <Select
          value={entity}
          onValueChange={(v) => {
            setEntity(v as ResearchEntity);
            dispatch({ type: "reset-root", op: "AND", conditions: [] });
          }}
        >
          <SelectTrigger className="w-auto">
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="w-[--anchor-width]">
            {ENTITIES.map((e) => (
              <SelectItem key={e} value={e}>
                {e}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-xs text-muted-foreground">
          Rank operators evaluate against the current population; only observed
          values match.
        </span>
      </div>

      {variablesQuery.isLoading ? (
        <LoadingState label="Loading variable catalogue…" />
      ) : variablesQuery.isError ? (
        <ErrorState
          message={(variablesQuery.error as Error).message}
          retry={() => variablesQuery.refetch()}
        />
      ) : (
        <GroupNode
          node={root}
          path={[]}
          depth={0}
          variables={variables}
          variablesByType={variablesByType}
          operators={operators.map((o) => o.name)}
          dispatch={dispatch}
        />
      )}

      <div className="flex items-center justify-between">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => dispatch({ type: "add-condition", path: [] })}
        >
          <Plus className="size-3.5" aria-hidden />
          Add condition
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => dispatch({ type: "add-group", path: [] })}
        >
          <Braces className="size-3.5" aria-hidden />
          Add group
        </Button>
      </div>
    </div>
  );
}

function GroupNode({
  node,
  path,
  depth,
  variables,
  variablesByType,
  operators,
  dispatch,
}: {
  node: QueryGroup;
  path: number[];
  depth: number;
  variables: VariableMeta[];
  variablesByType: Map<string, VariableMeta>;
  operators: QueryOperator[];
  dispatch: React.Dispatch<QueryBuilderAction>;
}) {
  return (
    <div
      className={cn(
        "space-y-2 rounded-md border p-3",
        depth === 0 ? "bg-transparent" : "bg-muted/30",
      )}
    >
      <div className="flex items-center gap-2">
        {depth > 0 ? (
          <>
            <Select
              value={node.operator}
              onValueChange={(op) =>
                dispatch({ type: "set-group-op", path, op: op as QueryGroupOp })
              }
            >
              <SelectTrigger size="sm" className="w-auto">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="w-[--anchor-width]">
                {GROUP_OPS.map((op) => (
                  <SelectItem key={op} value={op}>
                    {op}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <span className="text-xs text-muted-foreground">these rules</span>
          </>
        ) : (
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <FilterIcon className="size-3.5" aria-hidden />
            Query root
          </span>
        )}
        <div className="ml-auto flex gap-1">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => dispatch({ type: "add-condition", path })}
          >
            <Plus className="size-3.5" aria-hidden />
            Condition
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => dispatch({ type: "add-group", path })}
          >
            <CornerDownRight className="size-3.5" aria-hidden />
            Nested
          </Button>
          {depth > 0 ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => dispatch({ type: "remove", path })}
            >
              <Trash2 className="size-3.5" aria-hidden />
            </Button>
          ) : null}
        </div>
      </div>

      {node.conditions.length === 0 ? (
        <p className="text-sm text-muted-foreground">No conditions yet.</p>
      ) : (
        <div className="space-y-2">
          {node.conditions.map((child, index) => {
            const childPath = [...path, index];
            if (isGroup(child)) {
              return (
                <GroupNode
                  key={index}
                  node={child}
                  path={childPath}
                  depth={depth + 1}
                  variables={variables}
                  variablesByType={variablesByType}
                  operators={operators}
                  dispatch={dispatch}
                />
              );
            }
            return (
              <ConditionRow
                key={index}
                condition={child}
                path={childPath}
                variables={variables}
                variablesByType={variablesByType}
                operators={operators}
                dispatch={dispatch}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

function ConditionRow({
  condition,
  path,
  variables,
  variablesByType,
  operators,
  dispatch,
}: {
  condition: QueryCondition;
  path: number[];
  variables: VariableMeta[];
  variablesByType: Map<string, VariableMeta>;
  operators: QueryOperator[];
  dispatch: React.Dispatch<QueryBuilderAction>;
}) {
  const meta = condition.variable
    ? variablesByType.get(condition.variable)
    : undefined;

  return (
    <div className="flex flex-wrap items-end gap-2 rounded-md border border-border bg-background p-2">
      <div className="min-w-40 space-y-1">
        <Label className="text-[11px] text-muted-foreground">Variable</Label>
        <Combobox
          items={variables.map((v) => ({
            value: v.name,
            label: `${v.name} (${v.data_type})`,
          }))}
          value={condition.variable || undefined}
          onChange={(value) =>
            dispatch({
              type: "update-condition",
              path,
              patch: {
                variable: String(value),
                operator: "eq",
                value: undefined,
                values: undefined,
                quantile_n: null,
                quartile: null,
              },
            })
          }
          placeholder="Choose variable…"
        />
      </div>

      <div className="min-w-32 space-y-1">
        <Label className="text-[11px] text-muted-foreground">Operator</Label>
        <Combobox
          items={operators.map((op) => ({ value: op, label: op }))}
          value={condition.operator}
          onChange={(value) =>
            dispatch({
              type: "update-condition",
              path,
              patch: { operator: value as QueryOperator, value: undefined, values: undefined },
            })
          }
          placeholder="Operator…"
        />
      </div>

      <ValueInputs condition={condition} meta={meta} path={path} dispatch={dispatch} />

      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => dispatch({ type: "remove", path })}
      >
        <Trash2 className="size-3.5" aria-hidden />
      </Button>
    </div>
  );
}

function ValueInputs({
  condition,
  meta,
  path,
  dispatch,
}: {
  condition: QueryCondition;
  meta?: VariableMeta;
  path: number[];
  dispatch: React.Dispatch<QueryBuilderAction>;
}) {
  const op = condition.operator;
  const isNumeric = meta?.data_type === "int" || meta?.data_type === "float";
  const isText =
    meta?.data_type === "str" || meta?.data_type === "datetime" || !meta?.data_type;

  const patch = (p: Partial<QueryCondition>) =>
    dispatch({ type: "update-condition", path, patch: p });

  switch (op) {
    case "is_null":
    case "not_null":
    case "median_split":
      return (
        <div className="flex items-center gap-2 pb-1">
          <Badge variant="secondary" className="text-xs">
            {op === "median_split" ? "≥ median" : "no value required"}
          </Badge>
        </div>
      );
    case "between": {
      // Backend contract: values=[low, high]. Store BOTH bounds in `values`
      // (the previous code split them across `value` and `values[0]`, which the
      // server ignored -> every `between` query 400'd).
      const setBound = (idx: 0 | 1, raw: number | string | undefined) => {
        const next = [...(condition.values ?? [])] as Array<
          number | string | undefined
        >;
        next[idx] = raw;
        const cleaned = next.filter(
          (x) => x !== undefined,
        ) as Array<number | string>;
        patch({ value: undefined, values: cleaned.length ? cleaned : null });
      };
      return isNumeric ? (
        <>
          {field("From", (
            <NumberInput
              value={condition.values?.[0] as number | undefined}
              onChange={(v) => setBound(0, v)}
            />
          ))}
          {field("To", (
            <NumberInput
              value={condition.values?.[1] as number | undefined}
              onChange={(v) => setBound(1, v)}
            />
          ))}
        </>
      ) : (
        <>
          {field("From", (
            <Input
              value={String(condition.values?.[0] ?? "")}
              onChange={(e) => setBound(0, e.target.value || undefined)}
            />
          ))}
          {field("To", (
            <Input
              value={String(condition.values?.[1] ?? "")}
              onChange={(e) => setBound(1, e.target.value || undefined)}
            />
          ))}
        </>
      );
    }
    case "top_pct":
    case "bottom_pct":
    case "percentile_rank":
      return field("Percentile (0–100)", (
        <NumberInput
          value={condition.value as number | undefined}
          placeholder="e.g. 90"
          onChange={(v) => patch({ value: v })}
        />
      ));
    case "quartile":
      return field("Quartile (1–4)", (
        <Select
          value={condition.quartile ? String(condition.quartile) : undefined}
          onValueChange={(v) => patch({ quartile: Number(v) })}
        >
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="w-[--anchor-width]">
            {[1, 2, 3, 4].map((q) => (
              <SelectItem key={q} value={String(q)}>
                Q{q}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ));
    case "quantile":
      return field("Groups (n)", (
        <NumberInput
          value={condition.quantile_n as number | undefined}
          placeholder="e.g. 5"
          onChange={(v) => patch({ quantile_n: v })}
        />
      ));
    case "in":
    case "not_in":
      return field("Values", (
        <Input
          placeholder="comma-separated"
          value={
            condition.values
              ? (condition.values as Array<string | number>).join(", ")
              : ""
          }
          onChange={(e) =>
            patch({
              values: e.target.value
                ? e.target.value.split(",").map((s) => s.trim()).filter(Boolean)
                : null,
            })
          }
        />
      ));
    default:
      if (isNumeric) {
        return field("Value", (
          <NumberInput
            value={condition.value as number | undefined}
            onChange={(v) => patch({ value: v })}
          />
        ));
      }
      if (meta?.data_type === "bool") {
        return field("True / False", (
          <Select
            value={
              condition.value === undefined || condition.value === null
                ? undefined
                : String(condition.value)
            }
            onValueChange={(v) =>
              patch({ value: v === "true" ? true : v === "false" ? false : null })
            }
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="w-[--anchor-width]">
              <SelectItem value="true">true</SelectItem>
              <SelectItem value="false">false</SelectItem>
            </SelectContent>
          </Select>
        ));
      }
      return field(isText ? "Text" : "Value", (
        <Input
          value={String(condition.value ?? "")}
          onChange={(e) => patch({ value: e.target.value || null })}
        />
      ));
  }
}

function field(label: string, children: React.ReactNode) {
  return (
    <div className="min-w-36 space-y-1">
      <Label className="text-[11px] text-muted-foreground">{label}</Label>
      {children}
    </div>
  );
}

function NumberInput({
  value,
  onChange,
  placeholder,
}: {
  value?: number | null;
  onChange: (v?: number) => void;
  placeholder?: string;
}) {
  return (
    <Input
      type="number"
      placeholder={placeholder}
      value={value === undefined || value === null ? "" : String(value)}
      onChange={(e) =>
        onChange(e.target.value === "" ? undefined : Number(e.target.value))
      }
    />
  );
}