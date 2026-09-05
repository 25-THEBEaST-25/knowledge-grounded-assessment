import { redirect } from "next/navigation";

// The dashboard moved to /faculty as part of the Faculty/Student portal
// split. This keeps the old URL working rather than silently 404ing it.
export default function LegacyDashboardRedirect() {
  redirect("/faculty");
}
