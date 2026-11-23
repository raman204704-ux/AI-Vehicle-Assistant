import {
  ArrowUpRight,
  Check,
  CirclePlus,
  Gauge,
  Pencil,
  Trash2,
  X,
} from "lucide-react";
import { useState, type FormEvent } from "react";

import { api, type Vehicle, type VehicleInput } from "../api";
import { useVehicle } from "../components/AppShell";
import {
  ErrorBanner,
  Modal,
  PageHeader,
  Panel,
  StatusBadge,
} from "../components/Shared";

interface VehicleFormState {
  vehicle_name: string;
  manufacturer: string;
  model: string;
  year: string;
  fuel_type: string;
  registration_number: string;
  current_odometer: string;
}

const emptyForm: VehicleFormState = {
  vehicle_name: "",
  manufacturer: "",
  model: "",
  year: String(new Date().getFullYear()),
  fuel_type: "Petrol",
  registration_number: "",
  current_odometer: "0",
};

function toVehicleInput(form: VehicleFormState): VehicleInput {
  return {
    vehicle_name: form.vehicle_name.trim(),
    manufacturer: form.manufacturer.trim(),
    model: form.model.trim(),
    year: Number(form.year),
    fuel_type: form.fuel_type.trim(),
    registration_number: form.registration_number.trim(),
    current_odometer: Number(form.current_odometer),
  };
}

export function VehiclesPage() {
  const {
    vehicles,
    activeVehicleId,
    setActiveVehicleId,
    reloadVehicles,
  } = useVehicle();
  const [editing, setEditing] = useState<Vehicle | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<VehicleFormState>(emptyForm);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setError("");
    setFormOpen(true);
  }

  function openEdit(vehicle: Vehicle) {
    setEditing(vehicle);
    setForm({
      vehicle_name: vehicle.vehicle_name,
      manufacturer: vehicle.manufacturer,
      model: vehicle.model,
      year: String(vehicle.year),
      fuel_type: vehicle.fuel_type,
      registration_number: vehicle.registration_number,
      current_odometer: String(vehicle.current_odometer),
    });
    setError("");
    setFormOpen(true);
  }

  async function saveVehicle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const body = toVehicleInput(form);
      if (editing) {
        await api<Vehicle>(`/vehicles/${editing.id}`, {
          method: "PUT",
          body: JSON.stringify(body),
        });
      } else {
        const created = await api<Vehicle>("/vehicles/", {
          method: "POST",
          body: JSON.stringify(body),
        });
        setActiveVehicleId(created.id);
      }
      await reloadVehicles();
      setFormOpen(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save vehicle");
    } finally {
      setSaving(false);
    }
  }

  async function deleteVehicle(vehicle: Vehicle) {
    if (
      !window.confirm(
        `Delete ${vehicle.vehicle_name}? Its associated records may also be removed.`,
      )
    ) {
      return;
    }
    setError("");
    try {
      await api<void>(`/vehicles/${vehicle.id}`, { method: "DELETE" });
      await reloadVehicles();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not delete vehicle");
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="YOUR GARAGE"
        title="Every vehicle, accounted for."
        description="Keep the details up to date so your records and reminders stay useful."
        action={
          <button className="button primary" onClick={openCreate}>
            <CirclePlus size={17} /> Add vehicle
          </button>
        }
      />
      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      {vehicles.length === 0 ? (
        <Panel>
          <div className="empty-garage">
            <span className="empty-icon large"><Gauge size={26} /></span>
            <h2>Your garage is waiting</h2>
            <p>Add your first vehicle to start tracking its service history.</p>
            <button className="button primary" onClick={openCreate}>
              Add your first vehicle <ArrowUpRight size={16} />
            </button>
          </div>
        </Panel>
      ) : (
        <section className="vehicle-card-grid">
          {vehicles.map((vehicle) => {
            const active = vehicle.id === activeVehicleId;
            return (
              <article
                className={`vehicle-card ${active ? "selected" : ""}`}
                key={vehicle.id}
              >
                <div className="vehicle-card-top">
                  <div className="vehicle-card-icon">
                    <Gauge size={22} />
                  </div>
                  <div className="vehicle-card-actions">
                    {active && <StatusBadge status="active" />}
                    <button
                      className="icon-button"
                      onClick={() => openEdit(vehicle)}
                      aria-label={`Edit ${vehicle.vehicle_name}`}
                    >
                      <Pencil size={16} />
                    </button>
                    <button
                      className="icon-button danger-hover"
                      onClick={() => void deleteVehicle(vehicle)}
                      aria-label={`Delete ${vehicle.vehicle_name}`}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
                <div className="vehicle-card-title">
                  <h2>{vehicle.vehicle_name}</h2>
                  <p>
                    {vehicle.year} {vehicle.manufacturer} {vehicle.model}
                  </p>
                </div>
                <div className="vehicle-card-meta">
                  <span>
                    <small>ODOMETER</small>
                    <strong>{vehicle.current_odometer.toLocaleString()} km</strong>
                  </span>
                  <span>
                    <small>FUEL</small>
                    <strong>{vehicle.fuel_type}</strong>
                  </span>
                  <span>
                    <small>REGISTRATION</small>
                    <strong>{vehicle.registration_number}</strong>
                  </span>
                </div>
                {!active && (
                  <button
                    className="button secondary wide"
                    onClick={() => setActiveVehicleId(vehicle.id)}
                  >
                    Set as active vehicle <Check size={16} />
                  </button>
                )}
              </article>
            );
          })}
        </section>
      )}

      {formOpen && (
        <Modal
          title={editing ? "Update vehicle" : "Add a vehicle"}
          onClose={() => setFormOpen(false)}
        >
          <form className="form-stack" onSubmit={saveVehicle}>
            {error && <ErrorBanner message={error} />}
            <label className="field">
              <span>Vehicle nickname</span>
              <input
                value={form.vehicle_name}
                onChange={(event) =>
                  setForm({ ...form, vehicle_name: event.target.value })
                }
                placeholder="e.g. Weekend drive"
                required
              />
            </label>
            <div className="form-grid two">
              <label className="field">
                <span>Manufacturer</span>
                <input
                  value={form.manufacturer}
                  onChange={(event) =>
                    setForm({ ...form, manufacturer: event.target.value })
                  }
                  placeholder="Tata"
                  required
                />
              </label>
              <label className="field">
                <span>Model</span>
                <input
                  value={form.model}
                  onChange={(event) =>
                    setForm({ ...form, model: event.target.value })
                  }
                  placeholder="Nexon"
                  required
                />
              </label>
            </div>
            <div className="form-grid three">
              <label className="field">
                <span>Model year</span>
                <input
                  type="number"
                  min="1900"
                  max="2100"
                  value={form.year}
                  onChange={(event) =>
                    setForm({ ...form, year: event.target.value })
                  }
                  required
                />
              </label>
              <label className="field">
                <span>Fuel type</span>
                <select
                  value={form.fuel_type}
                  onChange={(event) =>
                    setForm({ ...form, fuel_type: event.target.value })
                  }
                >
                  <option>Petrol</option>
                  <option>Diesel</option>
                  <option>Electric</option>
                  <option>Hybrid</option>
                  <option>CNG</option>
                  <option>LPG</option>
                  <option>Other</option>
                </select>
              </label>
              <label className="field">
                <span>Current odometer (km)</span>
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  value={form.current_odometer}
                  onChange={(event) =>
                    setForm({ ...form, current_odometer: event.target.value })
                  }
                  required
                />
              </label>
            </div>
            <label className="field">
              <span>Registration number</span>
              <input
                value={form.registration_number}
                onChange={(event) =>
                  setForm({ ...form, registration_number: event.target.value })
                }
                placeholder="e.g. MH 01 AB 1234"
                required
              />
            </label>
            <div className="form-actions">
              <button
                type="button"
                className="button secondary"
                onClick={() => setFormOpen(false)}
              >
                <X size={16} /> Cancel
              </button>
              <button className="button primary" disabled={saving}>
                {saving ? "Saving..." : editing ? "Save changes" : "Add vehicle"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
