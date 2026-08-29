export type LogEvent =
  | { type: "connected" | "run_start" | "done"; run_id?: string; ts?: string }
  | {
      type: "stage_start" | "stage_done";
      stage?: string;
      run_id?: string;
      ts?: string;
    }
  | {
      type: "tool_call" | "tool_done";
      tool?: string;
      input?: unknown;
      run_id?: string;
      ts?: string;
    }
  | {
      type: "retriever";
      action: "start" | "end";
      tool?: string;
      query?: string;
      count?: number | null;
      run_id?: string;
      ts?: string;
    }
  | {
      type: "llm";
      action: "start" | "end";
      model?: string;
      tokens?: { prompt: number; completion: number; total: number } | null;
      run_id?: string;
      ts?: string;
    }
  | { type: "error"; stage?: string; message?: string; run_id?: string; ts?: string }
  | { type: "cancelled"; run_id?: string; message?: string; ts?: string }
  | { type: "run_complete"; run_id?: string; summary?: unknown; ts?: string }
  | {
      type: "log";
      level?: string;
      logger?: string;
      message?: string;
      run_id?: string;
      ts?: string;
    };

export interface LogCounts {
  stageStart: number;
  done: number;
  error: number;
  tokens: number;
  running: boolean;
}

export interface ReportVal {
  path?: string;
  content?: string;
  sources?: unknown[];
  costs?: number;
}

export interface ResearchAgentState {
  user_initial_query?: string;
  input_paths?: {
    subject_profile_path?: string;
    briefing_1_path?: string;
    briefing_2_path?: string;
  };
  report_plan?: string[] | null;
  reports?: Record<string, ReportVal>;
  run_folder?: string;
  [key: string]: unknown;
}
