"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { apiClient, ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/context";
import type { UpdatePasswordBody, UpdatePasswordResponse } from "@/lib/api/types";

const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, "Current password is required"),
    new_password: z.string().min(12, "Password must be at least 12 characters"),
    confirm_password: z.string().min(1, "Confirm your new password"),
  })
  .refine((values) => values.new_password === values.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type ChangePasswordValues = z.infer<typeof changePasswordSchema>;

export default function ChangePasswordPage() {
  const router = useRouter();
  const { clearAuth, logout, passwordChangeRequired, status } = useAuth();
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
    setError,
  } = useForm<ChangePasswordValues>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: {
      current_password: "",
      new_password: "",
      confirm_password: "",
    },
  });

  useEffect(() => {
    if (status === "anonymous") {
      router.replace("/login");
      return;
    }
    if (status === "authenticated" && !passwordChangeRequired) {
      router.replace("/domains");
    }
  }, [passwordChangeRequired, router, status]);

  async function onSubmit(values: ChangePasswordValues) {
    try {
      const body: UpdatePasswordBody = {
        current_password: values.current_password,
        new_password: values.new_password,
      };
      await apiClient.put<UpdatePasswordResponse>("/api/v1/auth/password", body);
      clearAuth();
      router.replace("/login?passwordChanged=1");
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Password update failed";
      setError("root", { message });
    }
  }

  if (status === "loading") {
    return (
      <main className="app-frame">
        <section className="surface-card">
          <p className="status-text">Checking your session...</p>
        </section>
      </main>
    );
  }

  if (status !== "authenticated" || !passwordChangeRequired) {
    return null;
  }

  return (
    <main className="app-frame app-frame-auth auth-shell">
      <section className="hero-card stack">
        <p className="eyebrow">Security update</p>
        <h1 className="page-title">Change your temporary password before continuing.</h1>
        <p className="lede">
          This account is using a generated password. Set a new password with at least 12 characters to unlock the app.
        </p>
      </section>
      <section className="surface-card stack">
        <div>
          <p className="eyebrow">Required now</p>
          <h2 style={{ margin: "0 0 8px" }}>Choose a new password</h2>
          <p className="status-text">When you save it, every current session for this account will be signed out.</p>
        </div>
        <form className="stack" onSubmit={handleSubmit(onSubmit)}>
          <label className="field-label">
            Current password
            <input className="field-input" type="password" {...register("current_password")} autoComplete="current-password" />
            {errors.current_password ? <span className="error-text">{errors.current_password.message}</span> : null}
          </label>
          <label className="field-label">
            New password
            <input className="field-input" type="password" {...register("new_password")} autoComplete="new-password" />
            {errors.new_password ? <span className="error-text">{errors.new_password.message}</span> : null}
          </label>
          <label className="field-label">
            Confirm new password
            <input className="field-input" type="password" {...register("confirm_password")} autoComplete="new-password" />
            {errors.confirm_password ? <span className="error-text">{errors.confirm_password.message}</span> : null}
          </label>
          {errors.root ? <p className="error-text">{errors.root.message}</p> : null}
          <div className="dialog-actions">
            <button className="button-secondary" onClick={() => void logout()} type="button">
              Log out
            </button>
            <button className="button-primary" disabled={isSubmitting} type="submit">
              {isSubmitting ? "Saving..." : "Update password"}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}
