import {
  Activity,
  Bell,
  Bot,
  CarFront,
  ChevronDown,
  CircleHelp,
  FileText,
  Gauge,
  LayoutDashboard,
  LogOut,
  Menu,
  ReceiptText,
  Wrench,
  X,
} from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { api, type Vehicle } from "../api";
import { useAuth } from "../auth/AuthContext";

interface VehicleContextValue {
  vehicles: Vehicle[];
  activeVehicle: Vehicle | null;
  activeVehicleId: number | null;
  setActiveVehicleId: (id: number) => void;
  reloadVehicles: () => Promise<void>;
  loadingVehicles: boolean;
}

const VehicleContext = createContext<VehicleContextValue | null>(null);

const navigation = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/vehicles", label: "My vehicles", icon: CarFront },
  { to: "/service-history", label: "Service history", icon: Wrench },
  { to: "/expenses", label: "Expenses", icon: ReceiptText },
  { to: "/assistant", label: "Maintenance AI", icon: Bot },
  { to: "/mechanic", label: "AI mechanic", icon: CircleHelp },
  { to: "/reminders", label: "Reminders", icon: Bell },
  { to: "/documents", label: "Documents", icon: FileText },
];

const routeTitles: Record<string, string> = {
  "/": "Overview",
  "/vehicles": "My vehicles",
  "/service-history": "Service history",
  "/expenses": "Expense insights",
  "/assistant": "Maintenance AI",
  "/mechanic": "AI mechanic",
  "/reminders": "Reminders & alerts",
  "/documents": "Documents",
};

export function useVehicle() {
  const context = useContext(VehicleContext);
  if (!context) throw new Error("useVehicle must be used inside AppShell");
  return context;
}

export function AppShell() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [activeVehicleId, updateActiveVehicleId] = useState<number | null>(
    () => {
      const saved = Number(window.localStorage.getItem("motorly_vehicle_id"));
      return Number.isFinite(saved) && saved > 0 ? saved : null;
    },
  );
  const [loadingVehicles, setLoadingVehicles] = useState(true);
  const [shellError, setShellError] = useState("");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  const reloadVehicles = useCallback(async () => {
    setLoadingVehicles(true);
    try {
      const result = await api<Vehicle[]>("/vehicles/");
      setVehicles(result);
      setShellError("");
    } catch (reason) {
      const message =
        reason instanceof Error ? reason.message : "Could not load vehicles";
      setShellError(message);
      throw reason;
    } finally {
      setLoadingVehicles(false);
    }
  }, []);

  useEffect(() => {
    void reloadVehicles().catch(() => undefined);
  }, [reloadVehicles, user?.id]);

  useEffect(() => {
    if (loadingVehicles) return;
    if (vehicles.length === 0) {
      updateActiveVehicleId(null);
      window.localStorage.removeItem("motorly_vehicle_id");
      return;
    }
    if (!vehicles.some((vehicle) => vehicle.id === activeVehicleId)) {
      updateActiveVehicleId(vehicles[0].id);
      window.localStorage.setItem("motorly_vehicle_id", String(vehicles[0].id));
    }
  }, [vehicles, activeVehicleId, loadingVehicles]);

  const setActiveVehicleId = useCallback((id: number) => {
    updateActiveVehicleId(id);
    window.localStorage.setItem("motorly_vehicle_id", String(id));
  }, []);

  const activeVehicle =
    vehicles.find((vehicle) => vehicle.id === activeVehicleId) ?? null;

  const reloadUnread = useCallback(async () => {
    try {
      const notifications = await api<{ id: number }[]>(
        "/reminders/notifications?unread_only=true&limit=100",
      );
      setUnreadCount(notifications.length);
    } catch (reason) {
      if (reason instanceof Error) setShellError(reason.message);
    }
  }, []);

  useEffect(() => {
    void reloadUnread();
    window.addEventListener("motorly:notifications-updated", reloadUnread);
    return () =>
      window.removeEventListener(
        "motorly:notifications-updated",
        reloadUnread,
      );
  }, [reloadUnread, location.pathname]);

  const vehicleContext = useMemo(
    () => ({
      vehicles,
      activeVehicle,
      activeVehicleId,
      setActiveVehicleId,
      reloadVehicles,
      loadingVehicles,
    }),
    [
      vehicles,
      activeVehicle,
      activeVehicleId,
      setActiveVehicleId,
      reloadVehicles,
      loadingVehicles,
    ],
  );

  const currentTitle =
    routeTitles[location.pathname] ??
    (location.pathname.startsWith("/service-history")
      ? "Service history"
      : "Vehicle care");

  return (
    <VehicleContext.Provider value={vehicleContext}>
      <div className="app-shell">
        {mobileOpen && (
          <button
            className="mobile-backdrop"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
          />
        )}
        <aside className={`sidebar ${mobileOpen ? "open" : ""}`}>
          <div className="brand-lockup">
            <span className="brand-mark">
              <Gauge size={21} strokeWidth={2.2} />
            </span>
            <span>
              <strong>motorly</strong>
              <small>VEHICLE CARE</small>
            </span>
            <button
              className="icon-button sidebar-close"
              onClick={() => setMobileOpen(false)}
              aria-label="Close navigation"
            >
              <X size={18} />
            </button>
          </div>

          <div className="sidebar-section-label">WORKSPACE</div>
          <nav className="sidebar-nav" aria-label="Main navigation">
            {navigation.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `nav-link ${isActive ? "active" : ""}`
                }
                onClick={() => setMobileOpen(false)}
              >
                <Icon size={18} strokeWidth={1.9} />
                <span>{label}</span>
                {label === "Reminders" && unreadCount > 0 && (
                  <span className="nav-count">
                    {unreadCount > 9 ? "9+" : unreadCount}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>

          <div className="sidebar-bottom">
            <div className="sidebar-help">
              <div className="help-mark">
                <Activity size={17} />
              </div>
              <div>
                <strong>Care, in one place</strong>
                <span>Keep every mile in mind.</span>
              </div>
            </div>
            <button
              className="profile-button"
              onClick={() => {
                signOut();
                navigate("/login", { replace: true });
              }}
            >
              <span className="avatar">{user?.email.slice(0, 1).toUpperCase()}</span>
              <span className="profile-text">
                <strong>{user?.email.split("@")[0]}</strong>
                <small>{user?.email}</small>
              </span>
              <LogOut size={16} />
            </button>
          </div>
        </aside>

        <div className="main-shell">
          <header className="topbar">
            <button
              className="icon-button mobile-menu"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation"
            >
              <Menu size={21} />
            </button>
            <div className="topbar-title">
              <span className="breadcrumb">MOTORLY</span>
              <strong>{currentTitle}</strong>
            </div>
            <div className="topbar-actions">
              <label className="vehicle-switcher">
                <CarFront size={17} />
                <select
                  aria-label="Select active vehicle"
                  value={activeVehicleId ?? ""}
                  disabled={vehicles.length === 0 || loadingVehicles}
                  onChange={(event) =>
                    setActiveVehicleId(Number(event.target.value))
                  }
                >
                  {vehicles.length === 0 ? (
                    <option value="">Add a vehicle</option>
                  ) : (
                    vehicles.map((vehicle) => (
                      <option key={vehicle.id} value={vehicle.id}>
                        {vehicle.vehicle_name}
                      </option>
                    ))
                  )}
                </select>
                <ChevronDown size={14} />
              </label>
              <NavLink
                to="/reminders"
                className="icon-button notification-button"
                aria-label={`Notifications${unreadCount ? `, ${unreadCount} unread` : ""}`}
              >
                <Bell size={19} />
                {unreadCount > 0 && <span className="notification-dot" />}
              </NavLink>
            </div>
          </header>
          <main className="content-area">
            {shellError && (
              <div className="shell-error">
                <span>{shellError}</span>
                <button
                  className="icon-button subtle"
                  aria-label="Dismiss error"
                  onClick={() => setShellError("")}
                >
                  <X size={16} />
                </button>
              </div>
            )}
            <Outlet />
          </main>
        </div>
      </div>
    </VehicleContext.Provider>
  );
}
