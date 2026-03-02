using Merlin.Models;
using Merlin.Retrieval;

namespace Merlin.Reasoning;

/// <summary>
/// Query routing: decide retrieval strategy based on input type.
/// Mirrors app/reasoning/router.py.
/// </summary>
public sealed class QueryRouter
{
    private readonly HybridSearchService _hybrid;
    private readonly int _topKBm25;
    private readonly int _topKVector;
    private readonly int _topKFinal;

    public QueryRouter(
        HybridSearchService hybrid,
        int topKBm25   = 10,
        int topKVector = 10,
        int topKFinal  = 5)
    {
        _hybrid    = hybrid;
        _topKBm25  = topKBm25;
        _topKVector = topKVector;
        _topKFinal = topKFinal;
    }

    /// <summary>
    /// Determine query type and retrieve relevant chunks.
    /// Returns (results, isTriage).
    /// </summary>
    public async Task<(List<SearchResult> results, bool isTriage)> RouteAndRetrieveAsync(
        string query,
        CancellationToken ct = default)
    {
        bool isTriage = LogParser.IsErrorLog(query);

        List<string> docTypeFilter;
        string searchQuery;

        if (isTriage)
        {
            var sig = LogParser.ParseLogSignature(query);
            searchQuery  = LogParser.BuildSearchQuery(query, sig);
            docTypeFilter = ["incident", "runbook", "arch"];
        }
        else
        {
            searchQuery  = query;
            docTypeFilter = ["runbook", "arch", "general"];
        }

        var results = await _hybrid.SearchAsync(
            searchQuery, _topKBm25, _topKVector, _topKFinal, docTypeFilter, ct);

        // If filtered search returned nothing, fall back to an unfiltered search
        if (results.Count == 0)
        {
            results = await _hybrid.SearchAsync(
                searchQuery, _topKBm25, _topKVector, _topKFinal, null, ct);
        }

        return (results, isTriage);
    }
}
