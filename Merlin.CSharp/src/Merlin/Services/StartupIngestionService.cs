using Merlin.Ingestion;
using Merlin.Retrieval;

namespace Merlin.Services;

/// <summary>
/// Background service that ingests documents from docs/ on startup.
/// Mirrors the FastAPI lifespan handler in app/main.py.
/// </summary>
public sealed class StartupIngestionService : IHostedService
{
    private readonly IngestionService _ingestion;
    private readonly string           _docsDir;
    private readonly ILogger<StartupIngestionService> _logger;

    public StartupIngestionService(
        IngestionService ingestion,
        string docsDir,
        ILogger<StartupIngestionService> logger)
    {
        _ingestion = ingestion;
        _docsDir   = docsDir;
        _logger    = logger;
    }

    public async Task StartAsync(CancellationToken ct)
    {
        if (!Directory.Exists(_docsDir))
        {
            _logger.LogInformation("docs/ directory not found – skipping startup ingestion.");
            return;
        }

        _logger.LogInformation("Auto-ingesting documents from {DocsDir} …", _docsDir);
        try
        {
            int newChunks = await _ingestion.IngestDirectoryAsync(_docsDir, skipKnown: true, ct: ct);
            if (newChunks > 0)
                _logger.LogInformation("Startup ingestion complete: {Count} new chunk(s) indexed.", newChunks);
            else
                _logger.LogInformation("Startup ingestion: no new documents found.");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Startup ingestion failed.");
        }
    }

    public Task StopAsync(CancellationToken ct) => Task.CompletedTask;
}
