import { StoreWorkspaceNav } from "./StoreWorkspaceNav";
import { PersonalLibraryPanel } from "./PersonalLibraryPanel";

export default function StoreLibraryPage() {
  return (
    <div className="store-page">
      <section className="overview-hero" aria-labelledby="store-library-title">
        <div>
          <span className="eyebrow">Intelligence Store</span>
          <h1 id="store-library-title">My Library</h1>
          <p>Your private saved intelligence and personal folders.</p>
        </div>
      </section>
      <StoreWorkspaceNav />
      <PersonalLibraryPanel defaultOpen />
    </div>
  );
}
