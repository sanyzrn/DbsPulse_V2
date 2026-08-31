import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient, extractConflictEvaluationId, extractErrorMessage } from "../../api/client";
import { useDebouncedValue, useEvaluations, usePersonnelList } from "../../api/queries";
import { EmployeeProfileModal } from "../../components/EmployeeProfileModal";
import { EvaluationActionButton, type OpenEvaluation } from "../../components/EvaluationActionButton";
import { EvaluationList } from "../../components/EvaluationList";
import { MyEvaluationsPanel } from "../employee/MyEvaluationsPage";
import { RoleOverviewCards } from "../../components/RoleOverviewCards";
import { StatusBadge } from "../../components/StatusBadge";
import { PageHeader, TableSkeleton } from "../../ui/Card";
import { SearchInput } from "../../ui/SearchInput";
import { Table } from "../../ui/Table";
import { isOpenStatus, type Personnel } from "../../types";

export function SupervisorHomePage() {
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [startingId, setStartingId] = useState<number | null>(null);
  const [profilePerson, setProfilePerson] = useState<Personnel | null>(null);
  // مسئول واحد دو کارِ جدا دارد و تا امروز فقط یکی‌شان را داشت: ارزیابیِ
  // زیرمجموعه‌ها. خودش هم ارزیابی می‌شود، ولی صفحهٔ «کارنامه من» پشتِ گاردِ نقشِ
  // «کارمند» بود و او روی آن ۴۰۳ می‌گرفت — نه خودارزیابی می‌توانست بکند و نه
  // نتیجهٔ خودش را می‌دید.
  const [tab, setTab] = useState<"team" | "mine">("team");
  const navigate = useNavigate();
  // مسئول واحدی که شصت نفر زیرمجموعه دارد، تا امروز باید در یک جدولِ بی‌فیلتر
  // اسکرول می‌کرد تا اسم را پیدا کند — در حالی که فهرست ارزیابی‌ها درست پایین‌تر
  // جست‌وجوی کامل داشت. نقطهٔ *شروع* کار، تنها جایی بود که ابزار نداشت.
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const { data, error: loadError, isPending } = usePersonnelList({
    accessible_to_me: true,
    q: debouncedSearch || undefined,
    limit: 1000,
    offset: 0,
  });
  const personnel = data?.items ?? [];

  // برای غیرفعال‌کردن «شروع ارزیابی جدید» وقتی ارزیابی باز از قبل هست (به‌جای
  // کلیک بی‌نتیجه و خطای ۴۰۹) — این فهرست از قبل توسط بک‌اند به ارزیابی‌های
  // خودِ همین مسئول واحد محدود شده است.
  const { data: myEvaluations } = useEvaluations({ limit: 200, offset: 0 });
  // `isOpenStatus` و نه `!== "finalized"`: پروندهٔ **لغوشده** پایان‌یافته است و
  // نباید جلوی شروع ارزیابی تازه را بگیرد.
  const openEvaluationByPersonnel = new Map<number, OpenEvaluation>();
  for (const e of myEvaluations?.items ?? []) {
    if (isOpenStatus(e.status)) {
      openEvaluationByPersonnel.set(e.subject_personnel_id, {
        id: e.id,
        code: e.evaluation_code,
        status: e.status,
      });
    }
  }

  async function startEvaluation(p: Personnel) {
    if (starting) return;
    setStarting(true);
    setStartingId(p.id);
    setError(null);
    try {
      const { data } = await apiClient.post("/evaluations", { subject_personnel_id: p.id });
      navigate(`/evaluations/${data.id}`);
    } catch (err) {
      // اگر ارزیابی باز از قبل وجود دارد، مستقیم به همان پرونده برو
      const existingId = extractConflictEvaluationId(err);
      if (existingId !== null) {
        navigate(`/evaluations/${existingId}`);
        return;
      }
      setError(extractErrorMessage(err));
    } finally {
      setStarting(false);
      setStartingId(null);
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader title="ارزیابی عملکرد" subtitle="ارزیابی افراد زیرمجموعه، و خودارزیابی خودتان" />

      <div
        className="flex gap-1 rounded-2xl border border-gray-200 bg-white p-1"
        role="tablist"
        aria-label="بخش‌های ارزیابی مسئول واحد"
      >
        {([
          { key: "team", label: "ارزیابی زیرمجموعه‌ها" },
          { key: "mine", label: "خودارزیابی من" },
        ] as const).map((item) => (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={tab === item.key}
            onClick={() => setTab(item.key)}
            className={`flex-1 rounded-xl px-4 py-2 text-sm font-semibold transition ${
              tab === item.key
                ? "bg-pulse-600 text-white"
                : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === "mine" && <MyEvaluationsPanel />}

      <div hidden={tab !== "team"} className="space-y-4">
      <RoleOverviewCards />
      <div className="rounded-2xl border border-gray-200 bg-white p-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-base font-bold text-gray-900">فهرست افراد</h2>
          <SearchInput
            widthClass="sm:w-64"
            placeholder="جست‌وجو (نام، کد پرسنلی، عنوان شغلی، واحد)…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        {loadError != null && (
          <p className="mb-2 text-sm text-red-600">{extractErrorMessage(loadError)}</p>
        )}
        {error && <p className="mb-2 text-sm text-red-600">{error}</p>}
        {isPending ? (
          <TableSkeleton rows={4} />
        ) : (
        <Table
          bordered={false}
          headers={["نام", "عنوان شغلی", "واحد", "وضعیت ارزیابی", ""]}
          rowKeys={personnel.map((p) => p.id)}
          emptyMessage={search ? "کسی با این مشخصات پیدا نشد." : "فردی زیرمجموعه شما نیست."}
          rows={personnel.map((p) => [
            <button
              key="name"
              onClick={() => setProfilePerson(p)}
              className="font-medium text-gray-900 underline-offset-4 transition-colors hover:text-pulse-700 hover:underline"
              title="مشاهده پروفایل و روند عملکرد"
            >
              {p.full_name}
            </button>,
            <span key="job" className="text-gray-600">
              {p.job_title}
            </span>,
            <span key="unit" className="text-gray-500">
              {p.org_unit}
            </span>,
            // وضعیت در همین ردیف می‌آید تا مسئول واحد برای فهمیدن اینکه پروندهٔ
            // این فرد کجاست، مجبور نباشد به جدول پایین صفحه نگاه کند و اسم‌ها را
            // بین دو فهرست تطبیق بدهد.
            openEvaluationByPersonnel.has(p.id) ? (
              <StatusBadge key="status" status={openEvaluationByPersonnel.get(p.id)!.status} />
            ) : (
              <span key="status" className="text-xs text-gray-400">
                پروندهٔ باز ندارد
              </span>
            ),
            <EvaluationActionButton
              key="action"
              open={openEvaluationByPersonnel.get(p.id)}
              starting={starting}
              isStartingThis={startingId === p.id}
              onContinue={(id) => navigate(`/evaluations/${id}`)}
              onStart={() => startEvaluation(p)}
            />,
          ])}
        />
        )}
      </div>

      {/* جدول بالا «کارِ امروز» است؛ این یکی بایگانی — شامل پرونده‌های نهایی‌شده و
          دوره‌های گذشته که در فهرست افراد جایی ندارند. */}
      <EvaluationList
        title="سوابق ارزیابی‌های من"
        subtitle="همهٔ پرونده‌هایی که شما نمره داده‌اید، شامل نهایی‌شده‌ها و دوره‌های گذشته"
        tabs={[
          { key: "all", label: "همه" },
          { key: "draft", label: "پیش‌نویس", status: "draft" },
          { key: "submitted", label: "در انتظار بررسی", status: "submitted" },
          { key: "finalized", label: "نهایی‌شده", status: "finalized" },
        ]}
      />
      </div>

      {profilePerson && (
        <EmployeeProfileModal
          personnelId={profilePerson.id}
          personName={profilePerson.full_name}
          onClose={() => setProfilePerson(null)}
        />
      )}
    </div>
  );
}
