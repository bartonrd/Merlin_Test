using System.Text.RegularExpressions;
using Merlin.Models;

namespace Merlin.Reasoning;

/// <summary>
/// Heuristic detection and parsing of error logs / stack traces.
/// Mirrors app/reasoning/log_parser.py.
/// </summary>
public static class LogParser
{
    // ── Detection patterns ────────────────────────────────────────────────────

    private static readonly Regex PythonTb = new(
        @"Traceback \(most recent call last\)", RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly Regex JavaFrame = new(
        @"^\s+at\s+[\w.$<>]+\(", RegexOptions.Multiline | RegexOptions.Compiled);

    private static readonly Regex JsFrame = new(
        @"^\s+at\s+.+:\d+:\d+", RegexOptions.Multiline | RegexOptions.Compiled);

    private static readonly Regex ExceptionLine = new(
        @"(Exception|Error|FATAL|CRITICAL|Traceback|Caused by)[\s:]",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly Regex Http5Xx = new(
        @"\bHTTP[/ ]+5\d{2}\b", RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly Regex ErrorCode = new(
        @"\b(E\d{4,}|ORA-\d+|SQLSTATE\[\d+\]|errno\s*\d+|code\s*[:=]\s*\d{3,})\b",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly Regex LogTimestamp = new(
        @"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}|\[\d{4}-\d{2}-\d{2})",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly Regex PipeBracketLine = new(
        @"[\[\|]{1}.{10,}[\]\|]{1}", RegexOptions.Compiled);

    /// <summary>
    /// Detect whether text looks like an error log or stack trace.
    /// Heuristics: any 1 strong signal OR 2+ weak signals triggers true.
    /// </summary>
    public static bool IsErrorLog(string text)
    {
        // Strong signals
        if (PythonTb.IsMatch(text) || JavaFrame.IsMatch(text) || JsFrame.IsMatch(text))
            return true;

        // Weak signals
        int weakScore = 0;
        if (ExceptionLine.IsMatch(text)) weakScore++;
        if (Http5Xx.IsMatch(text))       weakScore++;
        if (ErrorCode.IsMatch(text))     weakScore++;
        if (LogTimestamp.Matches(text).Count >= 2) weakScore++;
        if (PipeBracketLine.Matches(text).Count >= 2) weakScore++;

        return weakScore >= 2;
    }

    // ── Signature extraction patterns ─────────────────────────────────────────

    private static readonly Regex ExceptionTypeRe = new(
        @"^(?:\s+Caused by:\s+)?([A-Za-z][\w.]*(?:Exception|Error|Fault|Panic))\b",
        RegexOptions.Multiline | RegexOptions.Compiled);

    private static readonly Regex StackFrameRe = new(
        @"^\s+(?:at\s+.+|File\s+"".+"",\s+line\s+\d+)",
        RegexOptions.Multiline | RegexOptions.Compiled);

    private static readonly Regex ErrorMsgRe = new(
        @"(Exception|Error|FATAL|CRITICAL)[:\s]+(.{10,120})",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly Regex HttpCodeRe = new(
        @"\bHTTP[/ ]+(\d{3})\b", RegexOptions.IgnoreCase | RegexOptions.Compiled);

    /// <summary>Extract a structured signature from an error log for improved search.</summary>
    public static LogSignature ParseLogSignature(string text)
    {
        var sig = new LogSignature { IsLog = IsErrorLog(text) };

        // Error codes (DB/application)
        sig.ErrorCodes = ErrorCode.Matches(text)
            .Select(m => m.Value)
            .Distinct()
            .ToList();

        // HTTP codes
        foreach (Match m in HttpCodeRe.Matches(text))
            if (!sig.ErrorCodes.Contains($"HTTP_{m.Groups[1].Value}"))
                sig.ErrorCodes.Add($"HTTP_{m.Groups[1].Value}");

        // Exception types (dedup preserving order)
        sig.ExceptionTypes = ExceptionTypeRe.Matches(text)
            .Select(m => m.Groups[1].Value)
            .Distinct()
            .ToList();

        // Stack trace lines (max 10)
        sig.StackTraceLines = StackFrameRe.Matches(text)
            .Select(m => m.Value)
            .Take(10)
            .ToList();

        // Error messages (max 5)
        sig.ErrorMessages = ErrorMsgRe.Matches(text)
            .Select(m => m.Groups[2].Value.Trim())
            .Take(5)
            .ToList();

        return sig;
    }

    /// <summary>Build an enhanced search query from a log signature.</summary>
    public static string BuildSearchQuery(string originalQuery, LogSignature sig)
    {
        var terms = new List<string>();
        terms.AddRange(sig.ExceptionTypes.Take(3));
        terms.AddRange(sig.ErrorCodes.Take(3));
        terms.AddRange(sig.ErrorMessages.Take(2));

        return terms.Count > 0 ? string.Join(" ", terms) : originalQuery;
    }
}
