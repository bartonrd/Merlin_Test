using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Merlin.Ingestion;

/// <summary>
/// Embedding service that calls an OpenAI-compatible /v1/embeddings endpoint.
/// Compatible with Ollama, LM Studio, llama.cpp server, and the OpenAI API.
///
/// Ollama example:  EmbedBaseUrl = "http://localhost:11434", EmbedModel = "all-minilm"
/// llama.cpp:       EmbedBaseUrl = "http://localhost:8080",  EmbedModel = "any"
/// </summary>
public sealed class RemoteEmbeddingService : IEmbeddingService
{
    private readonly HttpClient _http;
    private readonly string _model;

    public RemoteEmbeddingService(HttpClient http, string model)
    {
        _http  = http;
        _model = model;
    }

    public async Task<float[][]> EmbedAsync(IEnumerable<string> texts, CancellationToken ct = default)
    {
        var input = texts.ToList();
        if (input.Count == 0) return [];

        var payload = new { model = _model, input };

        using var response = await _http.PostAsJsonAsync("/v1/embeddings", payload, ct);
        response.EnsureSuccessStatusCode();

        var doc = await response.Content.ReadFromJsonAsync<EmbeddingResponse>(
            cancellationToken: ct) ?? throw new InvalidOperationException("Null embedding response");

        return doc.Data
            .OrderBy(d => d.Index)
            .Select(d => d.Embedding)
            .ToArray();
    }

    public async Task<bool> IsAvailableAsync(CancellationToken ct = default)
    {
        try
        {
            using var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
            cts.CancelAfter(TimeSpan.FromSeconds(5));
            await EmbedAsync(["test"], cts.Token);
            return true;
        }
        catch
        {
            return false;
        }
    }

    // ── JSON shape returned by /v1/embeddings ─────────────────────────────────

    private sealed record EmbeddingResponse(
        [property: JsonPropertyName("data")] List<EmbeddingData> Data);

    private sealed record EmbeddingData(
        [property: JsonPropertyName("index")]     int Index,
        [property: JsonPropertyName("embedding")] float[] Embedding);
}

/// <summary>
/// No-op embedding service used when EmbedMode=none.
/// Vector search will always return empty results, falling back to BM25 only.
/// </summary>
public sealed class NoEmbeddingService : IEmbeddingService
{
    public Task<float[][]> EmbedAsync(IEnumerable<string> texts, CancellationToken ct = default)
        => Task.FromResult(Array.Empty<float[]>());

    public Task<bool> IsAvailableAsync(CancellationToken ct = default)
        => Task.FromResult(false);
}
