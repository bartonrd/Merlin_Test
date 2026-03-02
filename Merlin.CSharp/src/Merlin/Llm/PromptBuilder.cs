using Merlin.Models;

namespace Merlin.Llm;

/// <summary>
/// Prompt building utilities.
/// Mirrors app/llm/prompting.py.
/// </summary>
public static class PromptBuilder
{
    private const string SystemPrompt = """
        You are an expert internal document assistant and incident triage specialist.
        You have access to internal runbooks, architecture documents, and incident history.

        RULES:
        1. Always cite sources using format: [doc_title §section:chunk_N]
        2. If information comes from documents, state it as fact with citation.
        3. If you are inferring or the answer is not in the documents, label it as [Inference] and explain your reasoning and uncertainty.
        4. Never fabricate runbook steps or incident details.
        5. Be detailed but concise. Default to concise answers unless asked to expand.
        6. Structure your answers clearly.
        """;

    private const string TriageSystemPrompt = """
        You are an expert SRE and incident triage specialist.
        You are analyzing error logs or stack traces and comparing them to known incidents and runbooks.

        RULES (SAME AS ABOVE, PLUS):
        7. Use the "Triage Mode" output format:
           ## Likely Cause (max 3, ranked)
           ## Safest Next Steps (read-only → reversible → risky)
           ## Verification Steps
           ## If Still Failing
           ## Confidence: High/Med/Low [reason]
        8. Always cite similar incidents and runbooks with format: [doc_title §section:chunk_N]
        9. Never guess at infrastructure specifics not found in documents.
        """;

    private const string ExpandInstruction =
        "\n\nThe user has asked you to expand on your previous answer. " +
        "Provide more detail, additional context, and deeper explanation.";

    public static string FormatCitation(SearchResult result) =>
        $"[{result.Title} §{result.Section}:chunk_{result.ChunkIndex}]";

    public static string FormatContext(IList<SearchResult> results, int maxChars = 6000)
    {
        var lines = new System.Text.StringBuilder("<context>");
        int total = "<context>".Length + "</context>".Length;

        foreach (var result in results)
        {
            var header =
                $"\n[Source: {result.Title} | section: {result.Section} " +
                $"| chunk: {result.ChunkIndex} | type: {result.DocType}]\n";
            var block = header + result.Text.Trim() + "\n";

            if (total + block.Length > maxChars) break;
            lines.Append(block);
            total += block.Length;
        }

        lines.Append("</context>");
        return lines.ToString();
    }

    public static List<ChatMessage> BuildChatMessages(
        string userQuery,
        IList<SearchResult> contextResults,
        bool isTriage = false,
        bool expand = false,
        int maxContextChars = 6000,
        string? systemPrompt = null)
    {
        systemPrompt ??= isTriage ? TriageSystemPrompt : SystemPrompt;

        var contextBlock = FormatContext(contextResults, maxContextChars);
        var userContent  = $"{contextBlock}\n\n{userQuery}";
        if (expand) userContent += ExpandInstruction;

        return
        [
            new ChatMessage("system", systemPrompt),
            new ChatMessage("user",   userContent),
        ];
    }
}
