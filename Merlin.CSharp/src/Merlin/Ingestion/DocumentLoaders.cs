using DocumentFormat.OpenXml.Packaging;
using UglyToad.PdfPig;
using UglyToad.PdfPig.Content;

namespace Merlin.Ingestion;

/// <summary>Load plain text from .txt and .md files.</summary>
public static class DocumentLoaders
{
    private static readonly HashSet<string> SupportedExtensions =
        new(StringComparer.OrdinalIgnoreCase) { ".txt", ".md", ".pdf", ".docx" };

    public static bool IsSupported(string path) =>
        SupportedExtensions.Contains(System.IO.Path.GetExtension(path));

    /// <summary>Dispatch to the right loader based on file extension.</summary>
    public static string LoadText(string filePath)
    {
        var ext = System.IO.Path.GetExtension(filePath).ToLowerInvariant();
        return ext switch
        {
            ".txt" or ".md" => LoadTxt(filePath),
            ".pdf"          => LoadPdf(filePath),
            ".docx"         => LoadDocx(filePath),
            _               => throw new NotSupportedException($"Unsupported file extension: {ext}")
        };
    }

    private static string LoadTxt(string path) => File.ReadAllText(path);

    private static string LoadPdf(string path)
    {
        using var doc = PdfDocument.Open(path);
        var pages = new List<string>();
        foreach (Page page in doc.GetPages())
        {
            var text = page.Text;
            if (!string.IsNullOrWhiteSpace(text))
                pages.Add(text);
        }
        return string.Join("\n\n", pages);
    }

    private static string LoadDocx(string path)
    {
        using var doc = WordprocessingDocument.Open(path, false);
        var body = doc.MainDocumentPart?.Document.Body;
        if (body is null) return string.Empty;

        var paragraphs = body
            .Descendants<DocumentFormat.OpenXml.Wordprocessing.Paragraph>()
            .Select(p => p.InnerText)
            .Where(t => !string.IsNullOrWhiteSpace(t));

        return string.Join("\n\n", paragraphs);
    }
}
