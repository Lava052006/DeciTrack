"use client";

import { useMemo, useState } from "react";

type Task = { id: number; title: string; owner: string; initials: string; color: string; priority: "High" | "Medium" | "Low"; status: "In progress" | "To do" | "Done"; due: string; project: string };

const initialTasks: Task[] = [
  { id: 1, title: "Finalize Q3 campaign brief", owner: "Maya Chen", initials: "MC", color: "coral", priority: "High", status: "In progress", due: "Today", project: "Brand refresh" },
  { id: 2, title: "Review onboarding flow with design", owner: "Jordan Lee", initials: "JL", color: "blue", priority: "High", status: "To do", due: "Today", project: "Product launch" },
  { id: 3, title: "Send revised pricing to Alex", owner: "Priya Shah", initials: "PS", color: "gold", priority: "Medium", status: "In progress", due: "Oct 22", project: "Partnerships" },
  { id: 4, title: "Prepare customer interview notes", owner: "Sam Rivera", initials: "SR", color: "green", priority: "Medium", status: "Done", due: "Oct 21", project: "Product launch" },
  { id: 5, title: "Share launch timeline with team", owner: "Maya Chen", initials: "MC", color: "coral", priority: "Low", status: "To do", due: "Oct 24", project: "Product launch" },
  { id: 6, title: "Book a follow-up with Northstar", owner: "Jordan Lee", initials: "JL", color: "blue", priority: "Medium", status: "In progress", due: "Oct 25", project: "Partnerships" },
];

const meetings = [
  { day: "21", month: "OCT", title: "Monday team sync", time: "10:00 – 10:30 AM", people: "Maya, Jordan, Priya +2", color: "violet", tag: "6 decisions", note: "Maya owns the Q3 campaign brief, due Friday." },
  { day: "21", month: "OCT", title: "Product launch review", time: "1:30 – 2:15 PM", people: "Jordan, Sam +3", color: "blue", tag: "4 decisions", note: "Jordan to review onboarding with design before Thursday." },
  { day: "22", month: "OCT", title: "Northstar partnership call", time: "11:00 – 11:45 AM", people: "Priya, Alex +1", color: "orange", tag: "3 decisions", note: "Priya will send the updated pricing proposal to Alex." },
];

function Icon({ name, size = 18 }: { name: string; size?: number }) {
  const common = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.7, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  const paths: Record<string, React.ReactNode> = {
    grid: <><rect x="3" y="3" width="8" height="8" rx="2"/><rect x="13" y="3" width="8" height="5" rx="2"/><rect x="13" y="10" width="8" height="11" rx="2"/><rect x="3" y="13" width="8" height="8" rx="2"/></>,
    check: <><path d="M20 7 10 17l-5-5"/><path d="M20 12v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9"/></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/></>,
    mic: <><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2m-7 9v3m-4 0h8"/></>,
    search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
    plus: <path d="M12 5v14m-7-7h14"/>,
    arrow: <><path d="M7 17 17 7M7 7h10v10"/></>,
    spark: <><path d="m12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-2-5.8L4 11l6-2.2L12 3Z"/><path d="m19 14 .9 2.1L22 17l-2.1.9L19 20l-.9-2.1L16 17l2.1-.9L19 14Z"/></>,
    dots: <><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></>,
    chevron: <path d="m9 18 6-6-6-6"/>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9m-8 13h4"/></>,
    filter: <><path d="M4 7h16M7 12h10m-7 5h4"/><circle cx="8" cy="7" r="1" fill="currentColor"/><circle cx="14" cy="12" r="1" fill="currentColor"/></>,
  };
  return <svg {...common} aria-hidden="true">{paths[name] ?? paths.grid}</svg>;
}

function Avatar({ initials, color, small = false }: { initials: string; color: string; small?: boolean }) {
  return <span className={`avatar avatar-${color} ${small ? "avatar-small" : ""}`}>{initials}</span>;
}

export default function Home() {
  const [active, setActive] = useState("Overview");
  const [tasks, setTasks] = useState(initialTasks);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All tasks");
  const [showCapture, setShowCapture] = useState(false);
  const [capture, setCapture] = useState("");
  const [toast, setToast] = useState("");
  const filtered = useMemo(() => tasks.filter((task) => (filter === "All tasks" || task.status === filter) && `${task.title} ${task.owner} ${task.project}`.toLowerCase().includes(query.toLowerCase())), [tasks, filter, query]);
  const completed = tasks.filter((task) => task.status === "Done").length;
  const showToast = (message: string) => { setToast(message); window.setTimeout(() => setToast(""), 2600); };
  const addTask = () => {
    if (!capture.trim()) return;
    setTasks((current) => [{ id: Date.now(), title: capture.trim(), owner: "You", initials: "YO", color: "violet", priority: "Medium", status: "To do", due: "Tomorrow", project: "Product launch" }, ...current]);
    setCapture(""); setShowCapture(false); setActive("Tasks"); showToast("Task added to Product launch");
  };
  const toggleStatus = (id: number) => setTasks((current) => current.map((task) => task.id === id ? { ...task, status: task.status === "Done" ? "To do" : "Done" } : task));

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#home" onClick={() => setActive("Overview")}><span className="brand-mark"><span/><span/><span/><span/></span><span>decitrack</span></a>
        <button className="workspace-switch"><span className="workspace-icon">N</span><span className="workspace-copy"><strong>Northstar Studio</strong><small>Free plan</small></span><span className="switch-chev">⌄</span></button>
        <button className="search-box" onClick={() => document.getElementById("task-search")?.focus()}><Icon name="search" size={16}/><span>Search anything...</span><kbd>⌘ K</kbd></button>
        <div className="nav-label">WORKSPACE</div>
        <nav className="primary-nav">
          {[{ name: "Overview", icon: "grid" }, { name: "My tasks", icon: "check" }, { name: "Meetings", icon: "calendar" }, { name: "Capture", icon: "mic" }].map((item) => <button key={item.name} className={`nav-item ${active === item.name || (item.name === "My tasks" && active === "Tasks") ? "nav-active" : ""}`} onClick={() => item.name === "Capture" ? setShowCapture(true) : setActive(item.name === "My tasks" ? "Tasks" : item.name)}><Icon name={item.icon}/><span>{item.name}</span>{item.name === "My tasks" && <span className="nav-count">{tasks.filter((t) => t.status !== "Done").length}</span>}</button>)}
        </nav>
        <div className="nav-label project-label">YOUR PROJECTS <button onClick={() => showToast("Project creation is part of this Demo Mode")}><Icon name="plus" size={15}/></button></div>
        <div className="project-list"><button className="project-item selected" onClick={() => setActive("Overview")}><span className="project-dot dot-purple"/>Product launch</button><button className="project-item" onClick={() => setActive("Overview")}><span className="project-dot dot-orange"/>Brand refresh</button><button className="project-item" onClick={() => setActive("Overview")}><span className="project-dot dot-blue"/>Partnerships</button></div>
        <div className="sidebar-bottom"><div className="upgrade-card"><span className="upgrade-spark"><Icon name="spark" size={16}/></span><strong>Make room for big ideas.</strong><p>Upgrade to unlock unlimited projects and more.</p><button onClick={() => showToast("You're exploring DeciTrack Demo Mode")}>Explore plans <Icon name="arrow" size={13}/></button></div><button className="profile-button"><Avatar initials="MC" color="coral"/><span className="profile-copy"><strong>Maya Chen</strong><small>maya@northstar.co</small></span><Icon name="dots" size={16}/></button></div>
      </aside>

      <section className="main-panel">
        <header className="topbar"><div className="breadcrumbs"><span>Northstar Studio</span><Icon name="chevron" size={14}/><strong>{active === "Tasks" ? "My tasks" : active}</strong></div><div className="top-actions"><span className="mode-pill"><span className="live-dot"/>Demo Mode</span><button className="icon-button" aria-label="Notifications" onClick={() => showToast("You’re all caught up!")}><Icon name="bell"/><i/></button><button className="help-button" onClick={() => showToast("Tip: add a task or explore a meeting recap")}><span>?</span> Help</button></div></header>
        <div className="content">
          <div className="greeting-row"><div><div className="eyebrow">MONDAY, OCTOBER 21, 2024 <span className="sun-icon">☀</span></div><h1>{active === "Tasks" ? "Your tasks" : active === "Meetings" ? "Your meetings" : "A clear view of what matters."}</h1><p className="subtitle">{active === "Tasks" ? "The little things that move the big things forward." : active === "Meetings" ? "Good conversations, captured and ready to act on." : "Good morning, Maya. Here’s where your team is headed."}</p></div><button className="primary-button" onClick={() => { setShowCapture(true); setCapture(""); }}><Icon name="plus" size={17}/> Capture a thought <kbd>⌘ J</kbd></button></div>

          <div className="stats-grid"><article className="stat-card"><div className="stat-top"><span>Open tasks</span><span className="stat-icon purple-soft"><Icon name="check" size={17}/></span></div><div className="stat-number">{tasks.filter((task) => task.status !== "Done").length}<span className="stat-trend">↗ 3 this week</span></div><div className="stat-foot">Across <strong>3 projects</strong></div></article><article className="stat-card"><div className="stat-top"><span>Meetings this week</span><span className="stat-icon blue-soft"><Icon name="calendar" size={17}/></span></div><div className="stat-number">8<span className="stat-trend muted-trend">2 today</span></div><div className="stat-foot">Next up at <strong>10:00 AM</strong></div></article><article className="stat-card progress-stat"><div className="stat-top"><span>Team progress</span><span className="stat-icon green-soft"><Icon name="arrow" size={17}/></span></div><div className="stat-number">{Math.round(completed / tasks.length * 100)}%<span className="stat-trend">↗ 12% this month</span></div><div className="progress-track"><span style={{ width: `${Math.round(completed / tasks.length * 100)}%` }}/></div></article><article className="stat-card focus-card"><div className="stat-top"><span>AI daily brief</span><span className="demo-mini"><Icon name="spark" size={12}/> DEMO</span></div><div className="focus-text">Your team is in a good rhythm.</div><div className="stat-foot">Two decisions need your attention today.</div><button className="text-link" onClick={() => showToast("AI summary generated from simulated team data")}>Read your brief <Icon name="arrow" size={13}/></button></article></div>

          <div className="dashboard-grid"><section className="panel tasks-panel"><div className="panel-heading"><div><div className="title-line"><h2>Tasks to keep things moving</h2><span className="count-chip">{filtered.length}</span></div><p>A little progress adds up.</p></div><button className="more-button" aria-label="Task options" onClick={() => showToast("Showing tasks across all projects")}><Icon name="dots"/></button></div><div className="task-controls"><div className="task-search"><Icon name="search" size={15}/><input id="task-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Find a task..."/></div><label className="filter-select"><Icon name="filter" size={15}/><select value={filter} onChange={(event) => setFilter(event.target.value)}><option>All tasks</option><option>To do</option><option>In progress</option><option>Done</option></select></label><button className="add-task-button" onClick={() => { setShowCapture(true); setCapture(""); }}><Icon name="plus" size={16}/></button></div>
            <div className="task-list">{filtered.length ? filtered.slice(0, 5).map((task) => <div className="task-row" key={task.id}><button className={`task-check ${task.status === "Done" ? "checked" : ""}`} aria-label={`Mark ${task.title} ${task.status === "Done" ? "to do" : "done"}`} onClick={() => toggleStatus(task.id)}>{task.status === "Done" && <span>✓</span>}</button><div className="task-main"><strong className={task.status === "Done" ? "task-complete" : ""}>{task.title}</strong><small>{task.project}</small></div><span className={`priority priority-${task.priority.toLowerCase()}`}>{task.priority}</span><Avatar initials={task.initials} color={task.color} small/><span className={`task-due ${task.due === "Today" ? "due-today" : ""}`}>{task.due}</span><button className="row-dots" onClick={() => showToast(`${task.title} · ${task.status}`)} aria-label="Task details"><Icon name="dots" size={16}/></button></div>) : <div className="empty-state">No tasks match that search.</div>}</div><button className="view-all" onClick={() => setActive("Tasks")}>View all tasks <Icon name="arrow" size={14}/></button></section>

            <section className="panel meetings-panel"><div className="panel-heading"><div><div className="title-line"><h2>Meeting moments</h2><span className="ai-tag"><Icon name="spark" size={12}/> AI notes</span></div><p>Decisions worth remembering.</p></div><button className="calendar-link" onClick={() => setActive("Meetings")}>This week <span>⌄</span></button></div><div className="meeting-list">{meetings.map((meeting) => <article className="meeting-item" key={meeting.title}><div className={`date-block date-${meeting.color}`}><strong>{meeting.day}</strong><span>{meeting.month}</span></div><div className="meeting-content"><div className="meeting-title-row"><h3>{meeting.title}</h3><button className="row-dots" onClick={() => showToast(`Opening recap: ${meeting.title}`)} aria-label="Meeting details"><Icon name="dots" size={16}/></button></div><div className="meeting-time">{meeting.time} <span>·</span> {meeting.people}</div><div className="meeting-note"><span className="note-star"><Icon name="spark" size={13}/></span><span>{meeting.note}</span></div><div className="meeting-tag">{meeting.tag} captured <span>·</span> <span className="simulated-tag">Simulated AI</span></div></div></article>)}</div><button className="view-all meetings-view" onClick={() => setActive("Meetings")}>See all meetings <Icon name="arrow" size={14}/></button></section></div>

          <section className="integration-banner"><div className="integration-icon"><Icon name="mic" size={21}/></div><div className="integration-copy"><strong>Your meetings, already in motion.</strong><span>Connect your tools to turn conversations into clear next steps.</span></div><div className="integration-logos"><span className="integration-logo wispr">w</span><span className="integration-logo calendar-logo">▦</span><span className="integration-logo slack-logo">✣</span><span className="integrations-caption">Wispr Flow <span>·</span> Google Calendar <span>·</span> Slack</span></div><button className="connect-button" onClick={() => showToast("Integrations are simulated in Demo Mode")}>Explore integrations <Icon name="arrow" size={14}/></button></section>
          <footer className="page-footer"><span>Made for the work between the meetings.</span><span><i/> All changes saved <span className="footer-sep">·</span> Your team, in sync</span></footer>
        </div>
      </section>

      {showCapture && <div className="modal-backdrop" onClick={() => setShowCapture(false)}><section className="capture-modal" onClick={(event) => event.stopPropagation()}><div className="modal-top"><span className="modal-icon"><Icon name="spark" size={18}/></span><button className="modal-close" onClick={() => setShowCapture(false)}>×</button></div><div className="eyebrow">QUICK CAPTURE <span className="demo-mini">DEMO MODE</span></div><h2>Get it out of your head.</h2><p>Turn a thought into a trackable next step.</p><textarea autoFocus value={capture} onChange={(event) => setCapture(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) addTask(); }} placeholder="What needs to get done?"/><div className="modal-meta"><span><span className="project-dot dot-purple"/>Product launch <span className="modal-meta-chevron">⌄</span></span><span>Assigned to Maya <Avatar initials="MC" color="coral" small/></span></div><div className="modal-actions"><span><Icon name="spark" size={14}/> Simulated AI organization</span><button className="primary-button" onClick={addTask}><Icon name="plus" size={16}/> Add to tasks <kbd>⌘ ↵</kbd></button></div></section></div>}
      {toast && <div className="toast"><span>✓</span>{toast}</div>}
    </main>
  );
}
