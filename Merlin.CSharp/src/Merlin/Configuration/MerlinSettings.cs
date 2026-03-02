namespace Merlin.Configuration;

/// <summary>Application configuration – mirrors config.py from the Python implementation.</summary>
public class MerlinSettings
{
    // LLM settings
    // LlmMode: "remote" | "none"
    //   remote – connect to an external OpenAI-compatible HTTP server (llama.cpp, Ollama, …)
    //   none   – return retrieved document excerpts without LLM synthesis
    public string LlmMode { get; set; } = "remote";
    public string LlmBaseUrl { get; set; } = "http://localhost:8080";
    public string LlmModel { get; set; } = "local-model";
    public int LlmMaxTokens { get; set; } = 2048;
    public double LlmTemperature { get; set; } = 0.1;

    // Embedding settings
    // EmbedMode: "remote" | "none"
    //   remote – call an OpenAI-compatible /v1/embeddings endpoint (Ollama, LM Studio, …)
    //   none   – skip vector indexing / search (BM25-only mode)
    public string EmbedMode { get; set; } = "remote";
    public string EmbedBaseUrl { get; set; } = "http://localhost:11434";  // Ollama default
    public string EmbedModel { get; set; } = "all-minilm";

    // Retrieval settings
    public int TopKBm25 { get; set; } = 10;
    public int TopKVector { get; set; } = 10;
    public int TopKFinal { get; set; } = 5;
    public double MinVectorScore { get; set; } = 0.3;
    public bool RerankerEnabled { get; set; } = false;

    // Storage paths
    public string DbPath { get; set; } = "./data/db.sqlite";
    public string VectorStorePath { get; set; } = "./data/vectors.bin";
    public string DocsDir { get; set; } = "./docs";
    public string AuditLogPath { get; set; } = "./data/audit.log";

    // Context limits
    public int MaxContextChars { get; set; } = 6000;
}
