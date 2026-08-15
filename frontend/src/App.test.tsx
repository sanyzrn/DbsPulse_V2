/** نشانی‌های قدیمی نباید بشکنند.
 *
 * «برنامه‌های بهبود» از /hr/improvement-plans به /improvement-plans منتقل شد، چون
 * صفحه‌ای که مسئول واحد و معاونت هم باز می‌کنند نباید در نشانی‌اش بگوید مالِ
 * منابع انسانی است. ولی اعلان‌هایی که *پیش از این* ساخته شده‌اند لینک قدیمی را در
 * دیتابیس دارند و زمان‌بند هم قبلاً همان را فرستاده است. اگر ریدایرکت شناسه را
 * نگه ندارد، آن اعلان‌ها کاربر را به فهرست خالی می‌برند نه به برنامهٔ خودشان.
 */
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Navigate, Route, Routes, useParams } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { LegacyImprovementPlanRedirect } from "./App";

function Landing() {
  const { id } = useParams();
  return <p>{`plan:${id ?? "list"}`}</p>;
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/improvement-plans" element={<Landing />} />
        <Route path="/improvement-plans/:id" element={<Landing />} />
        <Route
          path="/hr/improvement-plans"
          element={<Navigate to="/improvement-plans" replace />}
        />
        <Route path="/hr/improvement-plans/:id" element={<LegacyImprovementPlanRedirect />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ریدایرکت نشانی قدیمی برنامه‌های بهبود", () => {
  it("فهرست را به نشانی جدید می‌برد", () => {
    renderAt("/hr/improvement-plans");
    expect(screen.getByText("plan:list")).toBeInTheDocument();
  });

  it("شناسهٔ برنامه را در مسیر حفظ می‌کند", () => {
    renderAt("/hr/improvement-plans/42");
    expect(screen.getByText("plan:42")).toBeInTheDocument();
  });
});
