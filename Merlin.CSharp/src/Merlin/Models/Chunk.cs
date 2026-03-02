namespace Merlin.Models;

/// <summary>Represents a document chunk stored in the index.</summary>
public class Chunk
{
    public string DocId { get; set; } = string.Empty;
    public string Title { get; set; } = string.Empty;
    public string Path { get; set; } = string.Empty;
    /// <summary>runbook | arch | incident | general</summary>
    public string DocType { get; set; } = string.Empty;
    public string Section { get; set; } = string.Empty;
    public int ChunkIndex { get; set; }
    public string Text { get; set; } = string.Empty;
    public string? Timestamp { get; set; }
}
