import {
  ArrowUpRight,
  BellRing,
  CalendarDays,
  CarFront,
  CircleCheck,
  Clock3,
  Gauge,
  ReceiptText,
  Wrench,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  api,
  type AppNotification,
  type ExpenseSummary,
  type MaintenancePredictionResponse,
  type MonthlyExpense,
  type Reminder,
  type ServiceRecord,
} from "../api";
import { useVehicle } from "../components/AppShell";
import {
  EmptyState,
  ErrorBanner,
  formatAmount,
  formatDate,
  LoadingState,
  PageHeader,
  Panel,
  StatCard,
  StatusBadge,
} from "../components/Shared";

interface DashboardData {
  summary: ExpenseSummary;
  monthly: MonthlyExpense[];
  services: ServiceRecord[];
  reminders: Reminder[];
  notifications: AppNotification[];
  predictions: MaintenancePredictionResponse;
}

export function DashboardPage() {
  const { activeVehicle, loadingVehicles, vehicles } = useVehicle();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    if (!activeVehicle) {
      setData(null);
      return;
    }
    setLoading(true);
    setError("");
    const vehicleId = activeVehicle.id;
    Promise.all([
      api<ExpenseSummary>(`/analytics/vehicles/${vehicleId}/summary`),
      api<MonthlyExpense[]>(`/analytics/vehicles/${vehicleId}/monthly`),
      api<ServiceRecord[]>(`/vehicles/${vehicleId}/service-records`),
      api<Reminder[]>(`/reminders/vehicles/${vehicleId}`),
      api<AppNotification[]>(
        "/reminders/notifications?unread_only=true&limit=100",
      ),
      api<MaintenancePredictionResponse>(
        `/maintenance/vehicles/${vehicleId}/predictions`,
      ),
    ])
      .then(
        ([
          summary,
          monthly,
          services,
          reminders,
          notifications,
          predictions,
        ]) => {
          if (cancelled) return;
          setData({
            summary,
            monthly,
            services,
            reminders,
            notifications,
            predictions,
          });
        },
      )
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(
            reason instanceof Error ? reason.message : "Could not load overview",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeVehicle]);

  const chartData = useMemo(
    () =>
      (data?.monthly ?? []).slice(-6).map((item) => ({
        ...item,
        month_label: new Intl.DateTimeFormat(undefined, {
          month: "short",
        }).format(new Date(item.year, item.month - 1, 1)),
      })),
    [data?.monthly],
  );
  const upcomingReminders = (data?.reminders ?? [])
    .filter((reminder) => reminder.status === "active" && reminder.is_enabled)
    .slice(0, 4);
  const unreadCount = data?.notifications.length ?? 0;
  const forecast = data?.predictions.predictions ?? [];

  if (loadingVehicles && vehicles.length === 0) {
    return <LoadingState label="Finding your vehicles..." />;
  }

  if (!activeVehicle) {
    return (
      <div className="page-stack">
        <PageHeader
          eyebrow="YOUR GARAGE"
          title="A good day to get ahead."
          description="Add a vehicle to bring your maintenance, service records, and reminders together."
        />
        <Panel>
          <EmptyState
            icon={CarFront}
            title="Your garage is ready when you are"
            description="Add your first vehicle to start building its service timeline."
            action={
              <Link className="button primary" to="/vehicles">
                Add a vehicle <ArrowUpRight size={16} />
              </Link>
            }
          />
        </Panel>
      </div>
    );
  }

  return (
    <div className="page-stack">
      <section className="welcome-banner">
        <div className="welcome-copy">
          <p className="eyebrow">YOUR VEHICLE OVERVIEW</p>
          <h1>{activeVehicle.vehicle_name}</h1>
          <p>
            {activeVehicle.year} {activeVehicle.manufacturer}{" "}
            {activeVehicle.model}
            <span className="welcome-dot">·</span>
            {activeVehicle.current_odometer.toLocaleString()} km
          </p>
        </div>
        <div className="welcome-art" aria-hidden="true">
          <span className="art-ring ring-one" />
          <span className="art-ring ring-two" />
          <CarFront size={92} strokeWidth={1.1} />
          <span className="art-spark spark-one" />
          <span className="art-spark spark-two" />
        </div>
        <Link className="banner-link" to="/vehicles">
          Vehicle details <ArrowUpRight size={16} />
        </Link>
      </section>

      {error && <ErrorBanner message={error} />}

      {loading ? (
        <LoadingState label="Loading your vehicle overview..." />
      ) : (
        <>
          <section className="stat-grid">
            <StatCard
              label="Total recorded spend"
              value={formatAmount(data?.summary.total_expenses ?? 0)}
              detail={`${data?.summary.total_transactions ?? 0} transactions`}
              icon={ReceiptText}
              tone="green"
            />
            <StatCard
              label="Service records"
              value={String(data?.services.length ?? 0)}
              detail="Across this vehicle"
              icon={Wrench}
              tone="blue"
            />
            <StatCard
              label="Upcoming reminders"
              value={String(upcomingReminders.length)}
              detail="Date and mileage based"
              icon={CalendarDays}
              tone="orange"
            />
            <StatCard
              label="Unread notifications"
              value={String(unreadCount)}
              detail="Across your garage"
              icon={BellRing}
              tone="purple"
            />
          </section>

          <section className="dashboard-grid">
            <Panel
              title="Spending over time"
              subtitle="Monthly expense records for this vehicle"
              action={
                <Link className="text-link" to="/expenses">
                  View insights <ArrowUpRight size={15} />
                </Link>
              }
              className="chart-panel"
            >
              {chartData.length ? (
                <div className="chart-wrap">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} barSize={26}>
                      <CartesianGrid
                        vertical={false}
                        stroke="#e9eeeb"
                        strokeDasharray="4 5"
                      />
                      <XAxis
                        dataKey="month_label"
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: "#82908a", fontSize: 12 }}
                        dy={10}
                      />
                      <YAxis
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: "#82908a", fontSize: 11 }}
                        tickFormatter={(value: number) =>
                          value >= 1000
                            ? `${Math.round(value / 1000)}k`
                            : String(value)
                        }
                        width={38}
                      />
                      <Tooltip
                        cursor={{ fill: "#f3f7f4" }}
                        formatter={(value) => [formatAmount(Number(value)), "Spend"]}
                      />
                      <Bar
                        dataKey="total_amount"
                        fill="#2f805c"
                        radius={[6, 6, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <EmptyState
                  icon={ReceiptText}
                  title="Your spending picture starts here"
                  description="Expense totals will appear after an invoice or service record is added."
                  action={<Link className="text-link" to="/documents">Upload a document <ArrowUpRight size={15} /></Link>}
                />
              )}
            </Panel>

            <Panel
              title="Next up"
              subtitle="Your active maintenance reminders"
              action={
                <Link className="text-link" to="/reminders">
                  All reminders <ArrowUpRight size={15} />
                </Link>
              }
              className="reminder-panel"
            >
              {upcomingReminders.length ? (
                <div className="mini-list">
                  {upcomingReminders.map((reminder) => (
                    <div className="mini-reminder" key={reminder.id}>
                      <span className="mini-reminder-icon">
                        <Wrench size={17} />
                      </span>
                      <span className="mini-reminder-copy">
                        <strong>{reminder.title}</strong>
                        <small>
                          {reminder.due_date
                            ? `Due ${formatDate(reminder.due_date)}`
                            : `At ${reminder.due_odometer?.toLocaleString()} km`}
                        </small>
                      </span>
                      <span className="mini-arrow">›</span>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  icon={CircleCheck}
                  title="Nothing due just yet"
                  description="Create a reminder when you want to keep an eye on a service."
                  action={<Link className="text-link" to="/reminders">Set a reminder <ArrowUpRight size={15} /></Link>}
                />
              )}
            </Panel>
          </section>

          <section className="dashboard-grid lower-grid">
            <Panel
              title="Recent service history"
              subtitle="The latest care for your vehicle"
              action={
                <Link className="text-link" to="/service-history">
                  Open history <ArrowUpRight size={15} />
                </Link>
              }
            >
              {data?.services.length ? (
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Service</th>
                        <th>Date</th>
                        <th>Odometer</th>
                        <th>Cost</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.services.slice(0, 4).map((record) => (
                        <tr key={record.id}>
                          <td>
                            <strong>{record.service_type}</strong>
                            <small>{record.source_type}</small>
                          </td>
                          <td>{formatDate(record.service_date)}</td>
                          <td>{record.odometer_reading.toLocaleString()} km</td>
                          <td>{formatAmount(record.total_cost)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <EmptyState
                  icon={Wrench}
                  title="No service records yet"
                  description="Keep a simple timeline of the work done on your vehicle."
                  action={<Link className="text-link" to="/service-history">Add a service record <ArrowUpRight size={15} /></Link>}
                />
              )}
            </Panel>

            <Panel
              title="Maintenance outlook"
              subtitle="From verified rules in your workspace"
              action={
                <span className="quiet-label">
                  <Clock3 size={14} /> Based on service history
                </span>
              }
            >
              {forecast.length ? (
                <div className="forecast-list">
                  {forecast.slice(0, 4).map((item) => (
                    <div className="forecast-row" key={item.rule_id}>
                      <span className="forecast-icon">
                        <Gauge size={16} />
                      </span>
                      <span className="forecast-copy">
                        <strong>{item.maintenance_type}</strong>
                        <small>
                          {item.next_due_date
                            ? `Next date ${formatDate(item.next_due_date)}`
                            : item.next_due_odometer !== null
                              ? `At ${item.next_due_odometer.toLocaleString()} km`
                              : "More service history needed"}
                        </small>
                      </span>
                      <StatusBadge status={item.status} />
                    </div>
                  ))}
                  <p className="footnote">
                    Predictions use configured rules and are not a substitute
                    for your vehicle manufacturer’s guidance.
                  </p>
                </div>
              ) : (
                <EmptyState
                  icon={Gauge}
                  title="No verified forecast available"
                  description="When verified maintenance rules and service history are available, they will show here."
                />
              )}
            </Panel>
          </section>
        </>
      )}
    </div>
  );
}
