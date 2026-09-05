/** «دربارهٔ پلتفرم» و «تغییرات» روی صفحهٔ ورود.
 *
 * پیش‌فرض بسته‌اند: صفحهٔ ورود باید یک کار داشته باشد و آن ورود است. این دو
 * پشت دکمه‌اند تا برای کسی که فقط می‌خواهد وارد شود، سر راه نباشند.
 */
import { useState } from "react";
import { Modal } from "../ui/Modal";
import { APP_NAME, APP_NAME_FA, APP_VERSION } from "../appInfo";
import { ABOUT_SECTIONS, RELEASE_NOTES } from "../content/publicInfo";

type Panel = "about" | "changes" | null;

export function PublicInfoLinks() {
  const [panel, setPanel] = useState<Panel>(null);

  return (
    <>
      <div className="flex items-center justify-center gap-1 text-xs">
        <button
          type="button"
          onClick={() => setPanel("about")}
          className="cursor-pointer rounded-lg px-2 py-1 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-800"
        >
          دربارهٔ پلتفرم
        </button>
        <span aria-hidden className="text-gray-300">·</span>
        <button
          type="button"
          onClick={() => setPanel("changes")}
          className="cursor-pointer rounded-lg px-2 py-1 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-800"
        >
          تغییرات نسخه‌ها
        </button>
      </div>

      {panel === "about" && (
        <Modal title={`دربارهٔ ${APP_NAME}`} size="lg" onClose={() => setPanel(null)}>
          <p className="mb-4 text-sm text-gray-500">{APP_NAME_FA}</p>
          <div className="space-y-5">
            {ABOUT_SECTIONS.map((section) => (
              <section key={section.title}>
                <h3 className="mb-1.5 text-sm font-bold text-gray-900">{section.title}</h3>
                <p className="text-sm leading-relaxed text-gray-600">{section.body}</p>
                {section.bullets && (
                  <ul className="mt-2 space-y-1">
                    {section.bullets.map((item) => (
                      <li
                        key={item}
                        className="flex gap-2 text-sm leading-relaxed text-gray-600"
                      >
                        <span aria-hidden className="mt-2 h-1 w-1 shrink-0 rounded-full bg-pulse-500" />
                        {item}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            ))}
          </div>
        </Modal>
      )}

      {panel === "changes" && (
        <Modal title="تغییرات نسخه‌ها" size="lg" onClose={() => setPanel(null)}>
          <div className="space-y-5">
            {RELEASE_NOTES.map((release) => (
              <section key={release.version}>
                <div className="mb-2 flex flex-wrap items-baseline gap-2">
                  <span
                    dir="ltr"
                    className={`rounded-full px-2.5 py-0.5 font-mono text-xs font-semibold ${
                      release.version === APP_VERSION
                        ? "bg-pulse-600 text-white"
                        : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    v{release.version}
                  </span>
                  <span className="text-xs text-gray-400">{release.date}</span>
                  {release.version === APP_VERSION && (
                    <span className="text-xs font-medium text-pulse-700">نسخهٔ فعلی</span>
                  )}
                </div>
                <ul className="space-y-1">
                  {release.highlights.map((item) => (
                    <li key={item} className="flex gap-2 text-sm leading-relaxed text-gray-600">
                      <span aria-hidden className="mt-2 h-1 w-1 shrink-0 rounded-full bg-gray-300" />
                      {item}
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        </Modal>
      )}
    </>
  );
}
