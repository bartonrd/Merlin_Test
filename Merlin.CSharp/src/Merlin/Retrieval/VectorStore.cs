using System.Runtime.InteropServices;

namespace Merlin.Retrieval;

/// <summary>
/// Pure C# in-memory vector store with file persistence.
/// Equivalent to FAISS IndexFlatIP (inner product = cosine similarity on L2-normalised vectors).
///
/// Vectors are expected to be L2-normalised before insertion so that
/// inner-product equals cosine similarity.
/// </summary>
public sealed class VectorStore
{
    private readonly List<float[]> _vectors = new();
    private readonly List<int>     _ids     = new();

    public int Count => _vectors.Count;

    // ── Mutation ──────────────────────────────────────────────────────────────

    public void Clear()
    {
        _vectors.Clear();
        _ids.Clear();
    }

    public void Add(int[] ids, float[][] vectors)
    {
        if (ids.Length != vectors.Length)
            throw new ArgumentException("ids and vectors must have the same length");

        for (int i = 0; i < ids.Length; i++)
        {
            _ids.Add(ids[i]);
            _vectors.Add(vectors[i]);
        }
    }

    // ── Search ────────────────────────────────────────────────────────────────

    /// <summary>Return top-k (id, score) pairs sorted by descending cosine similarity.</summary>
    public List<(int id, float score)> Search(float[] query, int topK)
    {
        if (_vectors.Count == 0) return [];

        int dim = query.Length;
        var scored = new List<(int id, float score)>(_vectors.Count);

        for (int i = 0; i < _vectors.Count; i++)
        {
            float dot = DotProduct(query, _vectors[i], dim);
            scored.Add((_ids[i], dot));
        }

        scored.Sort((a, b) => b.score.CompareTo(a.score));
        return scored.Count > topK ? scored[..topK] : scored;
    }

    private static float DotProduct(float[] a, float[] b, int dim)
    {
        float sum = 0f;
        for (int i = 0; i < dim; i++)
            sum += a[i] * b[i];
        return sum;
    }

    // ── Persistence ───────────────────────────────────────────────────────────

    /// <summary>Save the store to a binary file.</summary>
    public void Save(string path)
    {
        var dir = System.IO.Path.GetDirectoryName(path);
        if (dir is not null) Directory.CreateDirectory(dir);
        using var fs = new FileStream(path, FileMode.Create, FileAccess.Write);
        using var bw = new BinaryWriter(fs);

        int count = _vectors.Count;
        int dim   = count > 0 ? _vectors[0].Length : 0;

        bw.Write(count);
        bw.Write(dim);

        for (int i = 0; i < count; i++)
        {
            bw.Write(_ids[i]);
            foreach (float f in _vectors[i])
                bw.Write(f);
        }
    }

    /// <summary>Load the store from a binary file.</summary>
    public void Load(string path)
    {
        Clear();
        if (!File.Exists(path)) return;

        using var fs = new FileStream(path, FileMode.Open, FileAccess.Read);
        using var br = new BinaryReader(fs);

        int count = br.ReadInt32();
        int dim   = br.ReadInt32();

        for (int i = 0; i < count; i++)
        {
            int id  = br.ReadInt32();
            var vec = new float[dim];
            for (int j = 0; j < dim; j++)
                vec[j] = br.ReadSingle();
            _ids.Add(id);
            _vectors.Add(vec);
        }
    }

    // ── L2 normalisation helper ───────────────────────────────────────────────

    /// <summary>Normalise a vector in-place to unit length.</summary>
    public static void L2Normalize(float[] vec)
    {
        float norm = 0f;
        foreach (float f in vec) norm += f * f;
        norm = MathF.Sqrt(norm);
        if (norm < 1e-9f) return;
        for (int i = 0; i < vec.Length; i++) vec[i] /= norm;
    }

    /// <summary>Normalise each row of a 2-D array in-place.</summary>
    public static void L2NormalizeRows(float[][] vecs)
    {
        foreach (var v in vecs) L2Normalize(v);
    }
}
