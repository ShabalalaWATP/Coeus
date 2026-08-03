import { PersonalLibraryPanel } from "./PersonalLibraryPanel";
import { StoreWorkspaceHeader } from "./StoreWorkspaceHeader";

export default function StoreLibraryPage() {
  return (
    <div className="store-page">
      <StoreWorkspaceHeader
        description="Your private saved intelligence and personal folders."
        title="My Library"
        titleId="store-library-title"
      />
      {/* The library is the page here, so it needs no open or close control. */}
      <PersonalLibraryPanel alwaysOpen />
    </div>
  );
}
