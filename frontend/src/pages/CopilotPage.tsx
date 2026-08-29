import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { PageHeader } from "../ui/Card";
import type { AiStatus } from "../types";
import { CopilotPanel } from "../components/copilot/CopilotPanel";

/**
 * همکار در صفحهٔ کامل — همان گفت‌وگو، با جای نفس‌کشیدن بیشتر:
 * تاریخچه همیشه دیده می‌شود و جدول‌های گزارش جا دارند.
 */
export default function CopilotPage() {
  const { data: status } = useQuery({
    queryKey: ["ai", "status"],
    queryFn: async () => (await apiClient.get<AiStatus>("/ai/status")).data,
    staleTime: 0,
    refetchOnMount: "always",
  });

  return (
    <div className="space-y-4">
      <PageHeader title="همکار هوشمند" subtitle="همان اختیاراتِ خودتان، در یک گفت‌وگو" />
      <div className="flex h-[calc(100vh-14rem)] min-h-[480px] flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
        <CopilotPanel status={status} variant="page" />
      </div>
    </div>
  );
}
