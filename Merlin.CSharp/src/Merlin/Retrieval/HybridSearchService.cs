using Merlin.Models;

namespace Merlin.Retrieval;

/// <summary>
/// Hybrid BM25 + vector search with score fusion.
/// Mirrors app/retrieval/hybrid.py.
///
/// Combined score = 0.5 * bm25_norm + 0.5 * vector_norm
/// </summary>
public sealed class HybridSearchService
{
    private readonly Bm25SearchService   _bm25;
    private readonly VectorSearchService _vector;

    public HybridSearchService(Bm25SearchService bm25, VectorSearchService vector)
    {
        _bm25   = bm25;
        _vector = vector;
    }

    public async Task<List<SearchResult>> SearchAsync(
        string query,
        int topKBm25 = 10,
        int topKVector = 10,
        int topKFinal = 5,
        IList<string>? docTypeFilter = null,
        CancellationToken ct = default)
    {
        var bm25Results   = _bm25.Search(query, topKBm25, docTypeFilter);
        var vectorResults = await _vector.SearchAsync(query, topKVector, docTypeFilter, ct);

        // Deduplicate: build a map chunk_id → SearchResult
        var allResults = new Dictionary<int, SearchResult>();
        foreach (var r in bm25Results.Concat(vectorResults))
            allResults.TryAdd(r.ChunkId, r);

        var bm25Norm   = NormalizeScores(bm25Results);
        var vectorNorm = NormalizeScores(vectorResults);

        // Fuse scores
        var fused = new Dictionary<int, double>();
        foreach (var (id, _) in allResults)
        {
            double b = bm25Norm.GetValueOrDefault(id, 0.0);
            double v = vectorNorm.GetValueOrDefault(id, 0.0);
            fused[id] = 0.5 * b + 0.5 * v;
        }

        var ranked = allResults.Values
            .OrderByDescending(r => fused[r.ChunkId])
            .Take(topKFinal)
            .ToList();

        return ranked;
    }

    private static Dictionary<int, double> NormalizeScores(IList<SearchResult> results)
    {
        if (results.Count == 0) return [];

        double minS = results.Min(r => r.Score);
        double maxS = results.Max(r => r.Score);
        double span = maxS - minS;

        if (span == 0)
            return results.ToDictionary(r => r.ChunkId, _ => 1.0);

        return results.ToDictionary(r => r.ChunkId, r => (r.Score - minS) / span);
    }
}
