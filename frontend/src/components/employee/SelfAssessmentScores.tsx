import type { Indicator, SelfAssessment } from "../../types";

export const ASSESSMENT_SECTIONS = [
  { key: "general", title: "شاخص‌های عمومی", description: "رفتار حرفه‌ای و مهارت‌های مشترک", tone: "bg-pulse-50 text-pulse-800" },
  { key: "specialized", title: "شاخص‌های تخصصی", description: "عملکرد و مهارت‌های مرتبط با شغل", tone: "bg-indigo-50 text-indigo-800" },
] as const;

export function SelfAssessmentScores({ scores, indicators }: {
  scores: SelfAssessment["scores"];
  indicators: Indicator[];
}) {
  const byId = new Map(indicators.map((indicator) => [indicator.id, indicator]));
  const groups = [
    ...ASSESSMENT_SECTIONS,
    { key: "unknown", title: "سایر شاخص‌ها", description: "", tone: "bg-gray-100 text-gray-700" },
  ];
  return (
    <div className="space-y-5">
      {groups.map((section) => {
        const rows = scores
          .filter((row) => (byId.get(row.indicator_id)?.section ?? "unknown") === section.key)
          .toSorted((a, b) => (byId.get(a.indicator_id)?.display_order ?? 0) - (byId.get(b.indicator_id)?.display_order ?? 0));
        if (!rows.length) return null;
        return (
          <section key={section.key} aria-label={section.title} className="overflow-hidden rounded-2xl border border-gray-200">
            <div className={`flex items-center justify-between gap-3 px-4 py-3 ${section.tone}`}>
              <h3 className="text-sm font-bold">{section.title}</h3>
              <span className="text-xs">{rows.length.toLocaleString("fa-IR")} شاخص</span>
            </div>
            <div className="divide-y divide-gray-100 bg-white">
              {rows.map((row) => (
                <div key={row.indicator_id} className="flex items-start justify-between gap-4 p-4">
                  <div className="min-w-0 space-y-1">
                    <p className="text-xs font-medium text-gray-500">{byId.get(row.indicator_id)?.category}</p>
                    <p className="text-sm leading-7 text-gray-800">{byId.get(row.indicator_id)?.description ?? `شاخص ${row.indicator_id}`}</p>
                    {row.note && <p className="whitespace-pre-wrap text-sm leading-6 text-gray-500">{row.note}</p>}
                  </div>
                  <span className="shrink-0 rounded-xl bg-gray-50 px-3 py-2 text-sm font-bold text-pulse-700">{row.score.toLocaleString("fa-IR")} از ۵</span>
                </div>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
