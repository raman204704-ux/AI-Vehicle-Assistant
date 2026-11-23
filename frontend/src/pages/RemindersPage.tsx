import {
  Bell,
  BellRing,
  CalendarDays,
  Check,
  CheckCheck,
  CirclePlus,
  Gauge,
  Pencil,
  Plus,
  Trash2,
  Wrench,
  X,
} from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  api,
  notifyNotificationsChanged,
  type AppNotification,
  type Reminder,
  type ReminderInput,
} from "../api";
import { useVehicle } from "../components/AppShell";
import {
  EmptyState,
  ErrorBanner,
  formatDate,
  LoadingState,
  Modal,
  PageHeader,
  Panel,
  StatusBadge,
} from "../components/Shared";

interface ReminderFormState {
  title: string;
  description: string;
  category: string;
  due_date: string;
  due_odometer: string;
  repeat_interval_months: string;
  repeat_interval_km: string;
  reminder_days_before: string;
}

interface ReminderEditState {
  title: string;
  description: string;
  due_date: string;
  due_odometer: string;
  reminder_days_before: string;
}

const emptyReminder: ReminderFormState = {
  title: "",
  description: "",
  category: "maintenance",
  due_date: "",
  due_odometer: "",
  repeat_interval_months: "",
  repeat_interval_km: "",
  reminder_days_before: "7",
};

function toReminderInput(form: ReminderFormState): ReminderInput {
  return {
    title: form.title.trim(),
    description: form.description.trim() || null,
    category: form.category,
    due_date: form.due_date || null,
    due_odometer: form.due_odometer ? Number(form.due_odometer) : null,
    repeat_interval_months: form.repeat_interval_months
      ? Number(form.repeat_interval_months)
      : null,
    repeat_interval_km: form.repeat_interval_km
      ? Number(form.repeat_interval_km)
      : null,
    reminder_days_before: Number(form.reminder_days_before),
  };
}

export function RemindersPage() {
  const { activeVehicle } = useVehicle();
  const activeVehicleId = activeVehicle?.id;
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Reminder | null>(null);
  const [form, setForm] = useState<ReminderFormState>(emptyReminder);
  const [editForm, setEditForm] = useState<ReminderEditState | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const notificationPromise = api<AppNotification[]>(
        "/reminders/notifications?limit=100",
      );
      const reminderPromise = activeVehicleId
        ? api<Reminder[]>(`/reminders/vehicles/${activeVehicleId}`)
        : Promise.resolve([]);
      const [nextReminders, nextNotifications] = await Promise.all([
        reminderPromise,
        notificationPromise,
      ]);
      setReminders(nextReminders);
      setNotifications(nextNotifications);
      notifyNotificationsChanged();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not load reminders",
      );
    } finally {
      setLoading(false);
    }
  }, [activeVehicleId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  function openCreate() {
    setForm(emptyReminder);
    setError("");
    setCreating(true);
  }

  async function createReminder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeVehicle) return;
    const body = toReminderInput(form);
    if (!body.due_date && body.due_odometer === null) {
      setError("Add a due date, odometer, or both.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api<Reminder>(`/reminders/vehicles/${activeVehicle.id}`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setCreating(false);
      await loadData();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create reminder");
    } finally {
      setSaving(false);
    }
  }

  function openEdit(reminder: Reminder) {
    setEditing(reminder);
    setEditForm({
      title: reminder.title,
      description: reminder.description ?? "",
      due_date: reminder.due_date ?? "",
      due_odometer:
        reminder.due_odometer === null ? "" : String(reminder.due_odometer),
      reminder_days_before: String(reminder.reminder_days_before),
    });
    setError("");
  }

  async function saveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing || !editForm) return;
    if (!editForm.due_date && !editForm.due_odometer) {
      setError("A reminder must retain a due date or odometer.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api<Reminder>(`/reminders/${editing.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: editForm.title.trim(),
          description: editForm.description.trim() || null,
          due_date: editForm.due_date || null,
          due_odometer: editForm.due_odometer
            ? Number(editForm.due_odometer)
            : null,
          reminder_days_before: Number(editForm.reminder_days_before),
        }),
      });
      setEditing(null);
      setEditForm(null);
      await loadData();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not update reminder");
    } finally {
      setSaving(false);
    }
  }

  async function completeReminder(reminder: Reminder) {
    setError("");
    try {
      await api<Reminder>(`/reminders/${reminder.id}/complete`, {
        method: "POST",
      });
      await loadData();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not complete reminder",
      );
    }
  }

  async function cancelReminder(reminder: Reminder) {
    if (!window.confirm(`Cancel the “${reminder.title}” reminder?`)) return;
    setError("");
    try {
      await api<void>(`/reminders/${reminder.id}`, { method: "DELETE" });
      await loadData();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not cancel reminder");
    }
  }

  async function markAsRead(notification: AppNotification) {
    setError("");
    try {
      await api<{ message: string }>(
        `/reminders/notifications/${notification.id}/read`,
        { method: "PATCH" },
      );
      await loadData();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not update notification",
      );
    }
  }

  const activeReminders = reminders.filter(
    (reminder) => reminder.status === "active",
  );
  const pastReminders = reminders.filter(
    (reminder) => reminder.status !== "active",
  );
  const unreadCount = notifications.filter(
    (notification) => !notification.is_read,
  ).length;

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={activeVehicle?.vehicle_name ?? "YOUR MAINTENANCE"}
        title="A little reminder goes a long way."
        description="Set your own due dates and mileage targets. Recurring intervals are always the ones you choose."
        action={
          <button
            className="button primary"
            onClick={openCreate}
            disabled={!activeVehicle}
          >
            <CirclePlus size={17} /> New reminder
          </button>
        }
      />
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      <section className="reminder-summary">
        <div>
          <span className="summary-icon"><BellRing size={18} /></span>
          <span><small>ACTIVE REMINDERS</small><strong>{activeReminders.length}</strong></span>
        </div>
        <div>
          <span className="summary-icon orange"><Bell size={18} /></span>
          <span><small>UNREAD NOTIFICATIONS</small><strong>{unreadCount}</strong></span>
        </div>
        <div>
          <span className="summary-icon blue"><CheckCheck size={18} /></span>
          <span><small>COMPLETED OR CANCELLED</small><strong>{pastReminders.length}</strong></span>
        </div>
      </section>

      <section className="dashboard-grid reminders-grid">
        <Panel
          title="Maintenance schedule"
          subtitle={
            activeVehicle
              ? `Reminders for ${activeVehicle.vehicle_name}`
              : "Select a vehicle to see its schedule"
          }
        >
          {loading ? (
            <LoadingState label="Loading your schedule..." />
          ) : activeReminders.length ? (
            <div className="reminder-list">
              {activeReminders.map((reminder) => (
                <article className="reminder-card" key={reminder.id}>
                  <span className="reminder-card-icon">
                    {reminder.due_date ? (
                      <CalendarDays size={18} />
                    ) : (
                      <Gauge size={18} />
                    )}
                  </span>
                  <div className="reminder-card-body">
                    <div className="reminder-title-row">
                      <h3>{reminder.title}</h3>
                      <StatusBadge status={reminder.category} />
                    </div>
                    <p>{reminder.description || "No additional notes"}</p>
                    <div className="reminder-details">
                      {reminder.due_date && (
                        <span><CalendarDays size={14} /> {formatDate(reminder.due_date)}</span>
                      )}
                      {reminder.due_odometer !== null && (
                        <span><Gauge size={14} /> {reminder.due_odometer.toLocaleString()} km</span>
                      )}
                      {(reminder.repeat_interval_months ||
                        reminder.repeat_interval_km) && (
                        <span>
                          <Wrench size={14} /> Repeats
                          {reminder.repeat_interval_months
                            ? ` every ${reminder.repeat_interval_months} months`
                            : ""}
                          {reminder.repeat_interval_km
                            ? ` every ${reminder.repeat_interval_km.toLocaleString()} km`
                            : ""}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="reminder-actions">
                    <button
                      className="icon-button"
                      onClick={() => openEdit(reminder)}
                      aria-label={`Edit ${reminder.title}`}
                    >
                      <Pencil size={15} />
                    </button>
                    <button
                      className="icon-button"
                      onClick={() => void completeReminder(reminder)}
                      aria-label={`Complete ${reminder.title}`}
                      title="Mark complete"
                    >
                      <Check size={16} />
                    </button>
                    <button
                      className="icon-button danger-hover"
                      onClick={() => void cancelReminder(reminder)}
                      aria-label={`Cancel ${reminder.title}`}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={CalendarDays}
              title="No reminders on the calendar"
              description={
                activeVehicle
                  ? "Create a date or mileage reminder whenever you want a nudge."
                  : "Add a vehicle before creating a reminder."
              }
              action={
                activeVehicle ? (
                  <button className="button secondary" onClick={openCreate}>
                    <Plus size={16} /> Create a reminder
                  </button>
                ) : null
              }
            />
          )}
        </Panel>

        <Panel
          title="Notification center"
          subtitle={`${unreadCount} unread · latest activity`}
        >
          {loading ? (
            <LoadingState label="Loading notifications..." />
          ) : notifications.length ? (
            <div className="notification-list">
              {notifications.map((notification) => (
                <article
                  className={`notification-card ${notification.is_read ? "read" : ""}`}
                  key={notification.id}
                >
                  <span
                    className={`notification-icon ${notification.notification_type}`}
                  >
                    {notification.notification_type === "overdue" ? (
                      <BellRing size={17} />
                    ) : (
                      <CalendarDays size={17} />
                    )}
                  </span>
                  <div className="notification-copy">
                    <div className="notification-title">
                      <strong>{notification.title}</strong>
                      <StatusBadge status={notification.notification_type} />
                    </div>
                    <p>{notification.message}</p>
                    <small>{new Date(notification.created_at).toLocaleString()}</small>
                  </div>
                  {!notification.is_read && (
                    <button
                      className="icon-button"
                      onClick={() => void markAsRead(notification)}
                      aria-label="Mark notification as read"
                    >
                      <Check size={16} />
                    </button>
                  )}
                </article>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={Bell}
              title="All caught up"
              description="When a reminder is coming up or overdue, you’ll find a note here."
            />
          )}
        </Panel>
      </section>

      {pastReminders.length > 0 && (
        <Panel title="Past reminders" subtitle="Completed or cancelled">
          <div className="past-reminder-list">
            {pastReminders.map((reminder) => (
              <div className="past-reminder-row" key={reminder.id}>
                <span>
                  <strong>{reminder.title}</strong>
                  <small>{formatDate(reminder.completed_at ?? reminder.updated_at)}</small>
                </span>
                <StatusBadge status={reminder.status} />
              </div>
            ))}
          </div>
        </Panel>
      )}

      {creating && (
        <Modal title="Create a maintenance reminder" onClose={() => setCreating(false)}>
          <form className="form-stack" onSubmit={createReminder}>
            {error && <ErrorBanner message={error} />}
            <label className="field">
              <span>Reminder title</span>
              <input
                value={form.title}
                onChange={(event) => setForm({ ...form, title: event.target.value })}
                placeholder="e.g. Inspect the tyres"
                minLength={2}
                maxLength={255}
                required
              />
            </label>
            <div className="form-grid two">
              <label className="field">
                <span>Category</span>
                <select
                  value={form.category}
                  onChange={(event) => setForm({ ...form, category: event.target.value })}
                >
                  <option value="maintenance">Maintenance</option>
                  <option value="inspection">Inspection</option>
                  <option value="repair">Repair</option>
                  <option value="registration">Registration</option>
                  <option value="insurance">Insurance</option>
                  <option value="other">Other</option>
                </select>
              </label>
              <label className="field">
                <span>Reminder days before</span>
                <input
                  type="number"
                  min="0"
                  max="365"
                  value={form.reminder_days_before}
                  onChange={(event) =>
                    setForm({ ...form, reminder_days_before: event.target.value })
                  }
                  required
                />
              </label>
            </div>
            <label className="field">
              <span>Notes (optional)</span>
              <textarea
                value={form.description}
                onChange={(event) =>
                  setForm({ ...form, description: event.target.value })
                }
                rows={2}
              />
            </label>
            <div className="form-grid two">
              <label className="field">
                <span>Due date (optional)</span>
                <input
                  type="date"
                  value={form.due_date}
                  onChange={(event) => setForm({ ...form, due_date: event.target.value })}
                />
              </label>
              <label className="field">
                <span>Due odometer in km (optional)</span>
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  value={form.due_odometer}
                  onChange={(event) =>
                    setForm({ ...form, due_odometer: event.target.value })
                  }
                />
              </label>
            </div>
            <p className="form-note">Enter a due date, a mileage target, or both.</p>
            <div className="form-grid two">
              <label className="field">
                <span>Repeat every (months)</span>
                <input
                  type="number"
                  min="1"
                  value={form.repeat_interval_months}
                  onChange={(event) =>
                    setForm({ ...form, repeat_interval_months: event.target.value })
                  }
                  placeholder="Optional"
                />
              </label>
              <label className="field">
                <span>Repeat every (km)</span>
                <input
                  type="number"
                  min="0.1"
                  step="0.1"
                  value={form.repeat_interval_km}
                  onChange={(event) =>
                    setForm({ ...form, repeat_interval_km: event.target.value })
                  }
                  placeholder="Optional"
                />
              </label>
            </div>
            <div className="form-actions">
              <button
                type="button"
                className="button secondary"
                onClick={() => setCreating(false)}
              >
                <X size={16} /> Cancel
              </button>
              <button className="button primary" disabled={saving}>
                {saving ? "Creating..." : "Create reminder"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {editing && editForm && (
        <Modal title="Update reminder" onClose={() => setEditing(null)}>
          <form className="form-stack" onSubmit={saveEdit}>
            {error && <ErrorBanner message={error} />}
            <label className="field">
              <span>Reminder title</span>
              <input
                value={editForm.title}
                onChange={(event) =>
                  setEditForm({ ...editForm, title: event.target.value })
                }
                minLength={2}
                maxLength={255}
                required
              />
            </label>
            <label className="field">
              <span>Notes</span>
              <textarea
                rows={2}
                value={editForm.description}
                onChange={(event) =>
                  setEditForm({ ...editForm, description: event.target.value })
                }
              />
            </label>
            <div className="form-grid two">
              <label className="field">
                <span>Due date</span>
                <input
                  type="date"
                  value={editForm.due_date}
                  onChange={(event) =>
                    setEditForm({ ...editForm, due_date: event.target.value })
                  }
                />
              </label>
              <label className="field">
                <span>Due odometer (km)</span>
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  value={editForm.due_odometer}
                  onChange={(event) =>
                    setEditForm({ ...editForm, due_odometer: event.target.value })
                  }
                />
              </label>
            </div>
            <label className="field compact-field">
              <span>Reminder days before</span>
              <input
                type="number"
                min="0"
                max="365"
                value={editForm.reminder_days_before}
                onChange={(event) =>
                  setEditForm({
                    ...editForm,
                    reminder_days_before: event.target.value,
                  })
                }
              />
            </label>
            <div className="form-actions">
              <button
                type="button"
                className="button secondary"
                onClick={() => setEditing(null)}
              >
                <X size={16} /> Cancel
              </button>
              <button className="button primary" disabled={saving}>
                {saving ? "Saving..." : "Save reminder"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
