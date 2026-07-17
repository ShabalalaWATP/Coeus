import {
  configureSearchEmbeddingKey,
  configureSearchEmbeddings,
  getSearchEmbeddingState,
  reindexSearchEmbeddings,
  testSearchEmbeddings,
} from "./admin";

afterEach(() => vi.restoreAllMocks());

test("calls the independent search administration endpoints", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
  vi.stubGlobal("fetch", fetchMock);

  await getSearchEmbeddingState();
  await configureSearchEmbeddingKey("search-key", "csrf");
  await configureSearchEmbeddings("gemini_api", "gemini-embedding-2", true, "csrf");
  await testSearchEmbeddings("csrf");
  await reindexSearchEmbeddings("csrf");

  expect(fetchMock).toHaveBeenNthCalledWith(
    1,
    "http://127.0.0.1:8001/api/v1/admin/search-embeddings",
    expect.objectContaining({ method: "GET" }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/admin/search-embeddings/api-key",
    expect.objectContaining({
      body: JSON.stringify({ apiKey: "search-key" }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf" },
      method: "PUT",
    }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    3,
    "http://127.0.0.1:8001/api/v1/admin/search-embeddings/configuration",
    expect.objectContaining({
      body: JSON.stringify({
        provider: "gemini_api",
        model: "gemini-embedding-2",
        confirmExternalEgress: true,
      }),
    }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    4,
    "http://127.0.0.1:8001/api/v1/admin/search-embeddings/test",
    expect.objectContaining({ method: "POST" }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    5,
    "http://127.0.0.1:8001/api/v1/admin/search-embeddings/reindex",
    expect.objectContaining({ method: "POST" }),
  );
});
