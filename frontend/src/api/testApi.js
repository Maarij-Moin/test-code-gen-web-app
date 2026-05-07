import api from "./axios.js";

export async function generateTests(repoPath, repoId) {
  const { data } = await api.post("/tests/generate", {
    repo_path: repoPath,
    repo_id: repoId
  });
  return data;
}

export async function updateTestVectorstore(repoPath, repoId) {
  const { data } = await api.post("/tests/update", {
    repo_path: repoPath,
    repo_id: repoId
  });
  return data;
}

export async function queryTestChunks(repoId, query, k = 5) {
  const { data } = await api.post("/tests/query-tests", {
    repo_id: repoId,
    query,
    k
  });
  return data;
}
