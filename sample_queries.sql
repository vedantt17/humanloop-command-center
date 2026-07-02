-- Active project delivery risk ranked by deadline pressure and open flags.
SELECT
  p.id,
  c.name AS customer,
  p.domain,
  p.deadline,
  COUNT(qf.id) AS open_flags,
  SUM(CASE WHEN et.status IN ('approved', 'delivered') THEN 1 ELSE 0 END) * 1.0 / p.target_dataset_size AS readiness_ratio
FROM projects p
JOIN customers c ON c.id = p.customer_id
LEFT JOIN evaluation_tasks et ON et.project_id = p.id
LEFT JOIN quality_flags qf ON qf.project_id = p.id AND qf.status IN ('open', 'triaged')
GROUP BY p.id, c.name, p.domain, p.deadline, p.target_dataset_size
ORDER BY p.deadline ASC, open_flags DESC;

-- Contributor quality leaderboard.
SELECT
  id,
  name,
  domain_expertise,
  ROUND(approval_rate * 100, 1) AS approval_rate_pct,
  average_rubric_score,
  ROUND(rejection_rate * 100, 1) AS rejection_rate_pct,
  active_tasks,
  capacity_per_week
FROM contributors
ORDER BY average_rubric_score DESC, approval_rate DESC
LIMIT 20;

-- QA pass rate by domain.
SELECT
  p.domain,
  COUNT(q.id) AS reviewed_tasks,
  ROUND(SUM(CASE WHEN q.qa_status = 'pass' THEN 1 ELSE 0 END) * 100.0 / COUNT(q.id), 1) AS qa_pass_rate
FROM qa_reviews q
JOIN evaluation_tasks et ON et.id = q.task_id
JOIN projects p ON p.id = et.project_id
GROUP BY p.domain
ORDER BY qa_pass_rate DESC;

-- Rejection reasons breakdown.
SELECT
  rejection_reason,
  COUNT(*) AS rejected_tasks
FROM qa_reviews
WHERE rejection_reason IS NOT NULL
GROUP BY rejection_reason
ORDER BY rejected_tasks DESC;

-- Export candidate rows for a project.
SELECT
  et.prompt,
  mr.response AS model_response,
  hr.rating AS final_human_rating,
  rs.overall_score AS rubric_score,
  q.qa_status,
  q.notes AS reviewer_notes,
  p.domain,
  p.id AS project_id
FROM evaluation_tasks et
JOIN projects p ON p.id = et.project_id
JOIN model_responses mr ON mr.task_id = et.id
JOIN rubric_scores rs ON rs.task_id = et.id
JOIN qa_reviews q ON q.task_id = et.id
JOIN human_ratings hr ON hr.task_id = et.id AND hr.is_final = 1
WHERE et.status IN ('approved', 'delivered')
  AND p.id = 1;

