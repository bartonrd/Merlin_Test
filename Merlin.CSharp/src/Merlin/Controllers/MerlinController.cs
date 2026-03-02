using System.Text.Json;
using Merlin.Configuration;
using Merlin.Llm;
using Merlin.Models;
using Merlin.Reasoning;
using Merlin.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Options;

namespace Merlin.Controllers;

[ApiController]
public sealed class MerlinController : ControllerBase
{
    private readonly QueryRouter        _router;
    private readonly ILlmClient         _llm;
    private readonly AuditLogger        _audit;
    private readonly MerlinSettings     _settings;
    private readonly ILogger<MerlinController> _logger;

    public MerlinController(
        QueryRouter router,
        ILlmClient llm,
        AuditLogger audit,
        IOptions<MerlinSettings> settings,
        ILogger<MerlinController> logger)
    {
        _router   = router;
        _llm      = llm;
        _audit    = audit;
        _settings = settings.Value;
        _logger   = logger;
    }

    // ── /health ───────────────────────────────────────────────────────────────

    [HttpGet("/health")]
    public IActionResult Health()
    {
        return Ok(new
        {
            status        = "ok",
            llm_reachable = _llm.HealthCheck(),
            db_path       = _settings.DbPath,
            vector_path   = _settings.VectorStorePath,
        });
    }

    // ── /chat ─────────────────────────────────────────────────────────────────

    [HttpPost("/chat")]
    public async Task<ActionResult<ChatResponse>> Chat(
        [FromBody] ChatRequest request,
        CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(request.Message))
            return BadRequest(new { detail = "message must not be empty" });

        return await HandleQueryAsync(request.Message, request.Expand, ct: ct);
    }

    // ── /generate ─────────────────────────────────────────────────────────────

    [HttpPost("/generate")]
    public async Task<ActionResult<ChatResponse>> Generate(
        [FromBody] GenerateRequest request,
        CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(request.Prompt))
            return BadRequest(new { detail = "prompt must not be empty" });

        var (results, isTriage) = await _router.RouteAndRetrieveAsync(request.Prompt, ct);

        var messages = PromptBuilder.BuildChatMessages(
            userQuery      : request.Prompt,
            contextResults : results,
            isTriage       : isTriage,
            maxContextChars: _settings.MaxContextChars,
            systemPrompt   : request.SystemPrompt);

        double temperature = request.Temperature ?? _settings.LlmTemperature;

        string answer;
        try
        {
            answer = await _llm.ChatAsync(messages, _settings.LlmMaxTokens, temperature, ct);
        }
        catch (InvalidOperationException ex)
        {
            return StatusCode(503, new { detail = ex.Message });
        }

        var citations = results.Select(PromptBuilder.FormatCitation).ToList();
        var chunkIds  = results.Select(r => r.ChunkId).ToList();

        await _audit.WriteAsync(new
        {
            timestamp  = DateTime.UtcNow.ToString("O"),
            query      = request.Prompt,
            chunk_ids  = chunkIds,
            answer,
            is_triage  = isTriage,
        }, ct);

        return Ok(new ChatResponse
        {
            Answer    = answer,
            Citations = citations,
            IsTriage  = isTriage,
            ChunkIds  = chunkIds,
        });
    }

    // ── /v1/chat/completions (OpenAI-compatible) ──────────────────────────────

    [HttpPost("/v1/chat/completions")]
    public async Task<IActionResult> OpenAiChat(
        [FromBody] OpenAiChatRequest request,
        CancellationToken ct)
    {
        if (request.Messages is not { Count: > 0 })
            return BadRequest(new { detail = "messages must not be empty" });

        var userMessages = request.Messages.Where(m => m.Role == "user").ToList();
        if (userMessages.Count == 0)
            return BadRequest(new { detail = "No user message found" });

        var query    = userMessages[^1].Content;
        var response = await HandleQueryAsync(query, ct: ct);

        if (response.Result is not OkObjectResult okResult || okResult.Value is not ChatResponse chatResp)
            return response.Result!;

        var citationBlock = chatResp.Citations.Count > 0
            ? "\n\n**Sources:** " + string.Join(" | ", chatResp.Citations)
            : string.Empty;

        return Ok(new
        {
            id      = "chatcmpl-merlin",
            @object = "chat.completion",
            created = DateTimeOffset.UtcNow.ToUnixTimeSeconds(),
            model   = request.Model,
            choices = new[]
            {
                new
                {
                    index         = 0,
                    message       = new { role = "assistant", content = chatResp.Answer + citationBlock },
                    finish_reason = "stop",
                }
            },
            usage = new { prompt_tokens = 0, completion_tokens = 0, total_tokens = 0 },
        });
    }

    // ── Shared query handler ──────────────────────────────────────────────────

    private async Task<ActionResult<ChatResponse>> HandleQueryAsync(
        string query,
        bool expand = false,
        CancellationToken ct = default)
    {
        var (results, isTriage) = await _router.RouteAndRetrieveAsync(query, ct);

        var messages = PromptBuilder.BuildChatMessages(
            userQuery      : query,
            contextResults : results,
            isTriage       : isTriage,
            expand         : expand,
            maxContextChars: _settings.MaxContextChars);

        string answer;
        try
        {
            answer = await _llm.ChatAsync(messages, _settings.LlmMaxTokens, _settings.LlmTemperature, ct);
        }
        catch (InvalidOperationException ex)
        {
            return StatusCode(503, new { detail = ex.Message });
        }

        var citations = results.Select(PromptBuilder.FormatCitation).ToList();
        var chunkIds  = results.Select(r => r.ChunkId).ToList();

        await _audit.WriteAsync(new
        {
            timestamp  = DateTime.UtcNow.ToString("O"),
            query,
            chunk_ids  = chunkIds,
            answer,
            is_triage  = isTriage,
        }, ct);

        return Ok(new ChatResponse
        {
            Answer    = answer,
            Citations = citations,
            IsTriage  = isTriage,
            ChunkIds  = chunkIds,
        });
    }
}
