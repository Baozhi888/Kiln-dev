import { writable, get } from "svelte/store"
import { api_error_handler, createKilnError } from "./utils/error_handlers"

export type ProjectInfo = {
  name: string
  description: string
  path: string
  created_at: Date
  created_by: string
}

export type AllProjects = {
  projects: ProjectInfo[]
  error: string | null
}

export type Task = {
  id: string
  name: string
  description: string
  path: string
  created_at: Date
  created_by: string
}

// UI State stored in the browser. For more client centric state
export type UIState = {
  current_project_path: string | null
  current_task_id: string | null
}

export const default_ui_state: UIState = {
  current_project_path: null,
  current_task_id: null,
}

// Private, used to store the path of the current project, and task ID
export const ui_state = localStorageStore("ui_state", default_ui_state)

// These stores store nice structured data. They are auto-updating based on the ui_state and server calls to load data
export const projects = writable<AllProjects | null>(null)
export const current_project = writable<ProjectInfo | null>(null)
export const current_task = writable<Task | null>(null)

let previous_ui_state: UIState = default_ui_state

// Live update the structured data stores based on the ui_state
ui_state.subscribe((state) => {
  if (state.current_project_path != previous_ui_state.current_project_path) {
    current_project.set(get_current_project())
  }
  if (state.current_task_id != previous_ui_state.current_task_id) {
    load_current_task(get(current_project))
  }
  previous_ui_state = { ...state }
})

projects.subscribe((all_projects) => {
  if (all_projects) {
    current_project.set(get_current_project())
    load_current_task(get(current_project))
  }
})

function get_current_project(): ProjectInfo | null {
  const all_projects = get(projects)

  if (!all_projects) {
    return null
  }
  const current_project_path = get(ui_state).current_project_path
  if (!current_project_path) {
    return null
  }
  const project = all_projects.projects.find(
    (project) => project.path === current_project_path,
  )
  if (!project) {
    return null
  }
  return project
}

export async function load_projects() {
  try {
    const response = await fetch("http://localhost:8757/api/projects")
    const data = await response.json()
    api_error_handler(response, data)

    const all_projects: AllProjects = {
      projects: data,
      error: null,
    }
    projects.set(all_projects)
  } catch (error: unknown) {
    const all_projects: AllProjects = {
      projects: [],
      error: "Issue loading projects. " + createKilnError(error).getMessage(),
    }
    projects.set(all_projects)
  }
}

// Custom function to create a localStorage-backed store
function localStorageStore<T>(key: string, initialValue: T) {
  // Check if localStorage is available
  const isBrowser = typeof window !== "undefined" && window.localStorage

  // Get stored value from localStorage or use initial value
  const storedValue = isBrowser
    ? JSON.parse(localStorage.getItem(key) || "null")
    : null
  const store = writable(storedValue !== null ? storedValue : initialValue)

  if (isBrowser) {
    // Subscribe to changes and update localStorage
    store.subscribe((value) => localStorage.setItem(key, JSON.stringify(value)))
  }

  return store
}

export async function load_current_task(project: ProjectInfo | null) {
  let task: Task | null = null
  try {
    const task_id = get(ui_state).current_task_id
    if (!project || !task_id) {
      return
    }
    const urlPath = encodeURIComponent(project.path)
    const response = await fetch(
      `http://localhost:8757/api/tasks?project_path=${urlPath}`,
    )
    const data = await response.json()
    api_error_handler(response, data)
    task = data.find((t: Task) => t.id === task_id)
  } catch (error: unknown) {
    // Can't load this task, likely deleted. Clear the ID, which will force the user to select a new task
    task = null
    ui_state.set({
      ...get(ui_state),
      current_task_id: null,
    })
  } finally {
    current_task.set(task)
  }
}
