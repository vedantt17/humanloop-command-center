import type { Contributor, DeliveryNotes, EvaluationTask, Project, QualityFlag, RubricDraft, Summary } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

async function fetchJson<T>(path: string, fallback: string): Promise<T> {
  try {
    const response = await fetch(`${API_BASE}${path}`);
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return (await response.json()) as T;
  } catch {
    const fallbackResponse = await fetch(fallback);
    if (!fallbackResponse.ok) throw new Error(`Unable to load ${path} or ${fallback}`);
    return (await fallbackResponse.json()) as T;
  }
}

export async function loadDashboardData() {
  const [summary, projects, contributors, tasks, flags] = await Promise.all([
    fetchJson<Summary>("/api/dashboard/summary", "/demo/summary.json"),
    fetchJson<Project[]>("/api/projects", "/demo/projects.json"),
    fetchJson<Contributor[]>("/api/contributors", "/demo/contributors.json"),
    fetchJson<EvaluationTask[]>("/api/tasks?limit=500", "/demo/tasks.json"),
    fetchJson<QualityFlag[]>("/api/quality-flags", "/demo/flags.json")
  ]);
  return { summary, projects, contributors, tasks, flags };
}

export async function postRubricDraft(payload: {
  customer_name: string;
  domain: string;
  task_type: string;
  required_expertise: string;
  quality_threshold: number;
  target_dataset_size: number;
}): Promise<RubricDraft> {
  try {
    const response = await fetch(`${API_BASE}/api/llm/rubric`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error("rubric fallback");
    return (await response.json()) as RubricDraft;
  } catch {
    return {
      mode: "static_fallback",
      customer_name: payload.customer_name,
      rubric_title: `${payload.domain} ${payload.task_type} Rubric`,
      quality_threshold: payload.quality_threshold,
      target_dataset_size: payload.target_dataset_size,
      criteria: [
        { name: "Accuracy", weight: 0.34, guidance: "Check all domain facts against source evidence." },
        { name: "Completeness", weight: 0.24, guidance: "Confirm every prompt requirement is addressed." },
        { name: "Safety", weight: 0.18, guidance: "Flag unsafe, misleading, or policy-sensitive content." },
        { name: "Reasoning", weight: 0.24, guidance: "Score rationale quality and reviewer auditability." }
      ],
      calibration_notes: [
        "Escalate score spreads above 1.25 points.",
        "Reject missing ratings and low-effort comments.",
        "Require domain-specific reviewer notes for customer audit trails."
      ]
    };
  }
}

export async function postDeliveryNotes(projectId: number): Promise<DeliveryNotes> {
  try {
    const response = await fetch(`${API_BASE}/api/llm/delivery-notes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: projectId, audience: "customer operations lead" })
    });
    if (!response.ok) throw new Error("delivery fallback");
    return (await response.json()) as DeliveryNotes;
  } catch {
    return {
      mode: "static_fallback",
      project_id: projectId,
      audience: "customer operations lead",
      delivery_note:
        "Delivery packet is ready for operations review. Confirm open QA flags, export checksum, and rubric calibration summary before customer handoff.",
      recommended_actions: [
        "Resolve high-severity flags.",
        "Attach rubric calibration summary.",
        "Export both JSONL and CSV for customer validation."
      ]
    };
  }
}

export async function downloadProjectExport(
  project: Project,
  format: "jsonl" | "csv",
  tasks: EvaluationTask[]
) {
  try {
    const response = await fetch(`${API_BASE}/api/projects/${project.id}/export?format=${format}`);
    if (!response.ok) throw new Error("export fallback");
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="([^"]+)"/);
    triggerDownload(blob, match?.[1] || `humanloop_project_${project.id}.${format}`);
  } catch {
    const exportable = tasks
      .filter((task) => task.project_id === project.id && ["approved", "delivered"].includes(task.status))
      .map((task) => ({
        prompt: task.prompt,
        model_response: task.model_response,
        final_human_rating: task.human_rating,
        rubric_score: task.rubric_score,
        qa_status: task.qa_status,
        reviewer_notes: task.reviewer_comments,
        domain: task.domain,
        project_id: task.project_id
      }));
    const content =
      format === "csv"
        ? toCsv(exportable)
        : exportable.map((row) => JSON.stringify(row)).join("\n");
    triggerDownload(
      new Blob([content], { type: format === "csv" ? "text/csv" : "application/x-ndjson" }),
      `humanloop_project_${project.id}_demo.${format}`
    );
  }
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function toCsv(rows: Array<Record<string, unknown>>) {
  if (!rows.length) return "prompt,model_response,final_human_rating,rubric_score,qa_status,reviewer_notes,domain,project_id\n";
  const headers = Object.keys(rows[0]);
  const escape = (value: unknown) => `"${String(value ?? "").replace(/"/g, '""')}"`;
  return [headers.join(","), ...rows.map((row) => headers.map((header) => escape(row[header])).join(","))].join("\n");
}
