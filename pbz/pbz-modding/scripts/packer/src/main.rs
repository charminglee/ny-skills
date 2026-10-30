use anyhow::{Context, Result, ensure};
use retoc::{EIoStoreTocVersion, FIoChunkId, FIoChunkIdRaw, UEPathBuf};
use retoc::container_header::{EIoContainerHeaderVersion, StoreEntry};
use retoc::iostore_writer::IoStoreWriter;
use serde::Deserialize;
use std::{collections::HashMap, fs, io::BufWriter, path::PathBuf};

#[derive(Deserialize)]
struct Manifest {
    toc_version: EIoStoreTocVersion,
    header_version: EIoContainerHeaderVersion,
    mount_point: String,
    packages: Vec<Package>,
    chunks: Vec<Chunk>,
}

#[derive(Deserialize)]
struct Package {
    path: String,
    chunk_id: String,
    store_entry: StoreEntry,
}

#[derive(Deserialize)]
struct Chunk {
    id: String,
    path: Option<String>,
    size: usize,
}

fn main() -> Result<()> {
    let args: Vec<String> = std::env::args().collect();
    ensure!(args.len() == 3, "usage: pbz_iostore_pack <manifest.json> <output.utoc>");
    let manifest_path = PathBuf::from(&args[1]);
    let output = PathBuf::from(&args[2]);
    let work = manifest_path.parent().context("manifest parent missing")?;
    let manifest: Manifest = serde_json::from_slice(&fs::read(&manifest_path)?)?;
    ensure!(output.extension().is_some_and(|ext| ext == "utoc"), "output must be .utoc");
    for extension in ["utoc", "ucas", "pak"] {
        let path = output.with_extension(extension);
        ensure!(!path.exists(), "output already exists: {}", path.display());
    }
    ensure!(!manifest.packages.is_empty(), "empty package whitelist");
    let mut seen_chunks = std::collections::HashSet::new();
    for chunk in &manifest.chunks {
        let _: FIoChunkIdRaw = chunk.id.parse()?;
        ensure!(seen_chunks.insert(chunk.id.as_str()), "duplicate chunk ID");
    }
    fs::create_dir_all(output.parent().context("output parent missing")?)?;

    // Rebuild the container header for exactly the selected original packages.
    let mut writer = IoStoreWriter::new(
        &output,
        manifest.toc_version,
        Some(manifest.header_version),
        manifest.mount_point.clone().into(),
    )?;
    let packages: HashMap<&str, &Package> = manifest.packages.iter()
        .map(|package| (package.chunk_id.as_str(), package)).collect();
    ensure!(packages.len() == manifest.packages.len(), "duplicate package chunk ID");
    let mut package_count = 0;
    for chunk in &manifest.chunks {
        let raw: FIoChunkIdRaw = chunk.id.parse()?;
        let data = fs::read(work.join("raw-chunks").join(format!("{}.bin", chunk.id)))?;
        ensure!(data.len() == chunk.size, "size mismatch for {}", chunk.id);
        let id = FIoChunkId::from_raw(raw, manifest.toc_version);
        let path: Option<UEPathBuf> = chunk.path.as_ref()
            .map(|path| format!("{}{}", manifest.mount_point, path).into());
        if let Some(package) = packages.get(chunk.id.as_str()) {
            ensure!(chunk.path.as_ref() == Some(&package.path), "package path mismatch");
            writer.write_package_chunk(id, path.as_deref(), &data, &package.store_entry)?;
            package_count += 1;
        } else {
            writer.write_chunk(id, path.as_deref(), &data)?;
        }
    }
    ensure!(package_count == manifest.packages.len(), "missing package chunks");
    writer.finalize()?;

    // An empty companion PAK lets the game discover the IoStore container.
    let pak_path = output.with_extension("pak");
    ensure!(!pak_path.exists(), "companion pak already exists");
    let mut pak_file = BufWriter::new(fs::File::create(pak_path)?);
    repak::PakBuilder::new().writer(
        &mut pak_file, repak::Version::V11, manifest.mount_point.clone(), None,
    ).write_index()?;
    println!("PACKED packages={} chunks={} toc={:?} header={:?}",
        package_count, manifest.chunks.len(), manifest.toc_version, manifest.header_version);
    Ok(())
}
