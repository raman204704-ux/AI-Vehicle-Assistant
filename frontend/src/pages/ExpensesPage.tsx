import { ArrowDownRight, ArrowUpRight, CircleDollarSign } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  api,
  type CategoryExpense,
  type ExpenseSummary,
  type MonthlyExpense,
  type ServiceTypeExpense,
  type VehicleExpenseComparison,
  type Vehicle,
  type YearlyExpense,
} from "../api";
import { useVehicle } from "../components/AppShell";
import {
  EmptyState,
  ErrorBanner,
  formatAmount,
  LoadingState,
  PageHeader,
  Panel,
  StatCard,
} from "../components/Shared";

interface ExpenseData {
  summary: ExpenseSummary;
  categories: CategoryExpense[];
  monthly: MonthlyExpense[];
  yearly: YearlyExpense[];
  services: ServiceTypeExpense[];
  comparison: VehicleExpenseComparison[];
}

const chartColors = ["#2f805c", "#e7a64a", "#627fd2", "#a57ac7", "#53a6a1", "#e47e68"];

export function ExpensesPage() {
  const { activeVehicle } = useVehicle();
  const [data, setData] = useState<ExpenseData | null>(null);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
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
      api<CategoryExpense[]>(`/analytics/vehicles/${vehicleId}/categories`),
      api<MonthlyExpense[]>(`/analytics/vehicles/${vehicleId}/monthly`),
      api<YearlyExpense[]>(`/analytics/vehicles/${vehicleId}/yearly`),
      api<ServiceTypeExpense[]>(`/analytics/vehicles/${vehicleId}/services`),
      api<VehicleExpenseComparison[]>("/analytics/expenses/comparison"),
      api<Vehicle[]>("/vehicles/"),
    ])
      .then(
        ([
          summary,
          categories,
          monthly,
          yearly,
          services,
          comparison,
          allVehicles,
        ]) => {
          if (cancelled) return;
          setData({
            summary,
            categories,
            monthly,
            yearly,
            services,
            comparison,
          });
          setVehicles(allVehicles);
        },
      )
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(
            reason instanceof Error ? reason.message : "Could not load expenses",
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

  const monthlyData = useMemo(
    () =>
      (data?.monthly ?? []).slice(-12).map((item) => ({
        ...item,
        label: new Intl.DateTimeFormat(undefined, {
          month: "short",
          year: "2-digit",
        }).format(new Date(item.year, item.month - 1, 1)),
      })),
    [data?.monthly],
  );
  const categoryTotal = (data?.categories ?? []).reduce(
    (total, item) => total + item.total_amount,
    0,
  );
  const monthlyAverage =
    data && data.monthly.length
      ? data.monthly.reduce((total, item) => total + item.total_amount, 0) /
        data.monthly.length
      : 0;

  if (!activeVehicle) {
    return (
      <div className="page-stack">
        <PageHeader
          eyebrow="EXPENSES"
          title="A clearer view of your spend."
          description="Select a vehicle to explore service costs and trends."
        />
        <Panel>
          <EmptyState
            icon={CircleDollarSign}
            title="Choose a vehicle first"
            description="Expense insights are grouped by vehicle so your totals stay meaningful."
          />
        </Panel>
      </div>
    );
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={activeVehicle.vehicle_name}
        title="A clearer view of your spend."
        description="Understand the expenses recorded for this vehicle over time."
        action={
          <span className="quiet-label">
            <CircleDollarSign size={16} /> Amounts shown in recorded units
          </span>
        }
      />
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      {loading ? (
        <LoadingState label="Gathering your expense insights..." />
      ) : (
        <>
          <section className="stat-grid">
            <StatCard
              label="Total recorded spend"
              value={formatAmount(data?.summary.total_expenses ?? 0)}
              detail={`${data?.summary.total_transactions ?? 0} transactions`}
              icon={CircleDollarSign}
              tone="green"
            />
            <StatCard
              label="Average transaction"
              value={formatAmount(data?.summary.average_expense ?? 0)}
              detail="Across recorded expenses"
              icon={ArrowUpRight}
              tone="blue"
            />
            <StatCard
              label="Monthly average"
              value={formatAmount(monthlyAverage)}
              detail={`${data?.monthly.length ?? 0} months with activity`}
              icon={ArrowDownRight}
              tone="orange"
            />
            <StatCard
              label="Categories"
              value={String(data?.categories.length ?? 0)}
              detail={`${formatAmount(categoryTotal)} total`}
              icon={CircleDollarSign}
              tone="purple"
            />
          </section>

          <section className="dashboard-grid expense-grid">
            <Panel
              title="Monthly spending"
              subtitle="Recorded totals by month"
              className="chart-panel"
            >
              {monthlyData.length ? (
                <div className="chart-wrap tall">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={monthlyData} barSize={24}>
                      <CartesianGrid
                        vertical={false}
                        stroke="#e9eeeb"
                        strokeDasharray="4 5"
                      />
                      <XAxis
                        dataKey="label"
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: "#82908a", fontSize: 11 }}
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
                  icon={CircleDollarSign}
                  title="No monthly totals yet"
                  description="Expense records will appear here as they are added from invoices."
                />
              )}
            </Panel>

            <Panel
              title="By category"
              subtitle="How recorded spend is distributed"
            >
              {data?.categories.length ? (
                <>
                  <div className="donut-wrap">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={data.categories}
                          dataKey="total_amount"
                          nameKey="category"
                          innerRadius={66}
                          outerRadius={94}
                          paddingAngle={3}
                          stroke="none"
                        >
                          {data.categories.map((item, index) => (
                            <Cell
                              key={item.category}
                              fill={chartColors[index % chartColors.length]}
                            />
                          ))}
                        </Pie>
                        <Tooltip
                          formatter={(value) => [formatAmount(Number(value)), "Spend"]}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="donut-center">
                      <strong>{formatAmount(categoryTotal)}</strong>
                      <small>total</small>
                    </div>
                  </div>
                  <div className="legend-list">
                    {data.categories.map((item, index) => (
                      <div className="legend-row" key={item.category}>
                        <span
                          className="legend-dot"
                          style={{
                            backgroundColor:
                              chartColors[index % chartColors.length],
                          }}
                        />
                        <span>{item.category}</span>
                        <strong>{formatAmount(item.total_amount)}</strong>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <EmptyState
                  icon={CircleDollarSign}
                  title="No category data"
                  description="Recorded expense categories will show up here."
                />
              )}
            </Panel>
          </section>

          <section className="dashboard-grid lower-grid">
            <Panel
              title="Service type"
              subtitle="Costs linked to service records"
            >
              {data?.services.length ? (
                <div className="service-cost-list">
                  {data.services.map((item) => (
                    <div className="service-cost-row" key={item.service_type}>
                      <span>
                        <strong>{item.service_type}</strong>
                        <small>{item.transaction_count} recorded</small>
                      </span>
                      <div className="service-cost-track">
                        <span
                          style={{
                            width: `${Math.min(
                              100,
                              (item.total_amount /
                                Math.max(
                                  ...data.services.map(
                                    (service) => service.total_amount,
                                  ),
                                )) *
                                100,
                            )}%`,
                          }}
                        />
                      </div>
                      <b>{formatAmount(item.total_amount)}</b>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  icon={CircleDollarSign}
                  title="No service-linked costs"
                  description="Costs connected to service records will be grouped here."
                />
              )}
            </Panel>

            <Panel title="Yearly totals" subtitle="Recorded spend by year">
              {data?.yearly.length ? (
                <div className="year-list">
                  {data.yearly
                    .slice()
                    .sort((left, right) => right.year - left.year)
                    .map((item) => (
                      <div className="year-row" key={item.year}>
                        <span>{item.year}</span>
                        <strong>{formatAmount(item.total_amount)}</strong>
                      </div>
                    ))}
                </div>
              ) : (
                <EmptyState
                  icon={CircleDollarSign}
                  title="No yearly totals yet"
                  description="Once expense activity is recorded, annual totals will appear here."
                />
              )}
            </Panel>
          </section>

          {data?.comparison.length ? (
            <Panel
              title="Your vehicles"
              subtitle="Expense comparison across your garage"
              className="comparison-panel"
            >
              <div className="comparison-grid">
                {data.comparison.map((item) => {
                  const vehicleName =
                    vehicles.find((vehicle) => vehicle.id === item.vehicle_id)
                      ?.vehicle_name ?? item.vehicle_name;
                  const maxSpend = Math.max(
                    ...data.comparison.map((vehicle) => vehicle.total_expenses),
                    1,
                  );
                  return (
                    <div className="comparison-row" key={item.vehicle_id}>
                      <div className="comparison-label">
                        <span>{vehicleName}</span>
                        <strong>{formatAmount(item.total_expenses)}</strong>
                      </div>
                      <div className="comparison-track">
                        <span
                          style={{
                            width: `${(item.total_expenses / maxSpend) * 100}%`,
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </Panel>
          ) : null}
          <p className="footnote">
            The current expense records do not store currency or refund details;
            totals are shown as recorded and should only be compared when they
            share a currency.
          </p>
        </>
      )}
    </div>
  );
}
