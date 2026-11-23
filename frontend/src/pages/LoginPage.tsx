import { ArrowRight, Gauge, ShieldCheck, Sparkles } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { ErrorBanner } from "../components/Shared";

export function LoginPage() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { signIn, signUp } = useAuth();
  const isRegister = pathname === "/register";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      if (isRegister) await signUp(email, password);
      else await signIn(email, password);
      navigate("/", { replace: true });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not sign in");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-story">
        <Link className="auth-brand" to="/login">
          <span className="brand-mark">
            <Gauge size={21} />
          </span>
          <span>motorly</span>
        </Link>
        <div className="auth-story-copy">
          <span className="story-kicker">
            <Sparkles size={15} /> A little more peace of mind
          </span>
          <h1>Every mile has a story. Keep yours running smoothly.</h1>
          <p>
            Your service history, helpful reminders, and vehicle know-how —
            thoughtfully brought together.
          </p>
          <div className="story-points">
            <div>
              <span className="story-point-icon">
                <ShieldCheck size={17} />
              </span>
              <span>
                <strong>Your records, in one place</strong>
                <small>Private to your account and vehicles</small>
              </span>
            </div>
            <div>
              <span className="story-point-icon">
                <Gauge size={17} />
              </span>
              <span>
                <strong>Know what is coming up</strong>
                <small>Stay ahead of dates and mileage</small>
              </span>
            </div>
          </div>
        </div>
        <div className="auth-story-footer">MADE FOR THE ROAD AHEAD</div>
      </section>

      <section className="auth-form-side">
        <div className="auth-form-wrap">
          <p className="eyebrow">{isRegister ? "GET STARTED" : "WELCOME BACK"}</p>
          <h2>{isRegister ? "Create your account" : "Sign in to Motorly"}</h2>
          <p className="auth-form-intro">
            {isRegister
              ? "A calmer way to keep up with every vehicle you own."
              : "Your vehicle care workspace is right where you left it."}
          </p>

          {error && <ErrorBanner message={error} />}

          <form className="form-stack" onSubmit={handleSubmit}>
            <label className="field">
              <span>Email address</span>
              <input
                autoComplete="email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
                required
              />
            </label>
            <label className="field">
              <span>Password</span>
              <input
                autoComplete={isRegister ? "new-password" : "current-password"}
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder={isRegister ? "At least 8 characters" : "Enter your password"}
                minLength={isRegister ? 8 : undefined}
                maxLength={128}
                required
              />
            </label>
            <button className="button primary wide" disabled={submitting}>
              {submitting
                ? "Please wait..."
                : isRegister
                  ? "Create account"
                  : "Sign in"}
              {!submitting && <ArrowRight size={17} />}
            </button>
          </form>

          <p className="auth-switch">
            {isRegister ? "Already have an account?" : "New to Motorly?"}{" "}
            <Link to={isRegister ? "/login" : "/register"}>
              {isRegister ? "Sign in" : "Create an account"}
            </Link>
          </p>
          <p className="auth-privacy">
            By continuing, you agree to keep your account credentials private.
          </p>
        </div>
      </section>
    </main>
  );
}
