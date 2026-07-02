CREATE TABLE customers (
  id INTEGER PRIMARY KEY,
  name VARCHAR(140) NOT NULL UNIQUE,
  segment VARCHAR(80) NOT NULL,
  contact_email VARCHAR(160) NOT NULL,
  created_at DATETIME NOT NULL
);

CREATE TABLE projects (
  id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL REFERENCES customers(id),
  name VARCHAR(180) NOT NULL,
  domain VARCHAR(50) NOT NULL,
  task_type VARCHAR(80) NOT NULL,
  target_dataset_size INTEGER NOT NULL,
  deadline DATETIME NOT NULL,
  quality_threshold FLOAT NOT NULL,
  required_expertise VARCHAR(120) NOT NULL,
  priority VARCHAR(20) NOT NULL,
  delivery_format VARCHAR(10) NOT NULL,
  status VARCHAR(40) NOT NULL,
  created_at DATETIME NOT NULL
);

CREATE TABLE contributors (
  id VARCHAR(20) PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  domain_expertise VARCHAR(160) NOT NULL,
  location_tz VARCHAR(80) NOT NULL,
  capacity_per_week INTEGER NOT NULL,
  current_assignment_status VARCHAR(40) NOT NULL,
  approval_rate FLOAT NOT NULL,
  average_rubric_score FLOAT NOT NULL,
  rejection_rate FLOAT NOT NULL,
  training_status VARCHAR(40) NOT NULL,
  coaching_flag BOOLEAN NOT NULL,
  historical_throughput INTEGER NOT NULL,
  active_tasks INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE contributor_training (
  id INTEGER PRIMARY KEY,
  contributor_id VARCHAR(20) NOT NULL REFERENCES contributors(id),
  module_name VARCHAR(120) NOT NULL,
  status VARCHAR(40) NOT NULL,
  completed_at DATETIME
);

CREATE TABLE evaluation_tasks (
  id VARCHAR(24) PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id),
  prompt TEXT NOT NULL,
  status VARCHAR(40) NOT NULL,
  qa_flag_count INTEGER NOT NULL DEFAULT 0,
  assigned_contributor_id VARCHAR(20) REFERENCES contributors(id),
  reviewer VARCHAR(120),
  submission_time DATETIME,
  created_at DATETIME NOT NULL,
  risk_score FLOAT NOT NULL DEFAULT 0
);

CREATE TABLE model_responses (
  id INTEGER PRIMARY KEY,
  task_id VARCHAR(24) NOT NULL UNIQUE REFERENCES evaluation_tasks(id),
  model_name VARCHAR(80) NOT NULL,
  response TEXT NOT NULL,
  response_version VARCHAR(40) NOT NULL
);

CREATE TABLE human_ratings (
  id INTEGER PRIMARY KEY,
  task_id VARCHAR(24) NOT NULL REFERENCES evaluation_tasks(id),
  contributor_id VARCHAR(20) NOT NULL REFERENCES contributors(id),
  rating INTEGER,
  rubric_score FLOAT NOT NULL,
  reviewer_comments TEXT NOT NULL,
  review_event_type VARCHAR(40) NOT NULL,
  created_at DATETIME NOT NULL,
  submission_seconds INTEGER NOT NULL,
  is_final BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE rubric_scores (
  id INTEGER PRIMARY KEY,
  task_id VARCHAR(24) NOT NULL UNIQUE REFERENCES evaluation_tasks(id),
  criteria_accuracy FLOAT NOT NULL,
  criteria_completeness FLOAT NOT NULL,
  criteria_safety FLOAT NOT NULL,
  criteria_reasoning FLOAT NOT NULL,
  overall_score FLOAT NOT NULL,
  consistency_check BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE qa_reviews (
  id INTEGER PRIMARY KEY,
  task_id VARCHAR(24) NOT NULL UNIQUE REFERENCES evaluation_tasks(id),
  reviewer VARCHAR(120) NOT NULL,
  qa_status VARCHAR(40) NOT NULL,
  notes TEXT NOT NULL,
  reviewed_at DATETIME,
  rejection_reason VARCHAR(120)
);

CREATE TABLE quality_flags (
  id INTEGER PRIMARY KEY,
  task_id VARCHAR(24) REFERENCES evaluation_tasks(id),
  project_id INTEGER REFERENCES projects(id),
  contributor_id VARCHAR(20) REFERENCES contributors(id),
  category VARCHAR(80) NOT NULL,
  severity VARCHAR(20) NOT NULL,
  owner VARCHAR(80) NOT NULL,
  status VARCHAR(40) NOT NULL,
  description TEXT NOT NULL,
  created_at DATETIME NOT NULL
);

CREATE TABLE exports (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id),
  format VARCHAR(10) NOT NULL,
  row_count INTEGER NOT NULL,
  created_at DATETIME NOT NULL,
  checksum VARCHAR(80) NOT NULL
);

CREATE TABLE activity_logs (
  id INTEGER PRIMARY KEY,
  entity_type VARCHAR(60) NOT NULL,
  entity_id VARCHAR(60) NOT NULL,
  action VARCHAR(120) NOT NULL,
  actor VARCHAR(120) NOT NULL,
  created_at DATETIME NOT NULL,
  detail TEXT NOT NULL
);

CREATE INDEX ix_projects_domain ON projects(domain);
CREATE INDEX ix_projects_deadline ON projects(deadline);
CREATE INDEX ix_evaluation_tasks_status ON evaluation_tasks(status);
CREATE INDEX ix_evaluation_tasks_project_id ON evaluation_tasks(project_id);
CREATE INDEX ix_human_ratings_task_id ON human_ratings(task_id);
CREATE INDEX ix_quality_flags_project_id ON quality_flags(project_id);
CREATE INDEX ix_quality_flags_contributor_id ON quality_flags(contributor_id);
CREATE INDEX ix_quality_flags_category ON quality_flags(category);

