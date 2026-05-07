import EmptyState from "../common/EmptyState.jsx";
import PromptCard from "./PromptCard.jsx";

export default function GeneratedTestsPanel({ prompts }) {
  if (!prompts?.length) {
    return (
      <EmptyState
        title="No prompts yet"
        message="Run the diff pipeline to generate test prompts."
      />
    );
  }

  return (
    <div className="grid gap-4">
      {prompts.map((prompt, index) => (
        <PromptCard key={`${prompt.file}-${index}`} prompt={prompt} />
      ))}
    </div>
  );
}
