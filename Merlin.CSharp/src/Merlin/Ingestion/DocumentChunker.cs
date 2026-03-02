using System.Text.RegularExpressions;
using Merlin.Models;

namespace Merlin.Ingestion;

/// <summary>
/// Type-aware document chunking – a C# port of app/ingestion/chunking.py.
/// </summary>
public static class DocumentChunker
{
    // ── Document-type detection ───────────────────────────────────────────────

    private static readonly Regex RunbookKeywords = new(
        @"\b(runbook|symptoms?|procedure|verification|rollback|remediation)\b",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly Regex IncidentKeywords = new(
        @"\b(incident|INC-\d+|postmortem|root\s+cause|what\s+happened|timeline|prevention)\b",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly Regex ArchKeywords = new(
        @"\b(architecture|overview|services?|deployment|infrastructure|platform|stack)\b",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly string[] RunbookSections =
        ["symptoms", "cause", "procedure", "verification", "rollback"];

    private static readonly string[] IncidentSections =
        ["what happened", "signals", "root cause", "fix", "prevention", "timeline"];

    public static string DetectDocType(string title, string text)
    {
        var combined = title + "\n" + (text.Length > 2000 ? text[..2000] : text);

        int runbookScore = RunbookKeywords.Matches(combined).Count;
        int incidentScore = IncidentKeywords.Matches(combined).Count;
        int archScore = ArchKeywords.Matches(combined).Count;

        var titleLower = title.ToLowerInvariant();
        if (titleLower.Contains("runbook"))       runbookScore += 5;
        if (Regex.IsMatch(titleLower, @"inc[-_]\d+")) incidentScore += 5;
        if (titleLower.Contains("architecture") || titleLower.Contains("overview") || titleLower.Contains("platform"))
            archScore += 5;

        int best = Math.Max(runbookScore, Math.Max(incidentScore, archScore));
        if (best == 0) return "general";
        if (best == runbookScore && runbookScore >= incidentScore) return "runbook";
        if (incidentScore > archScore) return "incident";
        if (archScore > 0) return "arch";
        return "general";
    }

    // ── Main dispatcher ───────────────────────────────────────────────────────

    public static List<Chunk> ChunkDocument(
        string text,
        string docId,
        string title,
        string path,
        string? docType = null,
        int maxChunkSize = 800,
        int overlap = 100)
    {
        docType ??= DetectDocType(title, text);

        return docType switch
        {
            "runbook"  => ChunkRunbook(text, docId, title, path, maxChunkSize, overlap),
            "incident" => ChunkIncident(text, docId, title, path, maxChunkSize, overlap),
            _          => ChunkGeneral(text, docId, title, path, maxChunkSize, overlap)
        };
    }

    // ── Specialised chunkers ──────────────────────────────────────────────────

    private static List<Chunk> ChunkRunbook(string text, string docId, string title, string path, int maxSize, int overlap)
    {
        var sections = ExtractSections(text, RunbookSections);
        return SectionsToChunks(sections, docId, title, path, "runbook", maxSize, overlap);
    }

    private static List<Chunk> ChunkIncident(string text, string docId, string title, string path, int maxSize, int overlap)
    {
        var sections = ExtractSections(text, IncidentSections);
        return SectionsToChunks(sections, docId, title, path, "incident", maxSize, overlap);
    }

    private static List<Chunk> ChunkGeneral(string text, string docId, string title, string path, int maxSize, int overlap)
    {
        var headingRe = new Regex(@"^#{1,4}\s+.+", RegexOptions.Multiline);
        var matches = headingRe.Matches(text);

        if (matches.Count == 0)
        {
            var subChunks = SplitBySize(text, maxSize, overlap);
            return subChunks
                .Select((sc, i) => sc.Trim())
                .Where(sc => sc.Length > 0)
                .Select((sc, i) => new Chunk
                {
                    DocId = docId, Title = title, Path = path,
                    DocType = "general", Section = "content", ChunkIndex = i, Text = sc
                })
                .ToList();
        }

        var sections = new List<(string name, string text)>();
        // Text before the first heading
        if (matches[0].Index > 0)
            sections.Add(("preamble", text[..matches[0].Index]));

        for (int i = 0; i < matches.Count; i++)
        {
            var sectionTitle = matches[i].Value.TrimStart('#').Trim();
            int start = matches[i].Index + matches[i].Length;
            int end = i + 1 < matches.Count ? matches[i + 1].Index : text.Length;
            sections.Add((sectionTitle, text[start..end]));
        }

        return SectionsToChunks(sections, docId, title, path, "general", maxSize, overlap);
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static readonly Regex MarkdownHeading = new(@"^\s*(#{1,4})\s+(.+)", RegexOptions.Compiled);
    private static readonly Regex AllCapsHeading = new(@"^[A-Z][A-Za-z ]{2,60}$", RegexOptions.Compiled);

    private static List<(string name, string text)> ExtractSections(string text, string[] knownSections)
    {
        var lines = text.Split('\n');
        var sections = new List<(string name, string text)>();
        var currentName = "preamble";
        var currentLines = new List<string>();

        foreach (var rawLine in lines)
        {
            var line = rawLine;
            string? headingText = null;

            var m = MarkdownHeading.Match(line);
            if (m.Success)
            {
                headingText = m.Groups[2].Value.Trim();
            }
            else
            {
                var stripped = line.Trim().TrimEnd(':');
                if (AllCapsHeading.IsMatch(stripped) && stripped.Length < 60)
                    headingText = stripped;
            }

            if (headingText != null)
            {
                var normalized = headingText.ToLowerInvariant();
                bool matched = knownSections.Any(s => normalized.Contains(s));
                if (matched || m.Success)
                {
                    if (currentLines.Count > 0)
                        sections.Add((currentName, string.Join("\n", currentLines)));
                    currentName = headingText.Trim();
                    currentLines = new List<string>();
                    continue;
                }
            }

            currentLines.Add(line);
        }

        if (currentLines.Count > 0)
            sections.Add((currentName, string.Join("\n", currentLines)));

        return sections;
    }

    private static List<Chunk> SectionsToChunks(
        List<(string name, string text)> sections,
        string docId, string title, string path, string docType,
        int maxSize, int overlap)
    {
        var chunks = new List<Chunk>();
        int chunkIndex = 0;

        foreach (var (sectionName, sectionText) in sections)
        {
            var trimmed = sectionText.Trim();
            if (trimmed.Length == 0) continue;

            foreach (var sub in SplitBySize(trimmed, maxSize, overlap))
            {
                var subTrimmed = sub.Trim();
                if (subTrimmed.Length == 0) continue;
                chunks.Add(new Chunk
                {
                    DocId = docId, Title = title, Path = path,
                    DocType = docType, Section = sectionName,
                    ChunkIndex = chunkIndex++, Text = subTrimmed
                });
            }
        }

        // Fallback: if no chunks were produced, treat whole text as one chunk
        if (chunks.Count == 0 && sections.Count > 0)
        {
            chunks.Add(new Chunk
            {
                DocId = docId, Title = title, Path = path,
                DocType = docType, Section = "content",
                ChunkIndex = 0, Text = sections[0].text.Trim()
            });
        }

        return chunks;
    }

    /// <summary>Split text by word boundaries respecting maxSize with overlap.</summary>
    public static List<string> SplitBySize(string text, int maxSize, int overlap)
    {
        if (text.Length <= maxSize)
            return [text];

        var words = text.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        var chunks = new List<string>();
        var currentWords = new List<string>();
        int currentLen = 0;

        foreach (var word in words)
        {
            int wordLen = word.Length + 1; // +1 for space
            if (currentLen + wordLen > maxSize && currentWords.Count > 0)
            {
                chunks.Add(string.Join(" ", currentWords));

                // Keep last `overlap` characters worth of words for the next chunk
                var overlapWords = new List<string>();
                int overlapLen = 0;
                for (int i = currentWords.Count - 1; i >= 0; i--)
                {
                    if (overlapLen + currentWords[i].Length + 1 > overlap) break;
                    overlapWords.Insert(0, currentWords[i]);
                    overlapLen += currentWords[i].Length + 1;
                }
                currentWords = overlapWords;
                currentLen = overlapLen;
            }

            currentWords.Add(word);
            currentLen += wordLen;
        }

        if (currentWords.Count > 0)
            chunks.Add(string.Join(" ", currentWords));

        return chunks;
    }
}
