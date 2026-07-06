import { EvaluationList } from "../../components/EvaluationList";

export function CeoHomePage() {
  return (
    <EvaluationList
      title="پرونده‌های ارزیابی"
      tabs={[
        { key: "pending", label: "در انتظار تأیید نهایی", status: "deputy_approved" },
        { key: "finalized", label: "نهایی‌شده", status: "finalized" },
        { key: "all", label: "همهٔ پرونده‌های من" },
      ]}
    />
  );
}
