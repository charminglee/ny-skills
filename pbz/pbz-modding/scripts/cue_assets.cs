using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using CUE4Parse.FileProvider;
using CUE4Parse.Compression;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.MappingsProvider;
using CUE4Parse.UE4.Versions;
using CUE4Parse.UE4.Objects.Core.Misc;
using CUE4Parse.UE4.IO;
using CUE4Parse.UE4.IO.Objects;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

public static class PbzCueAssets {
    private static string ChunkHex(FIoChunkId id) {
        if ((int)Marshal.OffsetOf<FIoChunkId>(nameof(FIoChunkId.ChunkType)) != 11)
            throw new Exception("Unsupported FIoChunkId layout; inspect the supplied CUE4Parse build");
        var bytes = new byte[Marshal.SizeOf<FIoChunkId>()];
        MemoryMarshal.Write(bytes.AsSpan(), in id);
        return Convert.ToHexString(bytes.AsSpan(0, 12)).ToLowerInvariant();
    }

    private static FIoStoreTocResource Toc(IoStoreReader reader) =>
        (FIoStoreTocResource)typeof(IoStoreReader).GetField("TocResource",
            BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance).GetValue(reader);

    private static void Json(string path, object value) =>
        File.WriteAllText(path, JsonConvert.SerializeObject(value, Formatting.Indented));

    public static void Run(string configPath) {
        var config = JObject.Parse(File.ReadAllText(configPath));
        var work = (string)config["work"];
        var action = (string)config["action"];
        OodleHelper.Initialize((string)config["oodle"]);
        using var provider = new DefaultFileProvider((string)config["paks"], SearchOption.TopDirectoryOnly,
            new VersionContainer(EGame.GAME_UE5_7), StringComparer.OrdinalIgnoreCase);
        provider.MappingsContainer = new FileUsmapTypeMappingsProvider((string)config["usmap"]);
        provider.Initialize();
        provider.SubmitKey(new FGuid(), new FAesKey((string)config["aes"]));
        if (action == "inventory") {
            var root = ((string)config["root"]).Replace('\\', '/').TrimEnd('/') + "/";
            var files = provider.Files.Keys.Where(p => p.StartsWith(root, StringComparison.OrdinalIgnoreCase)).OrderBy(p => p).ToArray();
            if (files.Length == 0) throw new Exception("No files below " + root);
            Json(Path.Combine(work, "inventory.json"), files);
            Console.WriteLine("INVENTORY " + files.Length + " files");
            return;
        }
        var paths = JArray.Parse(File.ReadAllText((string)config["assets"]))
            .Select(p => ((string)p).Replace('\\', '/')).Distinct(StringComparer.OrdinalIgnoreCase).ToArray();
        if (paths.Length == 0) throw new Exception("Empty package whitelist");
        if (action == "inspect") {
            var rows = new List<object>();
            foreach (var path in paths) {
                if (!path.EndsWith(".uasset", StringComparison.OrdinalIgnoreCase)) throw new Exception("Expected physical .uasset path: " + path);
                var exports = provider.LoadPackage(path).GetExports().ToArray();
                rows.Add(new { source = path, exports });
            }
            Json(Path.Combine(work, "objects.json"), rows);
            Console.WriteLine("INSPECTED " + rows.Count + " packages");
            return;
        }
        if (action != "extract") throw new Exception("Unknown action");
        var selected = new Dictionary<IoStoreReader, HashSet<ulong>>();
        var packages = new List<object>();
        var chunks = new List<object>();
        string tocVersion = null, headerVersion = null;
        foreach (var path in paths) {
            if (!provider.Files.TryGetValue(path, out var file) || file is not FIoStoreEntry entry)
                throw new Exception("Missing or non-Zen asset: " + path);
            if (!path.EndsWith(".uasset", StringComparison.OrdinalIgnoreCase)) throw new Exception("Whitelist must name package .uasset files");
            var reader = entry.IoStoreReader;
            var header = reader.ContainerHeader;
            var toc = Toc(reader);
            var packageIndex = Array.IndexOf(header.PackageIds, entry.ChunkId.AsPackageId());
            if (packageIndex < 0) throw new Exception("Package store entry missing: " + path);
            if ((int)header.Version != 5) throw new Exception("This helper requires verified UE5.7 header version 5");
            if (header.OptionalSegmentPackageIds?.Contains(entry.ChunkId.AsPackageId()) == true)
                throw new Exception("Selected package has optional-segment metadata requiring additional handling");
            if (tocVersion != null && (tocVersion != toc.Header.Version.ToString() || headerVersion != header.Version.ToString()))
                throw new Exception("Mixed container versions");
            tocVersion = toc.Header.Version.ToString();
            headerVersion = header.Version.ToString();
            var store = header.StoreEntries[packageIndex];
            if (!selected.ContainsKey(reader)) selected.Add(reader, new HashSet<ulong>());
            selected[reader].Add(entry.ChunkId.ChunkId);
            packages.Add(new {
                path, chunk_id = ChunkHex(entry.ChunkId), package_id = entry.ChunkId.ChunkId,
                store_entry = new {
                    export_bundles_size = 0, load_order = 0,
                    export_count = store.ExportCount, export_bundle_count = store.ExportBundleCount,
                    imported_packages = store.ImportedPackages.Select(p => p.id).ToArray(),
                    shader_map_hashes = store.ShaderMapHashes.Select(h => Convert.ToHexString(h.Hash).ToLowerInvariant()).ToArray()
                }
            });
        }
        var rawDir = Path.Combine(work, "raw-chunks");
        Directory.CreateDirectory(rawDir);
        var seen = new HashSet<string>();
        foreach (var selection in selected) {
            var reader = selection.Key;
            var named = reader.Files.Values.OfType<FIoStoreEntry>().GroupBy(f => ChunkHex(f.ChunkId))
                .ToDictionary(g => g.Key, g => g.First().Path);
            foreach (var id in Toc(reader).ChunkIds.Where(id => selection.Value.Contains(id.ChunkId))) {
                var hex = ChunkHex(id);
                if (!seen.Add(hex)) throw new Exception("Duplicate selected chunk ID: " + hex);
                var data = reader.Read(id);
                File.WriteAllBytes(Path.Combine(rawDir, hex + ".bin"), data);
                named.TryGetValue(hex, out var path);
                chunks.Add(new { id = hex, path, size = data.Length,
                    sha256 = Convert.ToHexString(SHA256.HashData(data)) });
            }
        }
        Json(Path.Combine(work, "repack-manifest.json"), new {
            toc_version = tocVersion, header_version = headerVersion, mount_point = "../../../", packages, chunks
        });
        Console.WriteLine("EXTRACTED " + packages.Count + " packages, " + chunks.Count + " chunks");
    }
}
