namespace Merlin.Ingestion;

/// <summary>
/// Abstraction for text embedding services.
/// Implementations include a remote HTTP service and a no-op stub.
/// </summary>
public interface IEmbeddingService
{
    /// <summary>
    /// Embed a batch of texts.  Returns an array of float vectors,
    /// one per input text.  Vectors should be L2-normalised so that
    /// dot-product equals cosine similarity.
    /// </summary>
    Task<float[][]> EmbedAsync(IEnumerable<string> texts, CancellationToken ct = default);

    /// <summary>Returns true if the embedding service is available.</summary>
    Task<bool> IsAvailableAsync(CancellationToken ct = default);
}
