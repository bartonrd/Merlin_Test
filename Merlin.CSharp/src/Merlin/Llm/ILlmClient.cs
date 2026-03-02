namespace Merlin.Llm;

public record ChatMessage(string Role, string Content);

/// <summary>Abstraction over different LLM backends.</summary>
public interface ILlmClient
{
    Task<string> ChatAsync(
        IEnumerable<ChatMessage> messages,
        int maxTokens,
        double temperature,
        CancellationToken ct = default);

    bool HealthCheck();
}
