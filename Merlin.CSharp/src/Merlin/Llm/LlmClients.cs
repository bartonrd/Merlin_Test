using System.Net.Http.Json;
using System.Text.Json.Serialization;

namespace Merlin.Llm;

/// <summary>
/// LLM client for a remote OpenAI-compatible API server.
/// Mirrors app/llm/client.py LLMClient (LLM_MODE=remote).
/// </summary>
public sealed class RemoteLlmClient : ILlmClient
{
    private readonly HttpClient _http;
    private readonly string     _model;

    public RemoteLlmClient(HttpClient http, string model)
    {
        _http  = http;
        _model = model;
    }

    public async Task<string> ChatAsync(
        IEnumerable<ChatMessage> messages,
        int maxTokens,
        double temperature,
        CancellationToken ct = default)
    {
        var payload = new
        {
            model       = _model,
            messages    = messages.Select(m => new { role = m.Role, content = m.Content }),
            max_tokens  = maxTokens,
            temperature,
            stream      = false,
        };

        HttpResponseMessage response;
        try
        {
            response = await _http.PostAsJsonAsync("/v1/chat/completions", payload, ct);
            response.EnsureSuccessStatusCode();
        }
        catch (HttpRequestException ex) when (ex.InnerException is System.Net.Sockets.SocketException)
        {
            throw new InvalidOperationException(
                $"Cannot connect to LLM server. " +
                "Is the server running? " +
                "Tip: set LLM_MODE=none in appsettings.json to use Merlin without an LLM server.", ex);
        }
        catch (TaskCanceledException ex) when (!ct.IsCancellationRequested)
        {
            throw new InvalidOperationException(
                "LLM server did not respond in time. " +
                "The model may still be loading or the request was too large.", ex);
        }
        catch (HttpRequestException ex)
        {
            throw new InvalidOperationException(
                $"LLM server returned an error: {ex.Message}", ex);
        }

        var doc = await response.Content.ReadFromJsonAsync<ChatCompletionResponse>(
            cancellationToken: ct) ?? throw new InvalidOperationException("Null LLM response");

        if (doc.Choices is not { Count: > 0 })
            throw new InvalidOperationException($"Unexpected LLM response: no choices");

        return doc.Choices[0].Message.Content;
    }

    public bool HealthCheck()
    {
        try
        {
            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(5));
            var res = _http.GetAsync("/health", cts.Token).GetAwaiter().GetResult();
            return (int)res.StatusCode < 500;
        }
        catch
        {
            return false;
        }
    }

    // ── JSON response shapes ──────────────────────────────────────────────────

    private sealed record ChatCompletionResponse(
        [property: JsonPropertyName("choices")] List<Choice> Choices);

    private sealed record Choice(
        [property: JsonPropertyName("message")] AssistantMessage Message);

    private sealed record AssistantMessage(
        [property: JsonPropertyName("content")] string Content);
}

/// <summary>
/// Fallback LLM client that returns retrieved document excerpts without LLM synthesis.
/// Mirrors app/llm/client.py NoLLMClient (LLM_MODE=none).
/// </summary>
public sealed class NoLlmClient : ILlmClient
{
    private const string Header =
        "**No LLM configured** – showing the most relevant document excerpts below.\n" +
        "Set `LLM_MODE=remote` (external server) in appsettings.json for AI-generated answers.\n\n" +
        "---\n\n";

    public Task<string> ChatAsync(
        IEnumerable<ChatMessage> messages,
        int maxTokens,
        double temperature,
        CancellationToken ct = default)
    {
        var userContent = messages
            .FirstOrDefault(m => m.Role == "user")?.Content ?? string.Empty;

        // Extract the <context> block if present
        var match = System.Text.RegularExpressions.Regex.Match(
            userContent, @"<context>(.*?)</context>",
            System.Text.RegularExpressions.RegexOptions.Singleline);

        var contextText = match.Success ? match.Groups[1].Value.Trim() : userContent;
        return Task.FromResult(Header + contextText);
    }

    public bool HealthCheck() => true;
}
