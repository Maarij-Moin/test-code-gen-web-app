import { FolderGit2, Layers, Sparkles } from "lucide-react";
import StatsCard from "../components/dashboard/StatsCard.jsx";
import ActivityPanel from "../components/dashboard/ActivityPanel.jsx";
import RepoOverview from "../components/dashboard/RepoOverview.jsx";
import { useAppContext } from "../context/AppContext.jsx";
import { useRepoContext } from "../context/RepoContext.jsx";

export default function Dashboard() {
  const { activity } = useAppContext();
  const { repoState } = useRepoContext();

  const stats = [
    { label: "Repositories", value: repoState.repoId ? 1 : 0, icon: FolderGit2 },
    { label: "Indexed Chunks", value: repoState.status === "indexed" ? 1200 : 0, icon: Layers },
    { label: "Prompts Generated", value: activity.filter((a) => a.type === "tests").length, icon: Sparkles }
  ];

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {stats.map((stat) => (
          <StatsCard key={stat.label} {...stat} />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <ActivityPanel activity={activity} />
        <RepoOverview />
      </div>
    </div>
  );
}
