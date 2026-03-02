using System.Text.Json.Serialization;

namespace Merlin.Models;

// ── Inbound request models ────────────────────────────────────────────────────

public class ChatRequest
{
    public string Message { get; set; } = string.Empty;
    public string? ConversationId { get; set; }
    public bool Expand { get; set; } = false;
}

public class GenerateRequest
{
    public string Prompt { get; set; } = string.Empty;
    public string? SystemPrompt { get; set; }
    public double? Temperature { get; set; }
}

public class OpenAiChatMessage
{
    public string Role { get; set; } = string.Empty;
    public string Content { get; set; } = string.Empty;
}

public class OpenAiChatRequest
{
    public string Model { get; set; } = "local-model";
    public List<OpenAiChatMessage> Messages { get; set; } = new();
    public int? MaxTokens { get; set; }
    public double? Temperature { get; set; }
    public bool Stream { get; set; } = false;
}

// ── Outbound response models ──────────────────────────────────────────────────

public class ChatResponse
{
    public string Answer { get; set; } = string.Empty;
    public List<string> Citations { get; set; } = new();
    public bool IsTriage { get; set; }
    public List<int> ChunkIds { get; set; } = new();
}
