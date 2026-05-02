using System.Buffers.Binary;
using System.Text;

static class Program
{
static ushort U16(byte[] data, int off) => BinaryPrimitives.ReadUInt16LittleEndian(data.AsSpan(off));
static uint U32(byte[] data, int off) => BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(off));

static byte[] ReadAt(FileStream fs, long off, int size)
{
    var buf = new byte[size];
    fs.Position = off;
    var total = 0;
    while (total < size)
    {
        var n = fs.Read(buf, total, size - total);
        if (n == 0)
        {
            throw new EndOfStreamException();
        }
        total += n;
    }
    return buf;
}

sealed record Section(uint Vaddr, uint RawPtr, uint RawSize);
sealed record Resource(long Off, uint Size);
sealed record DirEntry(uint Id, bool IsDir, uint Target);

sealed class PeFile : IDisposable
{
    private readonly FileStream _fs;
    private readonly List<Section> _sections = [];
    private readonly long _resOff;
    private readonly Dictionary<int, Resource> _resources = [];

    public PeFile(string path)
    {
        _fs = File.Open(path, FileMode.Open, FileAccess.Read, FileShare.Read);
        var dos = ReadAt(_fs, 0, 0x100);
        if (dos[0] != (byte)'M' || dos[1] != (byte)'Z')
        {
            throw new InvalidDataException("not an MZ file");
        }

        var peoff = U32(dos, 0x3c);
        var hdr = ReadAt(_fs, peoff, 0x400);
        if (hdr[0] != (byte)'P' || hdr[1] != (byte)'E' || hdr[2] != 0 || hdr[3] != 0)
        {
            throw new InvalidDataException("not a PE file");
        }

        var nsects = U16(hdr, 6);
        var optSize = U16(hdr, 20);
        const int optOff = 0x18;
        var magic = U16(hdr, optOff);
        var ddOff = magic switch
        {
            0x20b => optOff + 0x70,
            0x10b => optOff + 0x60,
            _ => throw new InvalidDataException($"unsupported PE optional header magic 0x{magic:x}")
        };
        var resRva = U32(hdr, ddOff + 16);

        var sectBytes = ReadAt(_fs, peoff + optOff + optSize, nsects * 40);
        for (var i = 0; i < nsects; i++)
        {
            var off = i * 40;
            _sections.Add(new Section(
                U32(sectBytes, off + 12),
                U32(sectBytes, off + 20),
                U32(sectBytes, off + 16)));
        }

        _resOff = RvaToOff(resRva);
        IndexResources();
    }

    public void Dispose() => _fs.Dispose();

    private long RvaToOff(uint rva)
    {
        foreach (var section in _sections)
        {
            if (section.RawSize != 0 && rva >= section.Vaddr && rva < section.Vaddr + section.RawSize)
            {
                return section.RawPtr + (rva - section.Vaddr);
            }
        }
        throw new InvalidDataException($"RVA not mapped: 0x{rva:x}");
    }

    private List<DirEntry> DirEntries(uint rel)
    {
        var off = _resOff + rel;
        var hdr = ReadAt(_fs, off, 16);
        var count = U16(hdr, 12) + U16(hdr, 14);
        var raw = ReadAt(_fs, off + 16, count * 8);
        var outEntries = new List<DirEntry>(count);
        for (var i = 0; i < count; i++)
        {
            var entry = i * 8;
            var ident = U32(raw, entry);
            var target = U32(raw, entry + 4);
            outEntries.Add(new DirEntry(ident & 0x7fffffff, (target & 0x80000000) != 0, target & 0x7fffffff));
        }
        return outEntries;
    }

    private void IndexResources()
    {
        foreach (var type in DirEntries(0))
        {
            if (type.Id != 10 || !type.IsDir)
            {
                continue;
            }

            foreach (var name in DirEntries(type.Target))
            {
                if (!name.IsDir)
                {
                    continue;
                }

                var langs = DirEntries(name.Target);
                if (langs.Count != 1 || langs[0].IsDir)
                {
                    throw new InvalidDataException($"unexpected resource language entry for {name.Id}");
                }

                var data = ReadAt(_fs, _resOff + langs[0].Target, 16);
                _resources[(int)name.Id] = new Resource(RvaToOff(U32(data, 0)), U32(data, 4));
            }
        }

        if (_resources.Count == 0)
        {
            throw new InvalidDataException("no RCDATA resources found");
        }
    }

    public byte[] DecompressResource(int id)
    {
        if (!_resources.TryGetValue(id, out var resource))
        {
            throw new KeyNotFoundException($"unknown resource id {id}");
        }
        return Aplib.Decompress(ReadAt(_fs, resource.Off, checked((int)resource.Size)));
    }
}

sealed class BitReader(byte[] src)
{
    private int _pos = 1;
    private byte _bits;
    private byte _tag;

    public int Bit()
    {
        if (_bits == 0)
        {
            if (_pos >= src.Length)
            {
                throw new EndOfStreamException();
            }
            _tag = src[_pos++];
            _bits = 0x80;
        }
        var output = (_tag & 0x80) != 0 ? 1 : 0;
        _tag <<= 1;
        _bits >>= 1;
        return output;
    }

    public byte Byte()
    {
        if (_pos >= src.Length)
        {
            throw new EndOfStreamException();
        }
        return src[_pos++];
    }

    public int Gamma()
    {
        var output = 1;
        while (true)
        {
            output = (output << 1) | Bit();
            if (Bit() == 0)
            {
                return output;
            }
        }
    }
}

static class Aplib
{
    public static byte[] Decompress(byte[] src)
    {
        if (src.Length == 0)
        {
            return [];
        }

        var bits = new BitReader(src);
        var dst = new byte[Math.Max(1024, src.Length * 4)];
        var len = 1;
        dst[0] = src[0];
        var lastOffset = -1;
        var lwm = 3;

        void Append(byte value)
        {
            if (len == dst.Length)
            {
                Array.Resize(ref dst, dst.Length * 2);
            }
            dst[len++] = value;
        }

        while (true)
        {
            if (bits.Bit() == 0)
            {
                Append(bits.Byte());
                lwm = 3;
                continue;
            }

            if (bits.Bit() == 1)
            {
                if (bits.Bit() == 0)
                {
                    var packed = bits.Byte();
                    if (packed == 0)
                    {
                        return dst[..len];
                    }
                    var offset = packed >> 1;
                    var shortLength = 2 + (packed & 1);
                    lastOffset = offset;
                    lwm = 2;
                    var copyFrom = len - offset;
                    if (copyFrom < 0)
                    {
                        throw new InvalidDataException("invalid short match offset");
                    }
                    for (var i = 0; i < shortLength; i++)
                    {
                        Append(dst[copyFrom++]);
                    }
                }
                else
                {
                    var offset = 0;
                    for (var i = 0; i < 4; i++)
                    {
                        offset = (offset << 1) | bits.Bit();
                    }
                    lwm = 3;
                    if (offset != 0)
                    {
                        var copyFrom = len - offset;
                        if (copyFrom < 0)
                        {
                            throw new InvalidDataException("invalid tiny match offset");
                        }
                        Append(dst[copyFrom]);
                    }
                    else
                    {
                        Append(0);
                    }
                }
                continue;
            }

            var gamma = bits.Gamma();
            var longOffset = gamma - lwm;
            int length;
            if (longOffset < 0)
            {
                longOffset = lastOffset;
                length = bits.Gamma();
            }
            else
            {
                longOffset = (longOffset << 8) | bits.Byte();
                length = bits.Gamma();
                if (longOffset <= 127 || longOffset > 31999)
                {
                    length += 2;
                }
                else if (longOffset > 1279)
                {
                    length++;
                }
                lastOffset = longOffset;
            }
            lwm = 2;
            var srcOff = len - longOffset;
            if (longOffset <= 0 || srcOff < 0)
            {
                throw new InvalidDataException("invalid long match offset");
            }
            for (var i = 0; i < length; i++)
            {
                Append(dst[srcOff++]);
            }
        }
    }
}

static async Task<int> Main(string[] args)
{
    if (args.Length != 1)
    {
        Console.Error.WriteLine("usage: AplibServer <pe>");
        return 2;
    }

    using var pe = new PeFile(args[0]);
    await using var stdout = Console.OpenStandardOutput();
    using var stdin = new StreamReader(Console.OpenStandardInput(), Encoding.ASCII, leaveOpen: false);
    var lenBuf = new byte[4];
    while (await stdin.ReadLineAsync() is { } line)
    {
        line = line.Trim();
        if (line.Length == 0)
        {
            continue;
        }
        var image = pe.DecompressResource(int.Parse(line));
        BinaryPrimitives.WriteUInt32LittleEndian(lenBuf, checked((uint)image.Length));
        await stdout.WriteAsync(lenBuf);
        await stdout.WriteAsync(image);
        await stdout.FlushAsync();
    }

    return 0;
}
}
