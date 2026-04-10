"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { useAuth } from "@/lib/auth/context";

const loginSchema = z.object({
  username: z.string().min(1, "Username is required"),
  password: z.string().min(1, "Password is required"),
});

type LoginValues = z.infer<typeof loginSchema>;

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginPageContent passwordChanged={false} />}>
      <LoginPageWithSearchParams />
    </Suspense>
  );
}

function LoginPageWithSearchParams() {
  const searchParams = useSearchParams();
  return <LoginPageContent passwordChanged={searchParams.get("passwordChanged") === "1"} />;
}

function LoginPageContent({ passwordChanged }: { passwordChanged: boolean }) {
  const router = useRouter();
  const { login, passwordChangeRequired, status } = useAuth();
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
    setError,
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      username: "",
      password: "",
    },
  });

  useEffect(() => {
    if (status !== "authenticated") {
      return;
    }
    router.replace(passwordChangeRequired ? "/change-password" : "/domains");
  }, [passwordChangeRequired, router, status]);

  async function onSubmit(values: LoginValues) {
    try {
      const data = await login(values);
      router.replace(data.password_change_required ? "/change-password" : "/domains");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Login failed";
      setError("root", { message });
    }
  }

  return (
    <main className="app-frame app-frame-auth auth-shell">
      <section className="hero-card stack">
        <p className="eyebrow">DMARCWatch</p>
        <h1 className="page-title">DMARC operations, in one focused workspace.</h1>
        <p className="lede">
          Sign in to review domains, dashboards, ingest jobs, search results, and admin activity from one place.
        </p>
        <div className="panel-grid">
          <article className="stat-card">
            <p className="stat-label">Dashboards</p>
            <p className="stat-value">Shared</p>
          </article>
          <article className="stat-card">
            <p className="stat-label">Search</p>
            <p className="stat-value">Live</p>
          </article>
          <article className="stat-card">
            <p className="stat-label">Audit</p>
            <p className="stat-value">Tracked</p>
          </article>
        </div>
      </section>
      <section className="surface-card stack">
        <div>
          <p className="eyebrow">Sign In</p>
          <h2 style={{ margin: "0 0 8px" }}>Welcome back</h2>
          <p className="status-text">Use your local account to sign in to DMARCWatch.</p>
          {passwordChanged ? (
            <p className="status-text">Password updated. Sign in again with your new password.</p>
          ) : null}
        </div>
        <form className="stack" onSubmit={handleSubmit(onSubmit)}>
          <label className="field-label">
            Username
            <input className="field-input" {...register("username")} autoComplete="username" />
            {errors.username ? <span className="error-text">{errors.username.message}</span> : null}
          </label>
          <label className="field-label">
            Password
            <input
              className="field-input"
              type="password"
              {...register("password")}
              autoComplete="current-password"
            />
            {errors.password ? <span className="error-text">{errors.password.message}</span> : null}
          </label>
          {errors.root ? <p className="error-text">{errors.root.message}</p> : null}
          <button className="button-primary" disabled={isSubmitting || status === "loading"} type="submit">
            {isSubmitting ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
