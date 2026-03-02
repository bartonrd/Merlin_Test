using Merlin.Reasoning;

namespace Merlin.Tests;

/// <summary>Tests for LogParser – mirrors tests/test_log_parser.py</summary>
public class LogParserTests
{
    [Fact]
    public void PythonTraceback_IsLog()
    {
        var log = """
            Traceback (most recent call last):
              File "app.py", line 42, in handler
                result = db.query(sql)
              File "db.py", line 17, in query
                raise DatabaseError("Connection timeout")
            DatabaseError: Connection timeout
            """;

        Assert.True(LogParser.IsErrorLog(log));
        var sig = LogParser.ParseLogSignature(log);
        Assert.True(sig.IsLog);
        Assert.Contains(sig.ExceptionTypes, e => e.Contains("DatabaseError"));
    }

    [Fact]
    public void JavaStackTrace_IsLog()
    {
        var log = """
            java.lang.NullPointerException: Cannot invoke method on null
                at com.example.service.OrderService.processOrder(OrderService.java:142)
                at com.example.controller.OrderController.createOrder(OrderController.java:87)
                at sun.reflect.NativeMethodAccessorImpl.invoke0(Native Method)
            """;

        Assert.True(LogParser.IsErrorLog(log));
    }

    [Fact]
    public void HttpErrorCode_IsLog()
    {
        var log = "2024-01-15 14:32:01 ERROR upstream returned HTTP 504 for /api/orders";
        Assert.True(LogParser.IsErrorLog(log));
    }

    [Fact]
    public void NormalQuestion_IsNotLog()
    {
        var query = "How do I restart the database connection pool?";
        Assert.False(LogParser.IsErrorLog(query));
    }

    [Fact]
    public void NormalSentence_IsNotLog()
    {
        var query = "What are the steps to scale the order-processor service?";
        Assert.False(LogParser.IsErrorLog(query));
    }

    [Fact]
    public void OracleErrorCodes_Parsed()
    {
        var log = "ORA-12541: TNS:no listener\nORA-12170: TNS:Connect timeout";
        var sig = LogParser.ParseLogSignature(log);
        Assert.Contains(sig.ErrorCodes, c => c.Contains("ORA-12541") || c.Contains("ORA-12170"));
    }

    [Fact]
    public void SqlException_TypeParsed()
    {
        var log = """
            java.sql.SQLException: Timeout waiting for connection
                at com.zaxxer.hikari.pool.HikariPool.getConnection(HikariPool.java:213)
            """;

        var sig = LogParser.ParseLogSignature(log);
        Assert.Contains(sig.ExceptionTypes, e => e.Contains("SQLException"));
    }

    [Fact]
    public void MultipleTimestamps_DetectedAsLog()
    {
        var log =
            "2024-01-01 10:00:00 INFO Starting\n" +
            "2024-01-01 10:00:01 ERROR Something failed\n" +
            "2024-01-01 10:00:02 CRITICAL Service down\n";

        Assert.True(LogParser.IsErrorLog(log));
    }

    [Fact]
    public void HttpErrorCodes_Parsed()
    {
        var log = "2024-01-15 ERROR upstream returned HTTP 503 gateway unavailable";
        var sig = LogParser.ParseLogSignature(log);
        Assert.Contains(sig.ErrorCodes, c => c.Contains("503"));
    }

    [Fact]
    public void StackTraceLines_Captured()
    {
        var log = """
            Traceback (most recent call last):
              File "main.py", line 10, in <module>
                run()
              File "core.py", line 55, in run
                connect()
            RuntimeError: failed to connect
            """;

        var sig = LogParser.ParseLogSignature(log);
        Assert.True(sig.IsLog);
        Assert.NotEmpty(sig.StackTraceLines);
    }
}
