import React from "react";
import {
  AccessTime,
  AutoStories,
  CheckCircle,
  EmojiEvents,
  MenuBook,
  PlayCircleFilled,
  School,
  TaskAlt,
  TrendingUp,
} from "@mui/icons-material";

const studyStats = [
  {
    label: "Weekly Focus",
    value: "18.5h",
    note: "3.5h ahead of target",
    icon: AccessTime,
    tone: "text-cyan-300",
  },
  {
    label: "Assignments Done",
    value: "12/15",
    note: "80% completion this week",
    icon: TaskAlt,
    tone: "text-emerald-300",
  },
  {
    label: "Average Score",
    value: "91%",
    note: "Up 6% from last month",
    icon: TrendingUp,
    tone: "text-amber-300",
  },
  {
    label: "Milestones",
    value: "4",
    note: "Certificates and streak goals",
    icon: EmojiEvents,
    tone: "text-rose-300",
  },
];

const courses = [
  {
    title: "Frontend Engineering",
    provider: "React + UI Systems",
    progress: 72,
    lessonsLeft: 6,
    color: "from-cyan-500 to-blue-500",
  },
  {
    title: "Data Structures",
    provider: "Algorithms Track",
    progress: 58,
    lessonsLeft: 11,
    color: "from-emerald-500 to-teal-500",
  },
  {
    title: "Machine Learning Basics",
    provider: "Python Lab",
    progress: 36,
    lessonsLeft: 14,
    color: "from-orange-500 to-amber-500",
  },
];

const assignments = [
  {
    title: "React dashboard refactor",
    course: "Frontend Engineering",
    due: "Today, 18:00",
    status: "In progress",
    statusClass: "bg-amber-500/15 text-amber-200 border-amber-400/30",
  },
  {
    title: "Binary tree exercises",
    course: "Data Structures",
    due: "Tomorrow, 12:00",
    status: "Needs review",
    statusClass: "bg-cyan-500/15 text-cyan-200 border-cyan-400/30",
  },
  {
    title: "Linear regression quiz",
    course: "Machine Learning Basics",
    due: "Fri, 09:00",
    status: "Ready to submit",
    statusClass: "bg-emerald-500/15 text-emerald-200 border-emerald-400/30",
  },
];

const studyPlan = [
  {
    time: "08:00 - 09:30",
    title: "Deep work: React module",
    detail: "Finish state management lecture and notes.",
  },
  {
    time: "13:00 - 14:00",
    title: "Practice session",
    detail: "Solve 3 graph questions and review errors.",
  },
  {
    time: "19:30 - 20:15",
    title: "Revision block",
    detail: "Summarize ML formulas and flash cards.",
  },
];

const resources = [
  "Lecture notes synced and organized",
  "Flash cards reviewed: 48 cards",
  "Mock exam scheduled for Saturday",
  "Reading list trimmed to 3 priority chapters",
];

function ProgressBar({ value, color }) {
  return (
    <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
      <div
        className={`h-full rounded-full bg-gradient-to-r ${color}`}
        style={{ width: `${value}%` }}
      />
    </div>
  );
}

export default function Study() {
  return (
    <div className="flex w-full min-w-0 flex-col gap-4 text-foreground sm:gap-5">
      <section className="glass-strong overflow-hidden rounded-2xl border border-border bg-gradient-aurora p-4 sm:p-6">
        <div className="flex min-w-0 flex-col gap-5 xl:items-end xl:justify-between">
          <div className="max-w-[480px]">
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-border bg-secondary px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-primary">
              <School sx={{ fontSize: 16 }} />
              Study Hub
            </div>
            <h1 className="text-3xl font-black tracking-tight text-gradient sm:text-4xl">
              Keep courses, deadlines, and momentum in one place.
            </h1>
            <p className="mt-3 max-w-xl text-sm leading-6 text-muted-foreground sm:text-base">
              A focused academic dashboard for tracking active modules,
              assignment pressure, revision rhythm, and progress across your
              study week.
            </p>
          </div>

          <div className="grid w-full min-w-[200px] grid-cols-1 gap-3 sm:grid-cols-2 xl:max-w-[520px]">
            {studyStats.map(({ label, value, note, icon: Icon, tone }) => (
              <article key={label} className="glass min-w-0 rounded-2xl border border-border p-3 sm:p-4">
                <div className={`mb-3 ${tone}`}>
                  <Icon />
                </div>
                <div className="text-2xl font-bold text-card-foreground">{value}</div>
                <div className="mt-1 text-sm font-semibold text-card-foreground">
                  {label}
                </div>
                <div className="mt-1 text-xs leading-5 text-muted-foreground">
                  {note}
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.45fr)_minmax(0,0.95fr)] xl:gap-4">
        <div className="grid min-w-0 gap-4 xl:gap-5">
          <article className="glass min-w-0 rounded-2xl border border-border p-2 sm:p-5">
            <div className="mb-5 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-card-foreground">Current Courses</h2>
                <p className="text-sm text-muted-foreground">
                  Track learning progress across active modules.
                </p>
              </div>
              <div className="rounded-full border border-border bg-secondary px-3 py-1 text-xs text-muted-foreground">
                3 active
              </div>
            </div>

            <div className="grid gap-4">
              {courses.map((course) => (
                <div
                  key={course.title}
                  className="min-w-0 rounded-2xl border border-border bg-card p-4"
                >
                  <div className="mb-3 flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="truncate text-base font-semibold text-card-foreground sm:text-lg">
                        {course.title}
                      </div>
                      <div className="truncate text-sm text-muted-foreground">
                        {course.provider}
                      </div>
                    </div>
                    <div className="shrink-0 text-right text-sm text-muted-foreground">
                      <div className="font-semibold">{course.progress}%</div>
                      <div className="text-xs text-muted-foreground">
                        {course.lessonsLeft} lessons left
                      </div>
                    </div>
                  </div>
                  <ProgressBar value={course.progress} color={course.color} />
                </div>
              ))}
            </div>
          </article>

          <article className="glass min-w-0 rounded-2xl border border-border p-4 sm:p-5">
            <div className="mb-5 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-card-foreground">Assignments</h2>
                <p className="text-sm text-muted-foreground">
                  Prioritize what needs attention next.
                </p>
              </div>
              <div className="rounded-full border border-warning/30 bg-warning/10 px-3 py-1 text-xs font-semibold text-warning">
                1 due today
              </div>
            </div>

            <div className="grid gap-2">
              {assignments.map((assignment) => (
                <div
                  key={assignment.title}
                  className="flex min-w-0 flex-col gap-3 rounded-2xl border border-border bg-card p-2 lg:flex-row lg:items-center lg:justify-between"
                >
                  <div className="min-w-0">
                    <div className="text-base font-semibold text-card-foreground">
                      {assignment.title}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {assignment.course}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 lg:justify-end">
                    <div className="text-sm text-muted-foreground lg:text-right">
                      <div>{assignment.due}</div>
                    </div>
                    <span
                      className={`rounded-full border px-3 py-1 text-xs font-semibold ${assignment.statusClass}`}
                    >
                      {assignment.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </article>
        </div>

        <div className="grid min-w-0 gap-4 xl:gap-3">
          <article className="glass min-w-0 rounded-2xl border border-border p-3 sm:p-5">
            <div className="mb-4 flex items-center gap-2">
              <PlayCircleFilled className="text-primary" />
              <h2 className="text-xl font-bold text-card-foreground">Today&apos;s Plan</h2>
            </div>
            <div className="grid gap-3">
              {studyPlan.map((item) => (
                <div
                  key={item.time}
                  className="min-w-0 rounded-2xl border border-border bg-card p-4"
                >
                  <div className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">
                    {item.time}
                  </div>
                  <div className="mt-2 text-base font-semibold text-card-foreground">
                    {item.title}
                  </div>
                  <div className="mt-1 text-sm leading-6 text-muted-foreground">
                    {item.detail}
                  </div>
                </div>
              ))}
            </div>
          </article>

          <article className="glass min-w-0 rounded-2xl border border-border p-2 sm:p-5">
            <div className="mb-4 flex items-center gap-2">
              <MenuBook className="text-success" />
              <h2 className="text-xl font-bold text-card-foreground">Study Resources</h2>
            </div>
            <div className="grid gap-3">
              {resources.map((resource) => (
                <div
                  key={resource}
                  className="flex min-w-0 items-center gap-3 rounded-2xl border border-border bg-card px-4 py-3 text-sm text-muted-foreground"
                >
                  <CheckCircle className="text-success" sx={{ fontSize: 18 }} />
                  <span className="min-w-0">{resource}</span>
                </div>
              ))}
            </div>
          </article>

          <article className="glass min-w-0 rounded-2xl border border-border p-4 sm:p-5">
            <div className="mb-4 flex items-center gap-2">
              <AutoStories className="text-warning" />
              <h2 className="text-xl font-bold text-card-foreground">Weekly Momentum</h2>
            </div>
            <div className="min-w-0 rounded-2xl border border-border bg-card p-4">
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Goal completion</span>
                <span className="font-semibold text-card-foreground">74%</span>
              </div>
              <ProgressBar value={74} color="from-amber-400 to-orange-500" />
              <div className="mt-4 grid grid-cols-1 gap-3 text-center sm:grid-cols-3">
                <div className="rounded-xl bg-secondary px-3 py-3">
                  <div className="text-lg font-bold text-card-foreground">5</div>
                  <div className="text-xs text-muted-foreground">Study streak</div>
                </div>
                <div className="rounded-xl bg-secondary px-3 py-3">
                  <div className="text-lg font-bold text-card-foreground">9</div>
                  <div className="text-xs text-muted-foreground">Topics revised</div>
                </div>
                <div className="rounded-xl bg-secondary px-3 py-3">
                  <div className="text-lg font-bold text-card-foreground">2</div>
                  <div className="text-xs text-muted-foreground">Quizzes left</div>
                </div>
              </div>
            </div>
          </article>
        </div>
      </section>
    </div>
  );
}
