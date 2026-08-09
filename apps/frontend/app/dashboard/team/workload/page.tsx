import { redirect } from "next/navigation";

// The old workload page was dead-code-ridden (N+1 fetch, always-zero
// counters — see git history) and has been replaced in place by the real
// capacity/resource-planning system at /dashboard/capacity.
export default function TeamWorkloadRedirect() {
  redirect("/dashboard/capacity");
}
