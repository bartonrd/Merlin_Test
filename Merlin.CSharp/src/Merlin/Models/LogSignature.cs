namespace Merlin.Models;

/// <summary>Structured signature extracted from an error log or stack trace.</summary>
public class LogSignature
{
    public bool IsLog { get; set; }
    public List<string> ErrorCodes { get; set; } = new();
    public List<string> ExceptionTypes { get; set; } = new();
    public List<string> StackTraceLines { get; set; } = new();
    public List<string> ErrorMessages { get; set; } = new();
}
