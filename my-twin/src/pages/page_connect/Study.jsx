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
    <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-800">
      <div
        className={`h-full rounded-full bg-gradient-to-r ${color}`}
        style={{ width: `${value}%` }}
      />
    </div>
  );
}

export default function Study() {
  return (
    <div className=" w-full min-w-0 gap-4 text-white sm:gap-5">
      <section className="overflow-hidden rounded-2xl border border-slate-800 bg-[radial-gradient(circle_at_top_left,_rgba(34,211,238,0.18),_transparent_28%),linear-gradient(135deg,_#0f172a_0%,_#111827_55%,_#020617_100%)] p-4 shadow-[0_24px_80px_rgba(2,6,23,0.45)] sm:p-6">
        <div className=" min-w-0 flex-col gap-5 xl:items-end xl:justify-between">
          <div className="max-w-[480px]">
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-cyan-200">
              <School sx={{ fontSize: 16 }} />
              Study Hub
            </div>
            <h1 className="text-3xl font-black tracking-tight text-white sm:text-4xl">
              Keep courses, deadlines, and momentum in one place.
            </h1>
            <p className="mt-3 max-w-xl text-sm leading-6 text-slate-300 sm:text-base">
              A focused academic dashboard for tracking active modules,
              assignment pressure, revision rhythm, and progress across your
              study week.
            </p>
          </div>

          <div className="grid w-full min-w-[200px] grid-cols-1 gap-3 sm:grid-cols-2 xl:max-w-[520px]">
            {studyStats.map(({ label, value, note, icon: Icon, tone }) => (
              <article
                key={label}
                className="min-w-0 rounded-2xl border border-white/10 bg-white/5 p-3 sm:p-4 backdrop-blur-sm"
              >
                <div className={`mb-3 ${tone}`}>
                  <Icon />
                </div>
                <div className="text-2xl font-bold text-white">{value}</div>
                <div className="mt-1 text-sm font-semibold text-slate-200">
                  {label}
                </div>
                <div className="mt-1 text-xs leading-5 text-slate-400">
                  {note}
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.45fr)_minmax(0,0.95fr)] xl:gap-4">
        <div className="grid min-w-0 gap-4 xl:gap-5">
          <article className="min-w-0 rounded-2xl border border-slate-800 bg-slate-900/80 p-2 sm:p-5">
            <div className="mb-5 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-white">Current Courses</h2>
                <p className="text-sm text-slate-400">
                  Track learning progress across active modules.
                </p>
              </div>
              <div className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300">
                3 active
              </div>
            </div>

            <div className="grid gap-4">
              {courses.map((course) => (
                <div
                  key={course.title}
                  className="min-w-0 rounded-2xl border border-slate-800 bg-slate-950/70 p-4"
                >
                  <div className="mb-3 flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="truncate text-base font-semibold text-white sm:text-lg">
                        {course.title}
                      </div>
                      <div className="truncate text-sm text-slate-400">
                        {course.provider}
                      </div>
                    </div>
                    <div className="shrink-0 text-right text-sm text-slate-300">
                      <div className="font-semibold">{course.progress}%</div>
                      <div className="text-xs text-slate-500">
                        {course.lessonsLeft} lessons left
                      </div>
                    </div>
                  </div>
                  <ProgressBar value={course.progress} color={course.color} />
                </div>
              ))}
            </div>
          </article>

          <article className="min-w-0 rounded-2xl border border-slate-800 bg-slate-900/80 p-4 sm:p-5">
            <div className="mb-5 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-white">Assignments</h2>
                <p className="text-sm text-slate-400">
                  Prioritize what needs attention next.
                </p>
              </div>
              <div className="rounded-full border border-amber-500/20 bg-amber-500/10 px-3 py-1 text-xs font-semibold text-amber-200">
                1 due today
              </div>
            </div>

            <div className="grid gap-2">
              {assignments.map((assignment) => (
                <div
                  key={assignment.title}
                  className="flex min-w-0 flex-col gap-3 rounded-2xl border border-slate-800 bg-slate-950/70 p-2 lg:flex-row lg:items-center lg:justify-between"
                >
                  <div className="min-w-0">
                    <div className="text-base font-semibold text-white">
                      {assignment.title}
                    </div>
                    <div className="text-sm text-slate-400">
                      {assignment.course}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 lg:justify-end">
                    <div className="text-sm text-slate-300 lg:text-right">
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
          <article className="min-w-0 rounded-2xl border border-slate-800 bg-slate-900/80 p-3 sm:p-5">
            <div className="mb-4 flex items-center gap-2">
              <PlayCircleFilled className="text-cyan-300" />
              <h2 className="text-xl font-bold text-white">Today&apos;s Plan</h2>
            </div>
            <div className="grid gap-3">
              {studyPlan.map((item) => (
                <div
                  key={item.time}
                  className="min-w-0 rounded-2xl border border-slate-800 bg-slate-950/70 p-4"
                >
                  <div className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-300">
                    {item.time}
                  </div>
                  <div className="mt-2 text-base font-semibold text-white">
                    {item.title}
                  </div>
                  <div className="mt-1 text-sm leading-6 text-slate-400">
                    {item.detail}
                  </div>
                </div>
              ))}
            </div>
          </article>

          <article className="min-w-0 rounded-2xl border border-slate-800 bg-slate-900/80 p-2 sm:p-5">
            <div className="mb-4 flex items-center gap-2">
              <MenuBook className="text-emerald-300" />
              <h2 className="text-xl font-bold text-white">Study Resources</h2>
            </div>
            <div className="grid gap-3">
              {resources.map((resource) => (
                <div
                  key={resource}
                  className="flex min-w-0 items-center gap-3 rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3 text-sm text-slate-300"
                >
                  <CheckCircle className="text-emerald-300" sx={{ fontSize: 18 }} />
                  <span className="min-w-0">{resource}</span>
                </div>
              ))}
            </div>
          </article>

          <article className="min-w-0 rounded-2xl border border-slate-800 bg-slate-900/80 p-4 sm:p-5">
            <div className="mb-4 flex items-center gap-2">
              <AutoStories className="text-amber-300" />
              <h2 className="text-xl font-bold text-white">Weekly Momentum</h2>
            </div>
            <div className="min-w-0 rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="text-slate-400">Goal completion</span>
                <span className="font-semibold text-white">74%</span>
              </div>
              <ProgressBar value={74} color="from-amber-400 to-orange-500" />
              <div className="mt-4 grid grid-cols-1 gap-3 text-center sm:grid-cols-3">
                <div className="rounded-xl bg-slate-900 px-3 py-3">
                  <div className="text-lg font-bold text-white">5</div>
                  <div className="text-xs text-slate-400">Study streak</div>
                </div>
                <div className="rounded-xl bg-slate-900 px-3 py-3">
                  <div className="text-lg font-bold text-white">9</div>
                  <div className="text-xs text-slate-400">Topics revised</div>
                </div>
                <div className="rounded-xl bg-slate-900 px-3 py-3">
                  <div className="text-lg font-bold text-white">2</div>
                  <div className="text-xs text-slate-400">Quizzes left</div>
                </div>
              </div>
            </div>
          </article>
        </div>
      </section>
    </div>
  );
}
