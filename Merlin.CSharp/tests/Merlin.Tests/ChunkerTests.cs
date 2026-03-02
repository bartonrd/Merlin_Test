using Merlin.Ingestion;
using Merlin.Models;

namespace Merlin.Tests;

/// <summary>Tests for DocumentChunker – mirrors tests/test_chunking.py</summary>
public class ChunkerTests
{
    [Fact]
    public void DetectDocType_Runbook()
    {
        var text = "# Symptoms\nApp crashes\n## Cause\nMemory leak";
        Assert.Equal("runbook", DocumentChunker.DetectDocType("database runbook", text));
    }

    [Fact]
    public void DetectDocType_Incident()
    {
        var text = "# What Happened\n## Root Cause\nBug in code";
        Assert.Equal("incident", DocumentChunker.DetectDocType("INC-2024-001 postmortem", text));
    }

    [Fact]
    public void DetectDocType_Arch()
    {
        var text = "# Platform Architecture Overview\n## Services\nThe platform has many services.";
        Assert.Equal("arch", DocumentChunker.DetectDocType("architecture overview", text));
    }

    [Fact]
    public void SplitBySize_ShortText_SingleChunk()
    {
        var text   = "This is a short text.";
        var chunks = DocumentChunker.SplitBySize(text, maxSize: 200, overlap: 20);
        Assert.Single(chunks);
        Assert.Equal(text, chunks[0]);
    }

    [Fact]
    public void SplitBySize_LongText_MultipleChunks()
    {
        var text   = string.Concat(Enumerable.Repeat("word ", 200));
        var chunks = DocumentChunker.SplitBySize(text, maxSize: 100, overlap: 20);
        Assert.True(chunks.Count > 1);
        foreach (var chunk in chunks)
            Assert.True(chunk.Length <= 150); // allow some margin for overlap
    }

    [Fact]
    public void SplitBySize_Overlap_WordsCarriedForward()
    {
        var text   = string.Join(" ", Enumerable.Range(0, 100).Select(i => $"word{i}"));
        var chunks = DocumentChunker.SplitBySize(text, maxSize: 50, overlap: 15);
        Assert.True(chunks.Count >= 2);

        var lastWordsOfFirst  = chunks[0].Split(' ')[^2..];
        var firstWordsOfSecond = chunks[1].Split(' ')[..3];
        Assert.True(lastWordsOfFirst.Intersect(firstWordsOfSecond).Any());
    }

    [Fact]
    public void ChunkDocument_Runbook()
    {
        var text = """
            # Test Runbook
            ## Symptoms
            App is down
            ## Cause
            Memory exhausted
            ## Procedure
            Restart the service
            ## Verification
            Check health endpoint
            """;

        var chunks = DocumentChunker.ChunkDocument(text, "rb-001", "Test Runbook", "/docs/test.md", "runbook");
        Assert.NotEmpty(chunks);
        Assert.All(chunks, c =>
        {
            Assert.Equal("rb-001", c.DocId);
            Assert.Equal("runbook", c.DocType);
            Assert.NotEmpty(c.Text);
        });
    }

    [Fact]
    public void ChunkDocument_Incident()
    {
        var text = """
            # INC-2024-001
            ## What Happened
            Service was down
            ## Root Cause
            Database lock
            ## Fix
            Restarted the pod
            ## Prevention
            Added monitoring
            """;

        var chunks = DocumentChunker.ChunkDocument(text, "inc-001", "INC-2024-001", "/docs/inc.md", "incident");
        Assert.NotEmpty(chunks);
        Assert.All(chunks, c =>
        {
            Assert.Equal("inc-001", c.DocId);
            Assert.Equal("incident", c.DocType);
        });
    }

    [Fact]
    public void ChunkDocument_General()
    {
        var text = string.Concat(Enumerable.Repeat("word ", 400));
        var chunks = DocumentChunker.ChunkDocument(text, "gen-001", "General Doc", "/docs/gen.md", "general");
        Assert.NotEmpty(chunks);
    }

    [Fact]
    public void ChunkDocument_AutoDetectsType()
    {
        var text = "# Symptoms\nApp crashes\n## Cause\nOOM\n## Procedure\nRestart";
        var chunks = DocumentChunker.ChunkDocument(text, "rb-auto", "DB Runbook", "/docs/rb.md");
        Assert.All(chunks, c => Assert.Equal("runbook", c.DocType));
    }

    [Fact]
    public void ChunkDocument_IndicesAreSequential()
    {
        var text = string.Concat(Enumerable.Repeat("word ", 600));
        var chunks = DocumentChunker.ChunkDocument(text, "seq-001", "Seq Doc", "/docs/seq.md", "general");
        var indices = chunks.Select(c => c.ChunkIndex).ToList();
        Assert.Equal(Enumerable.Range(0, indices.Count).ToList(), indices);
    }
}
