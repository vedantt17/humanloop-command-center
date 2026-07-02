export type RiskLevel = "low" | "medium" | "high" | "critical";

export type Project = {
  id: number;
  name: string;
  customer: string;
  domain: string;
  task_type: string;
  target_dataset_size: number;
  deadline: string;
  quality_threshold: number;
  required_expertise: string;
  priority: string;
  delivery_format: "JSONL" | "CSV";
  status: string;
  task_counts: Record<string, number>;
  total_tasks: number;
  approved_tasks: number;
  readiness_score: number;
  qa_pass_rate: number;
  open_flags: number;
  days_to_deadline: number;
  risk_level: RiskLevel;
  readiness_status: string;
};

export type Contributor = {
  id: string;
  name: string;
  domain_expertise: string;
  location_tz: string;
  capacity_per_week: number;
  current_assignment_status: string;
  approval_rate: number;
  average_rubric_score: number;
  rejection_rate: number;
  training_status: string;
  coaching_flag: boolean;
  historical_throughput: number;
  active_tasks: number;
  load_percent: number;
  open_flags: number;
};

export type EvaluationTask = {
  id: string;
  project_id: number;
  project_name: string;
  customer: string;
  domain: string;
  prompt: string;
  model_response: string;
  human_rating: number | null;
  rubric_score: number | null;
  reviewer_comments: string;
  qa_status: string;
  reviewer: string;
  assigned_contributor: string;
  assigned_contributor_id: string | null;
  status: string;
  qa_flag_count: number;
  submission_time: string | null;
  risk_score: number;
};

export type QualityFlag = {
  id: number;
  task_id: string | null;
  project_id: number | null;
  project_name: string;
  contributor_id: string | null;
  contributor_name: string;
  category: string;
  category_label: string;
  severity: "low" | "medium" | "high" | "critical";
  owner: string;
  status: string;
  description: string;
  created_at: string;
};

export type Summary = {
  generated_at: string;
  kpis: {
    active_projects: number;
    tasks_completed_today: number;
    dataset_readiness_score: number;
    qa_pass_rate: number;
    review_backlog: number;
    sla_risk: number;
    contributor_approval_rate: number;
    rejected_task_count: number;
    customer_delivery_readiness: number;
  };
  pipeline_funnel: Array<{ status: string; count: number }>;
  qa_pass_rate_by_domain: Array<{ domain: string; passRate: number; reviewed: number }>;
  contributor_quality_distribution: Array<{ band: string; contributors: number }>;
  project_deadline_risk: Project[];
  task_throughput_over_time: Array<{ date: string; tasks: number }>;
  rejection_reasons: Array<{ reason: string; count: number }>;
  domain_workload: Array<{ domain: string; tasks: number; approved: number; open_flags: number; readiness: number }>;
  quality_flag_categories: Array<{ category: string; count: number }>;
  contributor_leaderboard: Contributor[];
  low_performing_contributors: Contributor[];
  overloaded_contributors: Contributor[];
  domain_coverage_gaps: Array<{ domain: string; qualified_contributors: number; tasks_per_contributor: number; status: string }>;
  top_risk_projects: Project[];
};

export type RubricDraft = {
  mode: string;
  customer_name: string;
  rubric_title: string;
  quality_threshold: number;
  target_dataset_size: number;
  criteria: Array<{ name: string; weight: number; guidance: string }>;
  calibration_notes: string[];
};

export type DeliveryNotes = {
  mode: string;
  project_id: number;
  audience: string;
  delivery_note: string;
  recommended_actions: string[];
};

