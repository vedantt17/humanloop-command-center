import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import {
  AlertTriangle,
  ArrowDownAZ,
  Bot,
  Boxes,
  CheckCircle2,
  ClipboardCheck,
  Database,
  Download,
  FileJson,
  Gauge,
  Layers3,
  LayoutDashboard,
  Loader2,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  UserRoundCheck,
  UsersRound,
  XCircle
} from "lucide-react";
import { downloadProjectExport, loadDashboardData, postDeliveryNotes, postRubricDraft } from "./lib/api";
import type { Contributor, DeliveryNotes, EvaluationTask, Project, QualityFlag, RubricDraft, Summary } from "./types";

type View = "overview" | "projects" | "contributors" | "tasks" | "flags" | "llm" | "exports";
type SortDirection = "asc" | "desc";

const navItems: Array<{ id: View; label: string; icon: typeof LayoutDashboard }> = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "projects", label: "Projects", icon: Boxes },
  { id: "contributors", label: "Contributors", icon: UsersRound },
  { id: "tasks", label: "Evaluation Tasks", icon: ClipboardCheck },
  { id: "flags", label: "Quality Flags", icon: ShieldCheck },
  { id: "llm", label: "LLM Ops", icon: Bot },
  { id: "exports", label: "Exports", icon: Database }
];

const statusOrder = ["unassigned", "assigned", "submitted", "in review", "approved", "rejected", "delivered"];
const riskColors: Record<string, string> = {
  low: "#22C55E",
  medium: "#F59E0B",
  high: "#F97316",
  critical: "#EF4444"
};
const chartColors = ["#38BDF8", "#A78BFA", "#22C55E", "#F59E0B", "#EF4444", "#14B8A6", "#E2E8F0"];

function App() {
  const [view, setView] = useState<View>("overview");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [contributors, setContributors] = useState<Contributor[]>([]);
  const [tasks, setTasks] = useState<EvaluationTask[]>([]);
  const [flags, setFlags] = useState<QualityFlag[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [domainFilter, setDomainFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [flagFilter, setFlagFilter] = useState("all");
  const [projectSort, setProjectSort] = useState<{ key: keyof Project; direction: SortDirection }>({
    key: "days_to_deadline",
    direction: "asc"
  });
  const [taskSort, setTaskSort] = useState<{ key: keyof EvaluationTask; direction: SortDirection }>({
    key: "qa_flag_count",
    direction: "desc"
  });
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [selectedTask, setSelectedTask] = useState<EvaluationTask | null>(null);

  useEffect(() => {
    let mounted = true;
    loadDashboardData()
      .then((data) => {
        if (!mounted) return;
        setSummary(data.summary);
        setProjects(data.projects);
        setContributors(data.contributors);
        setTasks(data.tasks);
        setFlags(data.flags);
        setError(null);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : "Unable to load dashboard data.");
      })
      .finally(() => mounted && setLoading(false));
    return () => {
      mounted = false;
    };
  }, []);

  const domains = useMemo(() => ["all", ...Array.from(new Set(projects.map((project) => project.domain))).sort()], [projects]);
  const filteredProjects = useMemo(() => {
    return sortRows(
      projects.filter((project) => {
        const matchesDomain = domainFilter === "all" || project.domain === domainFilter;
        const haystack = `${project.name} ${project.customer} ${project.domain} ${project.task_type}`.toLowerCase();
        return matchesDomain && haystack.includes(search.toLowerCase());
      }),
      projectSort.key,
      projectSort.direction
    );
  }, [projects, domainFilter, search, projectSort]);

  const filteredTasks = useMemo(() => {
    return sortRows(
      tasks.filter((task) => {
        const matchesDomain = domainFilter === "all" || task.domain === domainFilter;
        const matchesStatus = statusFilter === "all" || task.status === statusFilter;
        const matchesFlags =
          flagFilter === "all" || (flagFilter === "flagged" ? task.qa_flag_count > 0 : task.qa_flag_count === 0);
        const haystack = `${task.id} ${task.project_name} ${task.prompt} ${task.assigned_contributor}`.toLowerCase();
        return matchesDomain && matchesStatus && matchesFlags && haystack.includes(search.toLowerCase());
      }),
      taskSort.key,
      taskSort.direction
    );
  }, [tasks, domainFilter, statusFilter, flagFilter, search, taskSort]);

  const filteredFlags = useMemo(() => {
    return flags.filter((flag) => {
      const matchesDomain =
        domainFilter === "all" || projects.find((project) => project.id === flag.project_id)?.domain === domainFilter;
      const matchesSearch = `${flag.category_label} ${flag.project_name} ${flag.contributor_name} ${flag.description}`
        .toLowerCase()
        .includes(search.toLowerCase());
      return matchesDomain && matchesSearch;
    });
  }, [flags, projects, domainFilter, search]);

  if (loading) {
    return (
      <Shell view={view} onView={setView} search={search} onSearch={setSearch}>
        <div className="state-panel">
          <Loader2 className="spin" size={22} />
          <span>Loading operations data...</span>
        </div>
      </Shell>
    );
  }

  if (error || !summary) {
    return (
      <Shell view={view} onView={setView} search={search} onSearch={setSearch}>
        <div className="state-panel error">
          <XCircle size={22} />
          <span>{error || "Dashboard data is unavailable."}</span>
        </div>
      </Shell>
    );
  }

  return (
    <Shell view={view} onView={setView} search={search} onSearch={setSearch}>
      <Toolbar
        domains={domains}
        domainFilter={domainFilter}
        statusFilter={statusFilter}
        flagFilter={flagFilter}
        onDomain={setDomainFilter}
        onStatus={setStatusFilter}
        onFlag={setFlagFilter}
      />
      {view === "overview" && (
        <Overview
          summary={summary}
          projects={filteredProjects}
          onProject={setSelectedProject}
        />
      )}
      {view === "projects" && (
        <ProjectsView
          projects={filteredProjects}
          sort={projectSort}
          onSort={setProjectSort}
          onProject={setSelectedProject}
        />
      )}
      {view === "contributors" && <ContributorsView contributors={contributors} summary={summary} />}
      {view === "tasks" && (
        <TasksView
          tasks={filteredTasks}
          sort={taskSort}
          onSort={setTaskSort}
          onTask={setSelectedTask}
        />
      )}
      {view === "flags" && <FlagsView flags={filteredFlags} summary={summary} />}
      {view === "llm" && <LlmOpsView projects={projects} contributors={contributors} />}
      {view === "exports" && <ExportsView projects={filteredProjects} tasks={tasks} />}
      {selectedProject && <ProjectDrawer project={selectedProject} onClose={() => setSelectedProject(null)} />}
      {selectedTask && <TaskDrawer task={selectedTask} onClose={() => setSelectedTask(null)} />}
    </Shell>
  );
}

function Shell({
  view,
  onView,
  search,
  onSearch,
  children
}: {
  view: View;
  onView: (view: View) => void;
  search: string;
  onSearch: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">HL</div>
          <div>
            <strong>HumanLoop</strong>
            <span>Command Center</span>
          </div>
        </div>
        <nav className="nav-list" aria-label="Primary dashboard navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                className={`nav-item ${view === item.id ? "active" : ""}`}
                key={item.id}
                onClick={() => onView(item.id)}
                title={item.label}
              >
                <Icon size={17} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="sidebar-foot">
          <span>Ops Health</span>
          <strong>Seeded synthetic data</strong>
        </div>
      </aside>
      <main className="workspace">
        <CommandBand search={search} onSearch={onSearch} />
        {children}
      </main>
    </div>
  );
}

function CommandBand({ search, onSearch }: { search: string; onSearch: (value: string) => void }) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let effect: { destroy?: () => void } | undefined;
    let cancelled = false;
    let starting = false;
    const canAnimate = () => Boolean(ref.current && window.innerWidth >= 760);
    const destroy = () => {
      effect?.destroy?.();
      effect = undefined;
    };
    const start = async () => {
      if (effect || starting || !canAnimate()) return;
      starting = true;
      try {
        const [p5Module, topology] = await Promise.all([import("p5"), import("vanta/dist/vanta.topology.min")]);
        if (cancelled || !ref.current || !canAnimate()) return;
        const p5 = p5Module.default ?? p5Module;
        effect = topology.default({
          el: ref.current,
          p5,
          mouseControls: true,
          touchControls: false,
          gyroControls: false,
          minHeight: 120,
          minWidth: 200,
          scale: 1,
          scaleMobile: 1,
          color: 0x38bdf8,
          backgroundColor: 0x080b12,
          points: 5,
          maxDistance: 17,
          spacing: 18
        });
      } catch {
        destroy();
      } finally {
        starting = false;
      }
    };
    const handleResize = () => {
      if (!canAnimate()) {
        destroy();
        return;
      }
      void start();
    };
    window.addEventListener("resize", handleResize);
    void start();
    return () => {
      cancelled = true;
      window.removeEventListener("resize", handleResize);
      effect?.destroy?.();
    };
  }, []);

  return (
    <header className="command-band" ref={ref}>
      <div className="command-overlay" />
      <div className="command-content">
        <div>
          <div className="eyebrow">AI Evaluation Pipeline for Expert-Labeled Data</div>
          <h1>HumanLoop Command Center</h1>
          <p>Customer intake, expert assignment, QA validation, rubric scoring, and delivery readiness in one operational view.</p>
        </div>
        <label className="search-box">
          <Search size={17} />
          <input
            value={search}
            onChange={(event) => onSearch(event.target.value)}
            placeholder="Search projects, prompts, contributors"
          />
        </label>
      </div>
    </header>
  );
}

function Toolbar({
  domains,
  domainFilter,
  statusFilter,
  flagFilter,
  onDomain,
  onStatus,
  onFlag
}: {
  domains: string[];
  domainFilter: string;
  statusFilter: string;
  flagFilter: string;
  onDomain: (value: string) => void;
  onStatus: (value: string) => void;
  onFlag: (value: string) => void;
}) {
  return (
    <div className="toolbar">
      <div className="toolbar-title">
        <SlidersHorizontal size={17} />
        <span>Controls</span>
      </div>
      <label>
        Domain
        <select value={domainFilter} onChange={(event) => onDomain(event.target.value)}>
          {domains.map((domain) => (
            <option key={domain} value={domain}>
              {domain === "all" ? "All domains" : titleCase(domain)}
            </option>
          ))}
        </select>
      </label>
      <label>
        Task Status
        <select value={statusFilter} onChange={(event) => onStatus(event.target.value)}>
          <option value="all">All statuses</option>
          {statusOrder.map((status) => (
            <option value={status} key={status}>
              {titleCase(status)}
            </option>
          ))}
        </select>
      </label>
      <label>
        QA Flags
        <select value={flagFilter} onChange={(event) => onFlag(event.target.value)}>
          <option value="all">All tasks</option>
          <option value="flagged">Flagged only</option>
          <option value="clear">No flags</option>
        </select>
      </label>
    </div>
  );
}

function Overview({
  summary,
  projects,
  onProject
}: {
  summary: Summary;
  projects: Project[];
  onProject: (project: Project) => void;
}) {
  const kpis = [
    { label: "Active Projects", value: summary.kpis.active_projects, icon: Layers3, accent: "blue" },
    { label: "Dataset Readiness", value: `${summary.kpis.dataset_readiness_score}%`, icon: Gauge, accent: "green" },
    { label: "QA Pass Rate", value: `${summary.kpis.qa_pass_rate}%`, icon: CheckCircle2, accent: "violet" },
    { label: "Review Backlog", value: summary.kpis.review_backlog, icon: ClipboardCheck, accent: "amber" },
    { label: "SLA Risk", value: summary.kpis.sla_risk, icon: AlertTriangle, accent: "red" },
    { label: "Contributor Approval", value: `${summary.kpis.contributor_approval_rate}%`, icon: UserRoundCheck, accent: "green" }
  ];

  return (
    <section className="view-stack">
      <div className="kpi-grid">
        {kpis.map((item) => (
          <KpiCard key={item.label} {...item} />
        ))}
      </div>
      <div className="dashboard-grid">
        <Panel title="Active Project Risk" action={`${projects.length} visible`}>
          <div className="table-scroll compact">
            <table>
              <thead>
                <tr>
                  <th>Project</th>
                  <th>Domain</th>
                  <th>Ready</th>
                  <th>Deadline</th>
                  <th>Risk</th>
                </tr>
              </thead>
              <tbody>
                {projects.slice(0, 8).map((project) => (
                  <tr key={project.id} onClick={() => onProject(project)}>
                    <td>
                      <strong>{project.customer}</strong>
                      <span>{project.name}</span>
                    </td>
                    <td>{titleCase(project.domain)}</td>
                    <td>{project.readiness_score}%</td>
                    <td>{project.days_to_deadline}d</td>
                    <td>
                      <RiskChip risk={project.risk_level} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
        <Panel title="Pipeline Funnel" action="All tasks">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={summary.pipeline_funnel}>
              <CartesianGrid stroke="#263244" vertical={false} />
              <XAxis dataKey="status" tick={{ fill: "#94A3B8", fontSize: 11 }} interval={0} angle={-18} textAnchor="end" height={54} />
              <YAxis tick={{ fill: "#94A3B8", fontSize: 11 }} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(56,189,248,0.08)" }} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {summary.pipeline_funnel.map((_, index) => (
                  <Cell key={index} fill={chartColors[index % chartColors.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>
        <Panel title="Contributor Quality" action="Score distribution">
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={summary.contributor_quality_distribution}>
              <CartesianGrid stroke="#263244" vertical={false} />
              <XAxis dataKey="band" tick={{ fill: "#94A3B8", fontSize: 12 }} />
              <YAxis tick={{ fill: "#94A3B8", fontSize: 11 }} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(167,139,250,0.08)" }} />
              <Bar dataKey="contributors" fill="#A78BFA" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
        <Panel title="SLA and Throughput" action="14-day export path">
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={summary.task_throughput_over_time}>
              <defs>
                <linearGradient id="throughput" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="5%" stopColor="#38BDF8" stopOpacity={0.45} />
                  <stop offset="95%" stopColor="#38BDF8" stopOpacity={0.03} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#263244" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: "#94A3B8", fontSize: 10 }} minTickGap={18} />
              <YAxis tick={{ fill: "#94A3B8", fontSize: 11 }} />
              <Tooltip content={<ChartTooltip />} />
              <Area type="monotone" dataKey="tasks" stroke="#38BDF8" fill="url(#throughput)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </Panel>
      </div>
      <div className="dashboard-grid three">
        <MiniList title="Low-Performing Contributors" rows={summary.low_performing_contributors} />
        <MiniList title="Overloaded Contributors" rows={summary.overloaded_contributors} />
        <Panel title="Domain Workload" action="Readiness">
          <div className="workload-list">
            {summary.domain_workload.map((domain) => (
              <div key={domain.domain} className="workload-row">
                <div>
                  <strong>{titleCase(domain.domain)}</strong>
                  <span>{formatNumber(domain.tasks)} tasks</span>
                </div>
                <div className="progress-track">
                  <span style={{ width: `${Math.min(domain.readiness, 100)}%` }} />
                </div>
                <em>{domain.readiness}%</em>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </section>
  );
}

function ProjectsView({
  projects,
  sort,
  onSort,
  onProject
}: {
  projects: Project[];
  sort: { key: keyof Project; direction: SortDirection };
  onSort: (sort: { key: keyof Project; direction: SortDirection }) => void;
  onProject: (project: Project) => void;
}) {
  return (
    <Panel title="Customer Projects" action={`${projects.length} projects`}>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <SortHeader<Project> label="Customer" column="customer" sort={sort} onSort={onSort} />
              <SortHeader<Project> label="Domain" column="domain" sort={sort} onSort={onSort} />
              <SortHeader<Project> label="Deadline" column="days_to_deadline" sort={sort} onSort={onSort} />
              <SortHeader<Project> label="Readiness" column="readiness_score" sort={sort} onSort={onSort} />
              <SortHeader<Project> label="QA Pass" column="qa_pass_rate" sort={sort} onSort={onSort} />
              <SortHeader<Project> label="Risk" column="risk_level" sort={sort} onSort={onSort} />
              <th>Progress</th>
            </tr>
          </thead>
          <tbody>
            {projects.map((project) => (
              <tr key={project.id} onClick={() => onProject(project)}>
                <td>
                  <strong>{project.customer}</strong>
                  <span>{project.name}</span>
                </td>
                <td>{titleCase(project.domain)}</td>
                <td>
                  <strong>{project.days_to_deadline} days</strong>
                  <span>{new Date(project.deadline).toLocaleDateString()}</span>
                </td>
                <td>{project.readiness_score}%</td>
                <td>{project.qa_pass_rate}%</td>
                <td>
                  <RiskChip risk={project.risk_level} />
                </td>
                <td>
                  <Progress value={project.readiness_score} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function ContributorsView({ contributors, summary }: { contributors: Contributor[]; summary: Summary }) {
  const sorted = [...contributors].sort((a, b) => b.average_rubric_score - a.average_rubric_score).slice(0, 40);
  return (
    <section className="dashboard-grid contributors-layout">
      <Panel title="Contributor Leaderboard" action={`${contributors.length} experts`}>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Contributor</th>
                <th>Expertise</th>
                <th>Approval</th>
                <th>Rubric</th>
                <th>Reject</th>
                <th>Load</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((contributor) => (
                <tr key={contributor.id}>
                  <td>
                    <strong>{contributor.name}</strong>
                    <span>{contributor.id}</span>
                  </td>
                  <td>{contributor.domain_expertise}</td>
                  <td>{contributor.approval_rate}%</td>
                  <td>{contributor.average_rubric_score}</td>
                  <td>{contributor.rejection_rate}%</td>
                  <td>
                    <Progress value={Math.min(contributor.load_percent, 100)} tone={contributor.load_percent > 100 ? "risk" : "normal"} />
                  </td>
                  <td>
                    <StatusChip label={contributor.coaching_flag ? "coaching" : contributor.training_status} tone={contributor.coaching_flag ? "warning" : "success"} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <div className="side-stack">
        <Panel title="Coverage Gaps" action="Qualified supply">
          <div className="gap-list">
            {summary.domain_coverage_gaps.map((gap) => (
              <div key={gap.domain} className="gap-row">
                <div>
                  <strong>{titleCase(gap.domain)}</strong>
                  <span>{gap.qualified_contributors} qualified contributors</span>
                </div>
                <StatusChip label={gap.status} tone={gap.status === "gap" ? "warning" : "success"} />
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="Coaching Queue" action="Next actions">
          <div className="coach-list">
            {summary.low_performing_contributors.slice(0, 6).map((contributor) => (
              <div key={contributor.id} className="coach-row">
                <strong>{contributor.name}</strong>
                <span>{contributor.average_rubric_score} avg score, {contributor.rejection_rate}% rejected</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </section>
  );
}

function TasksView({
  tasks,
  sort,
  onSort,
  onTask
}: {
  tasks: EvaluationTask[];
  sort: { key: keyof EvaluationTask; direction: SortDirection };
  onSort: (sort: { key: keyof EvaluationTask; direction: SortDirection }) => void;
  onTask: (task: EvaluationTask) => void;
}) {
  return (
    <Panel title="Evaluation Task Queue" action={`${tasks.length} tasks shown`}>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <SortHeader<EvaluationTask> label="Task" column="id" sort={sort} onSort={onSort} />
              <SortHeader<EvaluationTask> label="Project" column="project_name" sort={sort} onSort={onSort} />
              <SortHeader<EvaluationTask> label="Domain" column="domain" sort={sort} onSort={onSort} />
              <SortHeader<EvaluationTask> label="Status" column="status" sort={sort} onSort={onSort} />
              <SortHeader<EvaluationTask> label="Rating" column="human_rating" sort={sort} onSort={onSort} />
              <SortHeader<EvaluationTask> label="Rubric" column="rubric_score" sort={sort} onSort={onSort} />
              <SortHeader<EvaluationTask> label="Flags" column="qa_flag_count" sort={sort} onSort={onSort} />
              <th>Contributor</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task) => (
              <tr key={task.id} onClick={() => onTask(task)}>
                <td>
                  <strong>{task.id}</strong>
                  <span>{task.prompt.slice(0, 74)}...</span>
                </td>
                <td>{task.project_name}</td>
                <td>{titleCase(task.domain)}</td>
                <td>
                  <StatusChip label={task.status} tone={task.status === "rejected" ? "danger" : task.status === "approved" || task.status === "delivered" ? "success" : "neutral"} />
                </td>
                <td>{task.human_rating ?? "missing"}</td>
                <td>{task.rubric_score ?? "n/a"}</td>
                <td>{task.qa_flag_count}</td>
                <td>{task.assigned_contributor}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function FlagsView({ flags, summary }: { flags: QualityFlag[]; summary: Summary }) {
  return (
    <section className="dashboard-grid flags-layout">
      <Panel title="Quality Flags" action={`${flags.length} visible`}>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Issue</th>
                <th>Project</th>
                <th>Owner</th>
                <th>Severity</th>
                <th>Status</th>
                <th>Contributor</th>
              </tr>
            </thead>
            <tbody>
              {flags.map((flag) => (
                <tr key={flag.id}>
                  <td>
                    <strong>{flag.category_label}</strong>
                    <span>{flag.description}</span>
                  </td>
                  <td>{flag.project_name}</td>
                  <td>{flag.owner}</td>
                  <td>
                    <SeverityChip severity={flag.severity} />
                  </td>
                  <td>{titleCase(flag.status)}</td>
                  <td>{flag.contributor_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <Panel title="Rejection Reasons" action="QA failures">
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={summary.rejection_reasons} layout="vertical" margin={{ left: 36 }}>
            <CartesianGrid stroke="#263244" horizontal={false} />
            <XAxis type="number" tick={{ fill: "#94A3B8", fontSize: 11 }} />
            <YAxis type="category" dataKey="reason" width={130} tick={{ fill: "#94A3B8", fontSize: 11 }} />
            <Tooltip content={<ChartTooltip />} />
            <Bar dataKey="count" fill="#EF4444" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Panel>
    </section>
  );
}

function LlmOpsView({ projects, contributors }: { projects: Project[]; contributors: Contributor[] }) {
  const [rubric, setRubric] = useState<RubricDraft | null>(null);
  const [notes, setNotes] = useState<DeliveryNotes | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState(projects[0]?.id ?? 1);
  const [busy, setBusy] = useState<string | null>(null);
  const selectedProject = projects.find((project) => project.id === selectedProjectId) || projects[0];
  const coachingQueue = contributors
    .filter((contributor) => contributor.coaching_flag)
    .sort((a, b) => b.rejection_rate - a.rejection_rate)
    .slice(0, 6);

  async function handleRubric() {
    if (!selectedProject) return;
    setBusy("rubric");
    setRubric(
      await postRubricDraft({
        customer_name: selectedProject.customer,
        domain: selectedProject.domain,
        task_type: selectedProject.task_type,
        required_expertise: selectedProject.required_expertise,
        quality_threshold: selectedProject.quality_threshold,
        target_dataset_size: selectedProject.target_dataset_size
      })
    );
    setBusy(null);
  }

  async function handleNotes() {
    if (!selectedProject) return;
    setBusy("notes");
    setNotes(await postDeliveryNotes(selectedProject.id));
    setBusy(null);
  }

  return (
    <section className="dashboard-grid llm-layout">
      <Panel title="Rubric Draft Generator" action="Deterministic LLM mock">
        <div className="form-grid">
          <label>
            Project
            <select value={selectedProjectId} onChange={(event) => setSelectedProjectId(Number(event.target.value))}>
              {projects.map((project) => (
                <option value={project.id} key={project.id}>
                  {project.customer} - {project.domain}
                </option>
              ))}
            </select>
          </label>
          <button className="primary-button" onClick={handleRubric}>
            {busy === "rubric" ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />}
            Generate Rubric
          </button>
        </div>
        {rubric && (
          <div className="llm-output">
            <strong>{rubric.rubric_title}</strong>
            <span>Quality threshold {rubric.quality_threshold} across {rubric.target_dataset_size} target tasks</span>
            {rubric.criteria.map((item) => (
              <div className="criteria-row" key={item.name}>
                <b>{item.name}</b>
                <em>{Math.round(item.weight * 100)}%</em>
                <p>{item.guidance}</p>
              </div>
            ))}
          </div>
        )}
      </Panel>
      <Panel title="Delivery Notes" action="Customer-ready draft">
        <button className="primary-button" onClick={handleNotes}>
          {busy === "notes" ? <Loader2 className="spin" size={16} /> : <FileJson size={16} />}
          Draft Delivery Note
        </button>
        {notes && (
          <div className="llm-output">
            <p>{notes.delivery_note}</p>
            {notes.recommended_actions.map((action) => (
              <div className="action-line" key={action}>
                <CheckCircle2 size={15} />
                <span>{action}</span>
              </div>
            ))}
          </div>
        )}
      </Panel>
      <Panel title="Coaching Recommendations" action="Contributor ops">
        <div className="coach-list">
          {coachingQueue.map((contributor) => (
            <div className="coach-row" key={contributor.id}>
              <strong>{contributor.name}</strong>
              <span>
                Assign calibration refresh for {contributor.domain_expertise.split(",")[0]} and review rejected samples.
              </span>
            </div>
          ))}
        </div>
      </Panel>
    </section>
  );
}

function ExportsView({ projects, tasks }: { projects: Project[]; tasks: EvaluationTask[] }) {
  const readyProjects = [...projects].sort((a, b) => b.readiness_score - a.readiness_score).slice(0, 12);
  return (
    <Panel title="Export-Ready Datasets" action="JSONL and CSV">
      <div className="export-grid">
        {readyProjects.map((project) => (
          <div className="export-card" key={project.id}>
            <div>
              <strong>{project.customer}</strong>
              <span>{project.name}</span>
            </div>
            <Progress value={project.readiness_score} tone={project.risk_level === "critical" ? "risk" : "normal"} />
            <div className="checklist">
              <span className={project.readiness_score >= 75 ? "ok" : ""}>Approved rows: {formatNumber(project.approved_tasks)}</span>
              <span className={project.qa_pass_rate >= 85 ? "ok" : ""}>QA pass: {project.qa_pass_rate}%</span>
              <span className={project.open_flags < 15 ? "ok" : ""}>Open flags: {project.open_flags}</span>
            </div>
            <div className="button-row">
              <button className="icon-button text" onClick={() => downloadProjectExport(project, "jsonl", tasks)}>
                <Download size={16} />
                JSONL
              </button>
              <button className="icon-button text" onClick={() => downloadProjectExport(project, "csv", tasks)}>
                <Download size={16} />
                CSV
              </button>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function ProjectDrawer({ project, onClose }: { project: Project; onClose: () => void }) {
  return (
    <Drawer title={project.customer} onClose={onClose}>
      <div className="drawer-stack">
        <h3>{project.name}</h3>
        <RiskChip risk={project.risk_level} />
        <dl>
          <div><dt>Domain</dt><dd>{titleCase(project.domain)}</dd></div>
          <div><dt>Task type</dt><dd>{titleCase(project.task_type)}</dd></div>
          <div><dt>Required expertise</dt><dd>{project.required_expertise}</dd></div>
          <div><dt>Target size</dt><dd>{formatNumber(project.target_dataset_size)}</dd></div>
          <div><dt>Approved tasks</dt><dd>{formatNumber(project.approved_tasks)}</dd></div>
          <div><dt>Quality threshold</dt><dd>{project.quality_threshold}</dd></div>
          <div><dt>Delivery format</dt><dd>{project.delivery_format}</dd></div>
          <div><dt>Deadline</dt><dd>{new Date(project.deadline).toLocaleDateString()}</dd></div>
        </dl>
        <Progress value={project.readiness_score} />
      </div>
    </Drawer>
  );
}

function TaskDrawer({ task, onClose }: { task: EvaluationTask; onClose: () => void }) {
  return (
    <Drawer title={task.id} onClose={onClose}>
      <div className="drawer-stack">
        <StatusChip label={task.status} tone={task.status === "rejected" ? "danger" : "neutral"} />
        <h3>{task.project_name}</h3>
        <p className="prompt-block">{task.prompt}</p>
        <p className="response-block">{task.model_response}</p>
        <dl>
          <div><dt>Human rating</dt><dd>{task.human_rating ?? "missing"}</dd></div>
          <div><dt>Rubric score</dt><dd>{task.rubric_score ?? "n/a"}</dd></div>
          <div><dt>QA status</dt><dd>{task.qa_status}</dd></div>
          <div><dt>Contributor</dt><dd>{task.assigned_contributor}</dd></div>
          <div><dt>Reviewer</dt><dd>{task.reviewer}</dd></div>
          <div><dt>QA flags</dt><dd>{task.qa_flag_count}</dd></div>
        </dl>
        <p className="response-block">{task.reviewer_comments}</p>
      </div>
    </Drawer>
  );
}

function Drawer({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" onClick={(event) => event.stopPropagation()}>
        <div className="drawer-head">
          <span>{title}</span>
          <button className="icon-button" onClick={onClose} aria-label="Close drawer">
            <XCircle size={18} />
          </button>
        </div>
        {children}
      </aside>
    </div>
  );
}

function KpiCard({
  label,
  value,
  icon: Icon,
  accent
}: {
  label: string;
  value: string | number;
  icon: typeof LayoutDashboard;
  accent: string;
}) {
  return (
    <div className={`kpi-card ${accent}`}>
      <div className="kpi-icon"><Icon size={18} /></div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Panel({ title, action, children }: { title: string; action?: string; children: ReactNode }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{title}</h2>
        {action && <span>{action}</span>}
      </div>
      {children}
    </section>
  );
}

function MiniList({ title, rows }: { title: string; rows: Contributor[] }) {
  return (
    <Panel title={title} action={`${rows.length} tracked`}>
      <div className="mini-list">
        {rows.slice(0, 6).map((row) => (
          <div className="mini-row" key={row.id}>
            <div>
              <strong>{row.name}</strong>
              <span>{row.domain_expertise}</span>
            </div>
            <em>{row.average_rubric_score}</em>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function SortHeader<T extends object>({
  label,
  column,
  sort,
  onSort
}: {
  label: string;
  column: keyof T;
  sort: { key: keyof T; direction: SortDirection };
  onSort: (sort: { key: keyof T; direction: SortDirection }) => void;
}) {
  const active = sort.key === column;
  return (
    <th>
      <button
        className={`sort-button ${active ? "active" : ""}`}
        onClick={() => onSort({ key: column, direction: active && sort.direction === "asc" ? "desc" : "asc" })}
      >
        {label}
        <ArrowDownAZ size={13} />
      </button>
    </th>
  );
}

function Progress({ value, tone = "normal" }: { value: number; tone?: "normal" | "risk" }) {
  return (
    <div className={`progress ${tone}`}>
      <span style={{ width: `${Math.min(Math.max(value, 0), 100)}%` }} />
      <em>{Math.round(value)}%</em>
    </div>
  );
}

function StatusChip({ label, tone }: { label: string; tone: "success" | "warning" | "danger" | "neutral" }) {
  return <span className={`chip ${tone}`}>{titleCase(label)}</span>;
}

function RiskChip({ risk }: { risk: string }) {
  return (
    <span className="risk-chip" style={{ borderColor: riskColors[risk], color: riskColors[risk] }}>
      {titleCase(risk)}
    </span>
  );
}

function SeverityChip({ severity }: { severity: string }) {
  return <span className={`severity ${severity}`}>{titleCase(severity)}</span>;
}

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ name: string; value: number }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <strong>{titleCase(String(label || payload[0].name))}</strong>
      {payload.map((item) => (
        <span key={item.name}>{item.name}: {formatNumber(Number(item.value))}</span>
      ))}
    </div>
  );
}

function sortRows<T extends Record<string, unknown>>(rows: T[], key: keyof T, direction: SortDirection): T[] {
  return [...rows].sort((a, b) => {
    const aValue = a[key];
    const bValue = b[key];
    const result =
      typeof aValue === "number" && typeof bValue === "number"
        ? aValue - bValue
        : String(aValue ?? "").localeCompare(String(bValue ?? ""));
    return direction === "asc" ? result : -result;
  });
}

function titleCase(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter: string) => letter.toUpperCase());
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-US").format(value);
}

export default App;
