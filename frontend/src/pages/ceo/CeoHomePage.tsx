import { EvaluationList } from "../../components/EvaluationList";

export function CeoHomePage() {
  return <EvaluationList title="پرونده‌های در انتظار تأیید نهایی" statusFilter="deputy_approved" />;
}
