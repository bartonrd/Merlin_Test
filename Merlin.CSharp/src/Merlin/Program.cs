using Merlin.Configuration;
using Merlin.Ingestion;
using Merlin.Llm;
using Merlin.Reasoning;
using Merlin.Retrieval;
using Merlin.Services;
using Microsoft.Extensions.Options;

var builder = WebApplication.CreateBuilder(args);

// ── Configuration ─────────────────────────────────────────────────────────────
builder.Services.Configure<MerlinSettings>(
    builder.Configuration.GetSection("Merlin"));

// ── HTTP clients ──────────────────────────────────────────────────────────────
// LLM HTTP client
builder.Services.AddHttpClient("llm", (sp, client) =>
{
    var cfg = sp.GetRequiredService<IOptions<MerlinSettings>>().Value;
    client.BaseAddress = new Uri(cfg.LlmBaseUrl.TrimEnd('/'));
    client.Timeout     = TimeSpan.FromSeconds(180);
});

// Embedding HTTP client
builder.Services.AddHttpClient("embed", (sp, client) =>
{
    var cfg = sp.GetRequiredService<IOptions<MerlinSettings>>().Value;
    client.BaseAddress = new Uri(cfg.EmbedBaseUrl.TrimEnd('/'));
    client.Timeout     = TimeSpan.FromSeconds(60);
});

// ── Core services ─────────────────────────────────────────────────────────────

// Embedding service
builder.Services.AddSingleton<IEmbeddingService>(sp =>
{
    var cfg = sp.GetRequiredService<IOptions<MerlinSettings>>().Value;
    if (cfg.EmbedMode == "none")
        return new NoEmbeddingService();

    var factory = sp.GetRequiredService<IHttpClientFactory>();
    var http    = factory.CreateClient("embed");
    return new RemoteEmbeddingService(http, cfg.EmbedModel);
});

// BM25 / SQLite
builder.Services.AddSingleton<Bm25SearchService>(sp =>
{
    var cfg = sp.GetRequiredService<IOptions<MerlinSettings>>().Value;
    return new Bm25SearchService(cfg.DbPath);
});

// Vector store (in-memory + disk)
builder.Services.AddSingleton<VectorStore>();

// Vector search
builder.Services.AddSingleton<VectorSearchService>(sp =>
{
    var cfg     = sp.GetRequiredService<IOptions<MerlinSettings>>().Value;
    var store   = sp.GetRequiredService<VectorStore>();
    var embedder = sp.GetRequiredService<IEmbeddingService>();
    var bm25    = sp.GetRequiredService<Bm25SearchService>();
    return new VectorSearchService(store, embedder, bm25, cfg.VectorStorePath, cfg.MinVectorScore);
});

// Hybrid search
builder.Services.AddSingleton<HybridSearchService>();

// Query router
builder.Services.AddSingleton<QueryRouter>(sp =>
{
    var cfg    = sp.GetRequiredService<IOptions<MerlinSettings>>().Value;
    var hybrid = sp.GetRequiredService<HybridSearchService>();
    return new QueryRouter(hybrid, cfg.TopKBm25, cfg.TopKVector, cfg.TopKFinal);
});

// LLM client
builder.Services.AddSingleton<ILlmClient>(sp =>
{
    var cfg     = sp.GetRequiredService<IOptions<MerlinSettings>>().Value;
    var factory = sp.GetRequiredService<IHttpClientFactory>();

    if (cfg.LlmMode == "none")
        return new NoLlmClient();

    var http = factory.CreateClient("llm");
    return new RemoteLlmClient(http, cfg.LlmModel);
});

// Ingestion service
builder.Services.AddSingleton<IngestionService>(sp =>
{
    var cfg      = sp.GetRequiredService<IOptions<MerlinSettings>>().Value;
    var bm25     = sp.GetRequiredService<Bm25SearchService>();
    var store    = sp.GetRequiredService<VectorStore>();
    var embedder = sp.GetRequiredService<IEmbeddingService>();
    return new IngestionService(bm25, store, embedder, cfg.VectorStorePath);
});

// Audit logger
builder.Services.AddSingleton<AuditLogger>(sp =>
{
    var cfg    = sp.GetRequiredService<IOptions<MerlinSettings>>().Value;
    var logger = sp.GetRequiredService<ILogger<AuditLogger>>();
    return new AuditLogger(cfg.AuditLogPath, logger);
});

// Startup ingestion
builder.Services.AddSingleton<StartupIngestionService>(sp =>
{
    var cfg       = sp.GetRequiredService<IOptions<MerlinSettings>>().Value;
    var ingestion = sp.GetRequiredService<IngestionService>();
    var logger    = sp.GetRequiredService<ILogger<StartupIngestionService>>();
    return new StartupIngestionService(ingestion, cfg.DocsDir, logger);
});
builder.Services.AddHostedService(sp => sp.GetRequiredService<StartupIngestionService>());

// ── MVC / API ─────────────────────────────────────────────────────────────────
builder.Services.AddControllers()
    .AddJsonOptions(opts =>
    {
        opts.JsonSerializerOptions.PropertyNamingPolicy =
            System.Text.Json.JsonNamingPolicy.SnakeCaseLower;
    });

// ── Build app ─────────────────────────────────────────────────────────────────
var app = builder.Build();

app.UseStaticFiles();   // serves wwwroot/ (chat UI)
app.MapControllers();

app.Run();

// Make Program accessible to the test project
public partial class Program { }
