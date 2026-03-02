using Merlin.Models;
using Microsoft.Data.Sqlite;

namespace Merlin.Retrieval;

/// <summary>
/// BM25 search via SQLite FTS5.
/// Mirrors app/retrieval/bm25.py.
/// </summary>
public sealed class Bm25SearchService
{
    private readonly string _dbPath;

    public Bm25SearchService(string dbPath) => _dbPath = dbPath;

    // ── DDL ───────────────────────────────────────────────────────────────────

    private const string Ddl = """
        CREATE TABLE IF NOT EXISTS chunks (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id       TEXT    NOT NULL,
            title        TEXT    NOT NULL,
            path         TEXT    NOT NULL,
            doc_type     TEXT    NOT NULL,
            section      TEXT    NOT NULL,
            chunk_index  INTEGER NOT NULL,
            text         TEXT    NOT NULL,
            timestamp    TEXT
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            text,
            title,
            section,
            doc_type,
            content=chunks,
            content_rowid=id
        );
        """;

    public void InitDb()
    {
        var dir = System.IO.Path.GetDirectoryName(_dbPath);
        if (dir is not null) Directory.CreateDirectory(dir);
        using var conn = OpenConn();
        conn.ExecuteNonQuery(Ddl);
    }

    // ── Insert ────────────────────────────────────────────────────────────────

    public List<int> InsertChunks(IEnumerable<Chunk> chunks)
    {
        var rowIds = new List<int>();
        using var conn = OpenConn();
        using var tx = conn.BeginTransaction();

        foreach (var c in chunks)
        {
            using var cmd = conn.CreateCommand();
            cmd.Transaction = tx;
            cmd.CommandText = """
                INSERT INTO chunks (doc_id,title,path,doc_type,section,chunk_index,text,timestamp)
                VALUES (@docId,@title,@path,@docType,@section,@chunkIndex,@text,@ts)
                """;
            cmd.Parameters.AddWithValue("@docId",       c.DocId);
            cmd.Parameters.AddWithValue("@title",       c.Title);
            cmd.Parameters.AddWithValue("@path",        c.Path);
            cmd.Parameters.AddWithValue("@docType",     c.DocType);
            cmd.Parameters.AddWithValue("@section",     c.Section);
            cmd.Parameters.AddWithValue("@chunkIndex",  c.ChunkIndex);
            cmd.Parameters.AddWithValue("@text",        c.Text);
            cmd.Parameters.AddWithValue("@ts",          c.Timestamp ?? (object)DBNull.Value);
            cmd.ExecuteNonQuery();
            using var rowCmd = conn.CreateCommand();
            rowCmd.Transaction = tx;
            rowCmd.CommandText = "SELECT last_insert_rowid()";
            rowIds.Add((int)(long)rowCmd.ExecuteScalar()!);
        }

        tx.Commit();
        return rowIds;
    }

    public void RebuildFtsIndex()
    {
        using var conn = OpenConn();
        conn.ExecuteNonQuery("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')");
    }

    // ── Search ────────────────────────────────────────────────────────────────

    public List<SearchResult> Search(string query, int topK = 10, IList<string>? docTypeFilter = null)
    {
        if (string.IsNullOrWhiteSpace(query)) return [];
        if (!File.Exists(_dbPath)) return [];

        using var conn = OpenConn();

        string sql;
        var parameters = new Dictionary<string, object>();

        if (docTypeFilter is { Count: > 0 })
        {
            var placeholders = string.Join(",", docTypeFilter.Select((_, i) => $"@dt{i}"));
            sql = $"""
                SELECT c.id, c.doc_id, c.title, c.path, c.doc_type,
                       c.section, c.chunk_index, c.text,
                       -bm25(chunks_fts) AS score
                FROM chunks_fts f
                JOIN chunks c ON c.id = f.rowid
                WHERE chunks_fts MATCH @query
                  AND c.doc_type IN ({placeholders})
                ORDER BY score DESC
                LIMIT @topK
                """;
            for (int i = 0; i < docTypeFilter.Count; i++)
                parameters[$"@dt{i}"] = docTypeFilter[i];
        }
        else
        {
            sql = """
                SELECT c.id, c.doc_id, c.title, c.path, c.doc_type,
                       c.section, c.chunk_index, c.text,
                       -bm25(chunks_fts) AS score
                FROM chunks_fts f
                JOIN chunks c ON c.id = f.rowid
                WHERE chunks_fts MATCH @query
                ORDER BY score DESC
                LIMIT @topK
                """;
        }

        parameters["@query"] = query;
        parameters["@topK"]  = topK;

        try
        {
            using var cmd = conn.CreateCommand();
            cmd.CommandText = sql;
            foreach (var kv in parameters)
                cmd.Parameters.AddWithValue(kv.Key, kv.Value);

            var results = new List<SearchResult>();
            using var reader = cmd.ExecuteReader();
            while (reader.Read())
            {
                results.Add(new SearchResult
                {
                    ChunkId    = reader.GetInt32(0),
                    DocId      = reader.GetString(1),
                    Title      = reader.GetString(2),
                    Path       = reader.GetString(3),
                    DocType    = reader.GetString(4),
                    Section    = reader.GetString(5),
                    ChunkIndex = reader.GetInt32(6),
                    Text       = reader.GetString(7),
                    Score      = reader.GetDouble(8),
                });
            }
            return results;
        }
        catch (SqliteException)
        {
            // FTS table may not exist yet or the query has an FTS syntax error
            return [];
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    public HashSet<string> GetKnownDocIds()
    {
        if (!File.Exists(_dbPath)) return [];
        using var conn = OpenConn();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT DISTINCT doc_id FROM chunks";
        var ids = new HashSet<string>();
        using var reader = cmd.ExecuteReader();
        while (reader.Read()) ids.Add(reader.GetString(0));
        return ids;
    }

    public List<(int id, string text)> GetAllChunks()
    {
        if (!File.Exists(_dbPath)) return [];
        using var conn = OpenConn();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT id, text FROM chunks ORDER BY id";
        var rows = new List<(int, string)>();
        using var reader = cmd.ExecuteReader();
        while (reader.Read()) rows.Add((reader.GetInt32(0), reader.GetString(1)));
        return rows;
    }

    public SearchResult? GetChunkById(int id)
    {
        if (!File.Exists(_dbPath)) return null;
        using var conn = OpenConn();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT id,doc_id,title,path,doc_type,section,chunk_index,text FROM chunks WHERE id=@id";
        cmd.Parameters.AddWithValue("@id", id);
        using var reader = cmd.ExecuteReader();
        if (!reader.Read()) return null;
        return new SearchResult
        {
            ChunkId    = reader.GetInt32(0),
            DocId      = reader.GetString(1),
            Title      = reader.GetString(2),
            Path       = reader.GetString(3),
            DocType    = reader.GetString(4),
            Section    = reader.GetString(5),
            ChunkIndex = reader.GetInt32(6),
            Text       = reader.GetString(7),
        };
    }

    public void DeleteDb()
    {
        if (File.Exists(_dbPath)) File.Delete(_dbPath);
    }

    private SqliteConnection OpenConn()
    {
        var conn = new SqliteConnection($"Data Source={_dbPath}");
        conn.Open();
        return conn;
    }
}

// ── SqliteConnection extension for DDL scripts ────────────────────────────────
file static class SqliteConnectionExtensions
{
    public static void ExecuteNonQuery(this SqliteConnection conn, string sql)
    {
        foreach (var stmt in sql.Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            if (string.IsNullOrWhiteSpace(stmt)) continue;
            using var cmd = conn.CreateCommand();
            cmd.CommandText = stmt;
            cmd.ExecuteNonQuery();
        }
    }
}
