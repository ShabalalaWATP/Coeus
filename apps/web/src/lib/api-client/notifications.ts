import { apiRequestJson } from "./client";

export type AppNotification = {
  id: string;
  kind: string;
  title: string;
  body: string;
  linkPath: string | null;
  read: boolean;
  createdAt: string;
};

export type NotificationList = {
  notifications: AppNotification[];
  unread: number;
};

export async function listNotifications(): Promise<NotificationList> {
  return apiRequestJson<NotificationList>("/api/v1/notifications", { method: "GET" });
}

export async function markNotificationRead(
  notificationId: string,
  csrfToken: string,
): Promise<AppNotification> {
  return apiRequestJson<AppNotification>(`/api/v1/notifications/${notificationId}/read`, {
    headers: { "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}
