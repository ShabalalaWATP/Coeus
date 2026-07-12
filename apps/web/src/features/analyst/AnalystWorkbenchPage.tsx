import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import AnalystTaskDetail from "./AnalystTaskDetail";
import { ErrorState, LoadingState } from "../../components/ui/PageState";
import { formatWorkflowState } from "../../lib/workflow/state-format";
import {
  listAnalystTasks,
  type AnalystTask,
  type AnalystTaskList,
} from "../../lib/api-client/analyst";

const EMPTY_TASKS: AnalystTaskList = { tasks: [] };

export default function AnalystWorkbenchPage() {
  const { taskId } = useParams();
  const queryClient = useQueryClient();
  const tasksQuery = useQuery({
    queryKey: ["analyst-tasks"],
    queryFn: listAnalystTasks,
    initialData: EMPTY_TASKS,
    initialDataUpdatedAt: 0,
  });
  const tasks = tasksQuery.data.tasks;
  const requestedTask = tasks.find((task) => task.ticketId === taskId);
  const requestedMissing =
    taskId !== undefined &&
    requestedTask === undefined &&
    !tasksQuery.isFetching &&
    !tasksQuery.isError;
  const selectedTask = requestedMissing ? undefined : (requestedTask ?? tasks[0]);
  const updateTask = (task: AnalystTask) => {
    queryClient.setQueryData<AnalystTaskList>(["analyst-tasks"], (current) => ({
      tasks: replaceTask(current?.tasks ?? [], task),
    }));
  };

  return (
    <div className="analyst-page">
      <section className="overview-hero" aria-labelledby="analyst-title">
        <div>
          <h1 id="analyst-title">Analyst Workbench</h1>
          <p>Assigned task production and manager review.</p>
        </div>
        <div className="classification-note">MOCK DATA ONLY</div>
      </section>
      {requestedMissing ? (
        <p className="workspace-alert" role="alert">
          The requested task was not found or is no longer assigned to you.{" "}
          <Link to="/analyst/workbench">Back to your task list</Link>
        </p>
      ) : null}
      <section className="analyst-grid">
        <aside className="surface analyst-list" aria-label="Assigned tasks">
          <div className="section-heading">
            <h2>Assigned tasks</h2>
            <p>{tasks.length} tasks in your queue.</p>
          </div>
          {tasksQuery.isError ? (
            <ErrorState onRetry={() => void tasksQuery.refetch()} />
          ) : tasksQuery.isFetching && tasksQuery.dataUpdatedAt === 0 ? (
            <LoadingState label="Loading assigned tasks" />
          ) : (
            <>
              {tasks.map((task) => (
                <Link
                  aria-current={selectedTask?.ticketId === task.ticketId ? "page" : undefined}
                  className="request-row"
                  key={task.ticketId}
                  to={`/analyst/tasks/${encodeURIComponent(task.ticketId)}`}
                >
                  <strong>{task.reference}</strong>
                  <span>{task.title}</span>
                  <small>{formatWorkflowState(task.state)}</small>
                </Link>
              ))}
              {tasks.length === 0 ? <p>No assigned tasks.</p> : null}
            </>
          )}
        </aside>
        <AnalystTaskDetail
          key={selectedTask?.ticketId ?? "none"}
          onTaskChange={updateTask}
          task={selectedTask}
        />
      </section>
    </div>
  );
}

function replaceTask(tasks: AnalystTask[], nextTask: AnalystTask) {
  const withoutCurrent = tasks.filter((task) => task.ticketId !== nextTask.ticketId);
  return [nextTask, ...withoutCurrent];
}
