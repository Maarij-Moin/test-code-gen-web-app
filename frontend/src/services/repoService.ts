import { apiClient } from "@/lib/apiClient";
import type { Repository } from "@/types";

const repoCacheKey = "autotest-repositories";

function readLocalRepos(): Repository[] {
  try {
    return JSON.parse(localStorage.getItem(repoCacheKey) ?? "[]") as Repository[];
  } catch {
    return [];
  }
}

function writeLocalRepos(repos: Repository[]) {
  localStorage.setItem(repoCacheKey, JSON.stringify(repos));
}

function repoNameFromUrl(url: string) {
  const parts = url.replace(/\.git$/, "").split("/").filter(Boolean);
  return parts[parts.length - 1] ?? "Repository";
}

export const repoService = {
  async list() {
    return readLocalRepos();
  },
  async connect(repo_url: string) {
    const { data } = await apiClient.post<{
      message: string;
      repo_path: string;
      repo_id: string;
    }>("/repos/clone-and-index", { repo_url });

    const repository: Repository = {
      id: data.repo_id,
      repo_id: data.repo_id,
      name: repoNameFromUrl(repo_url),
      repo_url,
      repo_path: data.repo_path,
      status: "connected",
      last_indexed_at: new Date().toISOString(),
      branch: "main",
      language: "Mixed",
      coverage_delta: 0,
      open_prs: 0,
    };

    const nextRepos = [repository, ...readLocalRepos().filter((repo) => repo.repo_id !== repository.repo_id)];
    writeLocalRepos(nextRepos);
    return repository;
  },
  async get(repoId: string) {
    const repository = readLocalRepos().find((repo) => repo.repo_id === repoId);
    if (!repository) {
      throw new Error("Repository not found in this browser session");
    }
    return repository;
  },
  async update(repository: Repository) {
    const repos = readLocalRepos();
    const nextRepos = repos.map((repo) => (repo.repo_id === repository.repo_id ? repository : repo));
    writeLocalRepos(nextRepos);
    return repository;
  },
};
