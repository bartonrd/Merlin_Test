using System.Security.Cryptography;
using System.Text;
using Merlin.Models;
using Merlin.Retrieval;

namespace Merlin.Ingestion;

/// <summary>
/// Orchestrates document ingestion: load → chunk → store in SQLite + VectorStore.
/// Mirrors app/ingestion/ingest.py.
/// </summary>
public sealed class IngestionService
{
    private static readonly HashSet<string> SupportedExtensions =
        new(StringComparer.OrdinalIgnoreCase) { ".txt", ".md", ".pdf", ".docx" };

    private readonly Bm25SearchService _bm25;
    private readonly VectorStore       _store;
    private readonly IEmbeddingService _embedder;
    private readonly string            _vectorPath;

    public IngestionService(
        Bm25SearchService bm25,
        VectorStore store,
        IEmbeddingService embedder,
        string vectorPath)
    {
        _bm25        = bm25;
        _store       = store;
        _embedder    = embedder;
        _vectorPath  = vectorPath;
    }

    /// <summary>
    /// Ingest all supported documents in inputDir.
    /// Returns the number of new chunks inserted.
    /// </summary>
    public async Task<int> IngestDirectoryAsync(
        string inputDir,
        bool clear = false,
        bool skipKnown = true,
        CancellationToken ct = default)
    {
        if (!Directory.Exists(inputDir))
        {
            Console.WriteLine($"[ingest] Input directory not found: {inputDir}");
            return 0;
        }

        if (clear)
        {
            _bm25.DeleteDb();
            _store.Clear();
            Console.WriteLine("[ingest] Cleared existing DB and vector store.");
        }

        _bm25.InitDb();
        _store.Load(_vectorPath);

        var knownIds = skipKnown ? _bm25.GetKnownDocIds() : new HashSet<string>();

        var files = Directory
            .EnumerateFiles(inputDir, "*", SearchOption.AllDirectories)
            .Where(f => SupportedExtensions.Contains(Path.GetExtension(f)))
            .OrderBy(f => f)
            .ToList();

        if (files.Count == 0)
        {
            Console.WriteLine($"[ingest] No supported documents found in {inputDir}");
            return 0;
        }

        var newChunks    = new List<Chunk>();
        var newChunkRows = new List<int>();

        foreach (var filePath in files)
        {
            var docId = ComputeDocId(filePath);
            if (knownIds.Contains(docId))
            {
                Console.WriteLine($"[ingest] Skipping already-indexed: {Path.GetFileName(filePath)}");
                continue;
            }
            try
            {
                var chunks = ProcessFile(filePath);
                var rowIds = _bm25.InsertChunks(chunks);
                newChunks.AddRange(chunks);
                newChunkRows.AddRange(rowIds);
                Console.WriteLine($"[ingest]   {Path.GetFileName(filePath)}: {chunks.Count} chunk(s)");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[ingest]   ERROR processing {Path.GetFileName(filePath)}: {ex.Message}");
            }
        }

        if (newChunks.Count > 0)
        {
            Console.WriteLine($"[ingest] {newChunks.Count} new chunk(s) inserted – rebuilding indexes …");
            _bm25.RebuildFtsIndex();
            await BuildVectorIndexAsync(ct);
            Console.WriteLine("[ingest] Ingestion complete.");
        }
        else
        {
            Console.WriteLine("[ingest] No new documents – indexes unchanged.");
        }

        return newChunks.Count;
    }

    // ── File processing ───────────────────────────────────────────────────────

    private static List<Chunk> ProcessFile(string filePath)
    {
        var text   = DocumentLoaders.LoadText(filePath);
        var docId  = ComputeDocId(filePath);
        var title  = Path.GetFileNameWithoutExtension(filePath)
            .Replace('_', ' ').Replace('-', ' ');
        title = System.Globalization.CultureInfo.CurrentCulture.TextInfo.ToTitleCase(title.ToLower());
        return DocumentChunker.ChunkDocument(text, docId, title, filePath);
    }

    /// <summary>Embed all chunks in the DB and save the vector store.</summary>
    private async Task BuildVectorIndexAsync(CancellationToken ct)
    {
        var rows = _bm25.GetAllChunks();
        if (rows.Count == 0)
        {
            Console.WriteLine("[ingest] No chunks to embed – skipping vector index build.");
            return;
        }

        Console.WriteLine($"[ingest] Embedding {rows.Count} chunk(s) …");
        _store.Clear();

        const int batchSize = 64;
        for (int i = 0; i < rows.Count; i += batchSize)
        {
            var batch = rows.Skip(i).Take(batchSize).ToList();
            var texts = batch.Select(r => r.text).ToList();
            var ids   = batch.Select(r => r.id).ToArray();

            var vectors = await _embedder.EmbedAsync(texts, ct);
            VectorStore.L2NormalizeRows(vectors);
            _store.Add(ids, vectors);
        }

        _store.Save(_vectorPath);
        Console.WriteLine($"[ingest] Vector index saved: {_vectorPath}  ({rows.Count} vectors)");
    }

    /// <summary>Generate a stable doc_id from the file path (first 12 chars of MD5 hex).</summary>
    public static string ComputeDocId(string path)
    {
        var hash = MD5.HashData(Encoding.UTF8.GetBytes(path));
        return Convert.ToHexString(hash)[..12].ToLowerInvariant();
    }
}
