/** Status-only card for an evaluation that is still in progress. */
import { motion } from "motion/react";
import { WorkflowStepper } from "../WorkflowStepper";
import { Card } from "../../ui/Card";
import { formatDate, formatDateTime } from "../../utils/dates";
import type { MyOpenEvaluation } from "../../types";

export function OpenCaseCard({ item, index }: { item: MyOpenEvaluation; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.05 }}
    >
      <Card
        title={`پروندهٔ در جریان — ${item.evaluation_code}`}
        actions={
          <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-blue-500" />
            {item.stage_label}
          </span>
        }
      >
        <WorkflowStepper status={item.status} className="mb-4" />
        <p className="text-sm text-gray-600">
          ارزیابی شما از {formatDateTime(item.created_at)} آغاز شده و از{" "}
          {formatDateTime(item.stage_entered_at)} در مرحلهٔ فعلی است.
        </p>
        <p className="mt-1 text-xs text-gray-400">
          امتیازها تا پیش از تأیید نهایی قطعی نیستند و نمایش داده نمی‌شوند.
        </p>
        {item.submission_deadline && (
          <p className="mt-2 text-xs text-gray-500">
            مهلت ثبت ارزیابی این پرونده: {formatDate(item.submission_deadline)}
            {item.submission_deadline_extended ? " (تمدیدشده)" : ""}
          </p>
        )}
      </Card>
    </motion.div>
  );
}
