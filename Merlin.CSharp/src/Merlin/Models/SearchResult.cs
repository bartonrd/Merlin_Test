namespace Merlin.Models;

/// <summary>A retrieved document chunk with its relevance score.</summary>
public class SearchResult
{
    public int ChunkId { get; set; }
    public double Score { get; set; }
    public string DocId { get; set; } = string.Empty;
    public string Title { get; set; } = string.Empty;
    public string Path { get; set; } = string.Empty;
    public string DocType { get; set; } = string.Empty;
    public string Section { get; set; } = string.Empty;
    public int ChunkIndex { get; set; }
    public string Text { get; set; } = string.Empty;
}
