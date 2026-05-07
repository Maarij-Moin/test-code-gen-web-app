import api from "./axios.js";

export async function semanticSearch(repoId, query, k = 5) {
  const { data } = await api.post("/repos/query", {
    repo_id: repoId,
    query,
    k_code: k,
    k_tests: 0
  });
  return data;
}
