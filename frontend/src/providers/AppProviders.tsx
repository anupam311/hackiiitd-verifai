"use client";

import { SessionProvider } from "@/features/auth/SessionProvider";
import { CompareProvider } from "@/features/comparison/CompareProvider";
import { ProfileProvider } from "@/features/profile/ProfileProvider";
import { SavedProvider } from "@/features/saved/SavedProvider";
import { DemoProvider } from "./DemoProvider";
import { ThemeProvider } from "./ThemeProvider";
import { ToastProvider } from "./ToastProvider";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <DemoProvider>
        <ToastProvider>
          <SessionProvider>
            <ProfileProvider>
              <SavedProvider>
                <CompareProvider>{children}</CompareProvider>
              </SavedProvider>
            </ProfileProvider>
          </SessionProvider>
        </ToastProvider>
      </DemoProvider>
    </ThemeProvider>
  );
}
