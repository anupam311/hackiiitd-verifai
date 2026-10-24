import type { Metadata } from "next";
import { ProfileView } from "@/features/profile/ProfileView";

export const metadata: Metadata = { title: "Applicant Profile" };

export default function ProfilePage() {
  return <ProfileView />;
}
