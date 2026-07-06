import { Radar, ShieldCheck, Workflow } from "lucide-react";

const capabilities = [
  {
    icon: Radar,
    title: "Search before you task",
    detail: "RFI search offers existing intelligence products before new work is raised.",
  },
  {
    icon: Workflow,
    title: "Managed end to end",
    detail: "Requests route through assessment, collection, analysis and quality control.",
  },
  {
    icon: ShieldCheck,
    title: "Controlled by design",
    detail: "Role-based access, need-to-know groups and a full audit trail.",
  },
] as const;

export function SplashIntro() {
  return (
    <section className="splash-intro" aria-label="About Istari">
      <div className="splash-intro__logo-wrap">
        <img
          alt="Istari logo"
          className="splash-intro__logo"
          decoding="async"
          height={148}
          src="/istari-logo-256.png"
          width={148}
        />
      </div>
      <h1 className="splash-intro__title">Istari</h1>
      <p className="splash-intro__tagline">Task. Assess. Deliver.</p>
      <p className="splash-intro__pitch">
        The secure workspace for intelligence tasking: route customer requests, task analysts and
        release quality-assured products with every action audited.
      </p>
      <ul className="splash-intro__points">
        {capabilities.map((capability) => (
          <li key={capability.title}>
            <capability.icon aria-hidden="true" size={19} strokeWidth={1.9} />
            <div>
              <strong>{capability.title}</strong>
              <span>{capability.detail}</span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
