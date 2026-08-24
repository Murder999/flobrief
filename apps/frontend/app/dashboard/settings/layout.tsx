import type { ReactNode } from "react";
import { SettingsLayout } from "@/components/settings/SettingsLayout";

export default function AgencySettingsLayout({ children }: { children: ReactNode }) {
  return <SettingsLayout portal="agency">{children}</SettingsLayout>;
}
