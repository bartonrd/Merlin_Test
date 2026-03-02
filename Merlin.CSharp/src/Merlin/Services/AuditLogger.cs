using System.Text.Json;

namespace Merlin.Services;

/// <summary>Writes JSON-lines audit records to disk.</summary>
public sealed class AuditLogger
{
    private readonly string _path;
    private readonly ILogger<AuditLogger> _logger;
    private readonly SemaphoreSlim _lock = new(1, 1);

    public AuditLogger(string path, ILogger<AuditLogger> logger)
    {
        _path   = path;
        _logger = logger;
    }

    public async Task WriteAsync(object record, CancellationToken ct = default)
    {
        var line = JsonSerializer.Serialize(record);
        await _lock.WaitAsync(ct);
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
            await File.AppendAllTextAsync(_path, line + "\n", ct);
        }
        catch (IOException ex)
        {
            _logger.LogWarning("Audit log write failed: {Error}", ex.Message);
        }
        finally
        {
            _lock.Release();
        }
    }
}
