import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { IconButton } from "../ui/IconButton";
import {
  listNotifications,
  markNotificationRead,
  type AppNotification,
  type NotificationList,
} from "../../lib/api-client/notifications";
import { useAuth } from "../../lib/auth/auth-context";
import { useActionError } from "../../lib/mutations/action-error";

type NotificationsPopoverProps = {
  onToggle: () => void;
  open: boolean;
};

export function NotificationsPopover({ onToggle, open }: NotificationsPopoverProps) {
  const { session } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const csrfToken = session?.csrfToken ?? "";
  const notificationsQuery = useQuery({
    queryKey: ["notifications"],
    queryFn: listNotifications,
    refetchInterval: 60_000,
    retry: false,
  });
  const { actionError, clearActionError, failActionWith } = useActionError();
  const readMutation = useMutation({
    mutationFn: (notificationId: string) => markNotificationRead(notificationId, csrfToken),
    onError: failActionWith("The notification could not be marked as read."),
    onMutate: clearActionError,
    onSuccess: (updated: AppNotification) => {
      queryClient.setQueryData<NotificationList>(["notifications"], (current) =>
        current === undefined
          ? current
          : {
              notifications: current.notifications.map((item) =>
                item.id === updated.id ? updated : item,
              ),
              unread: Math.max(0, current.unread - 1),
            },
      );
    },
  });
  const unread = notificationsQuery.data?.unread ?? 0;
  const notifications = notificationsQuery.data?.notifications ?? [];

  function openNotification(notification: AppNotification) {
    if (!notification.read) {
      readMutation.mutate(notification.id);
    }
    if (notification.linkPath !== null) {
      onToggle();
      void navigate(notification.linkPath);
    }
  }

  return (
    <>
      <span className="notification-bell">
        <IconButton
          ariaLabel={unread > 0 ? `Notifications, ${unread} unread` : "Notifications"}
          onClick={onToggle}
        >
          <Bell aria-hidden="true" size={18} strokeWidth={1.8} />
        </IconButton>
        {unread > 0 ? (
          <span aria-hidden="true" className="notification-bell__badge">
            {unread > 9 ? "9+" : unread}
          </span>
        ) : null}
      </span>
      {open ? (
        <aside className="command-popover notifications-popover" aria-label="Notifications panel">
          <strong>Notifications</strong>
          {actionError ? (
            <p className="auth-error" role="alert">
              {actionError}
            </p>
          ) : null}
          {notificationsQuery.isLoading ? <p>Loading notifications...</p> : null}
          {notificationsQuery.isError ? (
            <div className="auth-error" role="alert">
              <span>Notifications could not be loaded.</span>
              <button onClick={() => void notificationsQuery.refetch()} type="button">
                Retry notifications
              </button>
            </div>
          ) : null}
          {!notificationsQuery.isLoading &&
          !notificationsQuery.isError &&
          notifications.length === 0 ? (
            <p>No new notifications.</p>
          ) : null}
          <ul>
            {notifications.slice(0, 8).map((notification) => (
              <li key={notification.id}>
                <button
                  className={notification.read ? "" : "notification--unread"}
                  onClick={() => openNotification(notification)}
                  type="button"
                >
                  <strong>{notification.title}</strong>
                  <span>{notification.body}</span>
                </button>
              </li>
            ))}
          </ul>
        </aside>
      ) : null}
    </>
  );
}
