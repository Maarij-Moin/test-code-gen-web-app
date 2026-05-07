import api from "./axios.js";

export async function uploadRepo(repoUrl) {
  const { data } = await api.post("/repos/upload", { repo_url: repoUrl });
  return data;
}

export async function indexRepo(repoPath) {
  const { data } = await api.post("/repos/index", { repo_path: repoPath });
  return data;
}

export async function cloneAndIndex(repoUrl) {
  const { data } = await api.post("/repos/clone-and-index", { repo_url: repoUrl });
  return data;
}

export async function updateRepo(repoPath, repoId) {
  const { data } = await api.post("/repos/update", {
    repo_path: repoPath,
    repo_id: repoId
  });
  return data;
}

export async function runDiffPipeline(repoPath, repoId) {
  const { data } = await api.post("/repos/diff-pipeline", {
    repo_path: repoPath,
    repo_id: repoId
  });
  return data;
}

export async function queryRepo(repoId, query, kCode = 5, kTests = 3) {
  const { data } = await api.post("/repos/query", {
    repo_id: repoId,
    query,
    k_code: kCode,
    k_tests: kTests
  });
  return data;
}
