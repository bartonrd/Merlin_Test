using Merlin.Ingestion;
using Merlin.Models;

namespace Merlin.Retrieval;

/// <summary>
/// Vector search using the in-memory VectorStore.
/// Mirrors app/retrieval/faiss_store.py.
/// </summary>
public sealed class VectorSearchService
{
    private readonly VectorStore       _store;
    private readonly IEmbeddingService _embedder;
    private readonly Bm25SearchService _bm25;      // used for metadata look-up
    private readonly string            _vectorPath;
    private readonly double            _minScore;

    public VectorSearchService(
        VectorStore store,
        IEmbeddingService embedder,
        Bm25SearchService bm25,
        string vectorPath,
        double minScore = 0.3)
    {
        _store      = store;
        _embedder   = embedder;
        _bm25       = bm25;
        _vectorPath = vectorPath;
        _minScore   = minScore;
    }

    public async Task<List<SearchResult>> SearchAsync(
        string query,
        int topK = 10,
        IList<string>? docTypeFilter = null,
        CancellationToken ct = default)
    {
        if (_store.Count == 0) return [];

        var queryVecs = await _embedder.EmbedAsync([query], ct);
        if (queryVecs.Length == 0) return [];

        var queryVec = queryVecs[0];
        VectorStore.L2Normalize(queryVec);

        int fetchK = docTypeFilter is { Count: > 0 } ? topK * 3 : topK;
        fetchK = Math.Min(fetchK, _store.Count);
        if (fetchK == 0) return [];

        var candidates = _store.Search(queryVec, fetchK);

        var results = new List<SearchResult>();
        foreach (var (dbId, score) in candidates)
        {
            if (score < _minScore) continue;
            var chunk = _bm25.GetChunkById(dbId);
            if (chunk is null) continue;
            if (docTypeFilter is { Count: > 0 } && !docTypeFilter.Contains(chunk.DocType)) continue;

            chunk.Score = score;
            results.Add(chunk);
        }

        results.Sort((a, b) => b.Score.CompareTo(a.Score));
        return results.Count > topK ? results[..topK] : results;
    }
}
