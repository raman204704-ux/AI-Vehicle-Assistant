import {
  ArrowUpRight,
  FilePlus2,
  Pencil,
  Plus,
  Trash2,
  Wrench,
  X,
} from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import {
  api,
  type ServiceRecord,
  type ServiceRecordInput,
} from "../api";
import { useVehicle } from "../components/AppShell";
import {
  EmptyState,
  ErrorBanner,
  formatAmount,
  formatDate,
  LoadingState,
  Modal,
  PageHeader,
  Panel,
  StatusBadge,
} from "../components/Shared";

interface ServiceFormState {
  service_date: string;
  odometer_reading: string;
  service_type: string;
  description: string;
  workshop_name: string;
  total_cost: string;
}

function initialForm(odometer = 0): ServiceFormState {
  return {
    service_date: new Date().toISOString().slice(0, 10),
    odometer_reading: String(odometer),
    service_type: "",
    description: "",
    workshop_name: "",
    total_cost: "0",
  };
}

function toInput(form: ServiceFormState): ServiceRecordInput {
  return {
    service_date: form.service_date,
    odometer_reading: Number(form.odometer_reading),
    service_type: form.service_type.trim(),
    description: form.description.trim() || null,
    workshop_name: form.workshop_name.trim() || null,
    total_cost: Number(form.total_cost),
  };
}

export function ServiceHistoryPage() {
  const { activeVehicle } = useVehicle();
  const [records, setRecords] = useState<ServiceRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState<ServiceRecord | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<ServiceFormState>(initialForm());
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function loadRecords() {
    if (!activeVehicle) {
      setRecords([]);
      return;
    }
    setLoading(true);
    setError("");
    try {
      setRecords(
        await api<ServiceRecord[]>(
          `/vehicles/${activeVehicle.id}/service-records`,
        ),
      );
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not load service history",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadRecords();
    // Load once per selected vehicle; the callback uses the active vehicle id.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeVehicle?.id]);

  function openCreate() {
    setEditing(null);
    setForm(initialForm(activeVehicle?.current_odometer ?? 0));
    setError("");
    setFormOpen(true);
  }

  function openEdit(record: ServiceRecord) {
    setEditing(record);
    setForm({
      service_date: record.service_date,
      odometer_reading: String(record.odometer_reading),
      service_type: record.service_type,
      description: record.description ?? "",
      workshop_name: record.workshop_name ?? "",
      total_cost: String(record.total_cost),
    });
    setError("");
    setFormOpen(true);
  }

  async function saveRecord(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeVehicle) return;
    setSaving(true);
    setError("");
    try {
      const body = toInput(form);
      if (editing) {
        await api<ServiceRecord>(`/service-records/${editing.id}`, {
          method: "PUT",
          body: JSON.stringify(body),
        });
      } else {
        await api<ServiceRecord>(
          `/vehicles/${activeVehicle.id}/service-records`,
          { method: "POST", body: JSON.stringify(body) },
        );
      }
      setFormOpen(false);
      await loadRecords();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not save service record",
      );
    } finally {
      setSaving(false);
    }
  }

  async function deleteRecord(record: ServiceRecord) {
    if (!window.confirm(`Delete the ${record.service_type} record?`)) return;
    setError("");
    try {
      await api<void>(`/service-records/${record.id}`, { method: "DELETE" });
      await loadRecords();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not delete service record",
      );
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={activeVehicle?.vehicle_name ?? "SERVICE HISTORY"}
        title="A clear record of every visit."
        description="Keep maintenance dates, mileage, and costs together — whether you added the record or it came from an invoice."
        action={
          <button
            className="button primary"
            onClick={openCreate}
            disabled={!activeVehicle}
          >
            <Plus size={17} /> Add service
          </button>
        }
      />
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      <Panel
        title="Service timeline"
        subtitle={
          activeVehicle
            ? `${records.length} ${records.length === 1 ? "record" : "records"} for ${activeVehicle.vehicle_name}`
            : "Select or add a vehicle to get started"
        }
      >
        {loading ? (
          <LoadingState label="Loading your service timeline..." />
        ) : records.length ? (
          <div className="table-scroll">
            <table className="data-table wide-table">
              <thead>
                <tr>
                  <th>Service</th>
                  <th>Date</th>
                  <th>Odometer</th>
                  <th>Workshop</th>
                  <th>Cost</th>
                  <th>Source</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {records.map((record) => (
                  <tr key={record.id}>
                    <td>
                      <strong>{record.service_type}</strong>
                      {record.description && <small>{record.description}</small>}
                    </td>
                    <td>{formatDate(record.service_date)}</td>
                    <td>{record.odometer_reading.toLocaleString()} km</td>
                    <td>{record.workshop_name || "—"}</td>
                    <td>{formatAmount(record.total_cost)}</td>
                    <td>
                      <StatusBadge status={record.source_type} />
                    </td>
                    <td>
                      <div className="table-actions">
                        <button
                          className="icon-button"
                          aria-label={`Edit ${record.service_type}`}
                          onClick={() => openEdit(record)}
                        >
                          <Pencil size={15} />
                        </button>
                        <button
                          className="icon-button danger-hover"
                          aria-label={`Delete ${record.service_type}`}
                          onClick={() => void deleteRecord(record)}
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            icon={Wrench}
            title="The first entry is the hardest"
            description="Add a service record to start a dependable maintenance timeline."
            action={
              activeVehicle ? (
                <button className="button secondary" onClick={openCreate}>
                  <FilePlus2 size={16} /> Add the first record
                </button>
              ) : (
                <a className="text-link" href="/vehicles">
                  Add a vehicle <ArrowUpRight size={15} />
                </a>
              )
            }
          />
        )}
      </Panel>

      {formOpen && (
        <Modal
          title={editing ? "Edit service record" : "Add a service record"}
          onClose={() => setFormOpen(false)}
        >
          <form className="form-stack" onSubmit={saveRecord}>
            {error && <ErrorBanner message={error} />}
            <label className="field">
              <span>Service type</span>
              <input
                value={form.service_type}
                onChange={(event) =>
                  setForm({ ...form, service_type: event.target.value })
                }
                placeholder="e.g. Engine oil change"
                required
                minLength={2}
                maxLength={100}
              />
            </label>
            <div className="form-grid three">
              <label className="field">
                <span>Service date</span>
                <input
                  type="date"
                  value={form.service_date}
                  onChange={(event) =>
                    setForm({ ...form, service_date: event.target.value })
                  }
                  required
                />
              </label>
              <label className="field">
                <span>Odometer (km)</span>
                <input
                  type="number"
                  min="0.1"
                  step="0.1"
                  value={form.odometer_reading}
                  onChange={(event) =>
                    setForm({ ...form, odometer_reading: event.target.value })
                  }
                  required
                />
              </label>
              <label className="field">
                <span>Total cost</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.total_cost}
                  onChange={(event) =>
                    setForm({ ...form, total_cost: event.target.value })
                  }
                  required
                />
              </label>
            </div>
            <div className="form-grid two">
              <label className="field">
                <span>Workshop</span>
                <input
                  value={form.workshop_name}
                  onChange={(event) =>
                    setForm({ ...form, workshop_name: event.target.value })
                  }
                  placeholder="Optional"
                  maxLength={150}
                />
              </label>
              <label className="field">
                <span>Description</span>
                <input
                  value={form.description}
                  onChange={(event) =>
                    setForm({ ...form, description: event.target.value })
                  }
                  placeholder="Optional notes"
                />
              </label>
            </div>
            <p className="form-note">
              Currency is not stored by the current service record model.
            </p>
            <div className="form-actions">
              <button
                type="button"
                className="button secondary"
                onClick={() => setFormOpen(false)}
              >
                <X size={16} /> Cancel
              </button>
              <button className="button primary" disabled={saving}>
                {saving ? "Saving..." : editing ? "Save changes" : "Save record"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
