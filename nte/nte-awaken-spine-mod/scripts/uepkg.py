"""Exact UE5.6 legacy (.uasset) reader/writer matching trumank/retoc's legacy_asset.rs
output (unversioned, filter-editor-only, with saved_hash).

Layout facts (all verified against retoc source + byte dumps):
- name entry   : FString (i32 len incl NUL; negative = UTF-16) + u16 + u16 hashes
- import entry : class_pkg{i32,i32} class_name{i32,i32} outer i32 object_name{i32,i32}
                 optional i32   = 32 bytes   (cooked: no package_name field)
- export entry : class,super,template,outer (i32 x4) name{i32,i32} flags u32
                 serial_size i64 serial_offset i64 forced i32 not_for_client i32
                 not_for_server i32 inherited i32 pkg_flags u32 not_always i32
                 is_asset i32 gen_public_hash i32 first_dep i32 sbs i32 cbs i32
                 sbc i32 cbc i32                = 96 bytes
- preload deps : Vec<i32> FPackageIndex (4 bytes each)
- imports/exports/preload referenced by FPackageIndex: import = -1-idx, export = 1-based
"""
import struct

MAGIC = 0x9E2A83C1


class R:
    def __init__(self, d, p=0):
        self.d, self.p = d, p

    def i8(self):
        v = struct.unpack_from('<b', self.d, self.p)[0]; self.p += 1; return v
    def u8(self):
        v = self.d[self.p]; self.p += 1; return v
    def i16(self):
        v = struct.unpack_from('<h', self.d, self.p)[0]; self.p += 2; return v
    def u16(self):
        v = struct.unpack_from('<H', self.d, self.p)[0]; self.p += 2; return v
    def i32(self):
        v = struct.unpack_from('<i', self.d, self.p)[0]; self.p += 4; return v
    def u32(self):
        v = struct.unpack_from('<I', self.d, self.p)[0]; self.p += 4; return v
    def i64(self):
        v = struct.unpack_from('<q', self.d, self.p)[0]; self.p += 8; return v
    def raw(self, n):
        v = self.d[self.p:self.p + n]; self.p += n; return v
    def fstring(self):
        n = self.i32()
        if n == 0:
            return ''
        if n < 0:
            s = self.raw(-n * 2).decode('utf-16-le', 'replace').rstrip('\x00')
        else:
            s = self.raw(n).decode('latin1', 'replace').rstrip('\x00')
        return s
    def name(self):
        return (self.i32(), self.i32())   # FMinimalName {index, number}


class W:
    def __init__(self):
        self.b = bytearray()
    def i8(self, v):  self.b += struct.pack('<b', v)
    def u8(self, v):  self.b += struct.pack('<B', v)
    def i16(self, v): self.b += struct.pack('<h', v)
    def u16(self, v): self.b += struct.pack('<H', v)
    def i32(self, v): self.b += struct.pack('<i', v)
    def u32(self, v): self.b += struct.pack('<I', v)
    def i64(self, v): self.b += struct.pack('<q', v)
    def raw(self, v): self.b += v
    def fstring(self, s):
        if s == '':
            self.i32(0); return
        e = s.encode('latin1')
        self.i32(len(e) + 1); self.b += e; self.b += b'\x00'
    def nm(self, n):
        self.i32(n[0]); self.i32(n[1])


class Import:
    __slots__ = ('class_package', 'class_name', 'outer', 'object_name', 'optional')
    def __init__(self):
        self.class_package = (0, 0)   # FMinimalName (index, number)
        self.class_name = (0, 0)
        self.outer = 0                # raw FPackageIndex (0 none, -1-idx import)
        self.object_name = (0, 0)
        self.optional = 0


class Export:
    __slots__ = ('class_index', 'super_index', 'template_index', 'outer', 'object_name',
                 'flags', 'serial_size', 'serial_offset', 'tail')
    def __init__(self):
        self.tail = b''   # 96B entry: everything after serial_offset (60 bytes)


class Package:
    def __init__(self, path):
        self.path = path
        self.data = open(path, 'rb').read()
        r = R(self.data)
        assert r.u32() == MAGIC
        self.legacy_version = r.i32()
        assert self.legacy_version == -9, f'legacy {self.legacy_version}'
        self.legacy_ue3 = r.i32()
        self.ver_ue4 = r.i32()
        self.ver_ue5 = r.i32()
        self.ver_licensee = r.i32()
        self.saved_hash = r.raw(20)
        self.total_header_size = r.i32()
        self.custom_count = r.i32()
        assert self.custom_count == 0
        self.package_name = r.fstring()
        self.orig_package_name = self.package_name
        self.package_flags = r.u32()
        self.name_count, self.name_offset = r.i32(), r.i32()
        self.softobj_count, self.softobj_offset = r.i32(), r.i32()
        self.gather_count, self.gather_offset = r.i32(), r.i32()
        self.export_count, self.export_offset = r.i32(), r.i32()
        self.import_count, self.import_offset = r.i32(), r.i32()
        self.cellx_count, self.cellx_offset = r.i32(), r.i32()
        self.celli_count, self.celli_offset = r.i32(), r.i32()
        self.metadata_offset = r.i32()
        self.depends_offset = r.i32()
        self.softref_count, self.softref_offset = r.i32(), r.i32()
        self.searchable_offset = r.i32()
        self.thumbnail_offset = r.i32()
        gen_count = r.i32()
        self.generations = [(r.i32(), r.i32()) for _ in range(gen_count)]
        self.saved_engine = (r.u16(), r.u16(), r.u16(), r.i32(), r.fstring())
        self.compat_engine = (r.u16(), r.u16(), r.u16(), r.i32(), r.fstring())
        self.compression_flags = r.u32()
        assert self.compression_flags == 0
        assert r.i32() == 0        # compressed chunks
        self.package_source = r.u32()
        assert r.i32() == 0        # additional packages to cook
        self.asset_registry_offset = r.i32()
        self.bulk_data_start = r.i64()
        self.world_tile_offset = r.i32()
        chunk_count = r.i32()
        assert chunk_count == 0
        self.preload_count, self.preload_offset = r.i32(), r.i32()
        self.names_ref_count = r.i32()
        self.payload_toc = r.i64()
        self.data_resource_offset = r.i32()
        self.summary_end = r.p
        assert r.p == self.name_offset, f'summary {r.p} != names {self.name_offset}'

        # names
        r.p = self.name_offset
        self.names = []
        for _ in range(self.name_count):
            s = r.fstring()
            r.u16(); r.u16()      # case hashes
            self.names.append(s)
        assert r.p == self.import_offset, f'names end {r.p} != imports {self.import_offset}'
        self.name_index = {n: i for i, n in enumerate(self.names)}

        # imports (32B entries)
        r.p = self.import_offset
        self.imports = []
        for _ in range(self.import_count):
            im = Import()
            im.class_package = r.name()
            im.class_name = r.name()
            im.outer = r.i32()
            im.object_name = r.name()
            im.optional = r.i32()
            self.imports.append(im)
        assert r.p == self.export_offset, f'imports end {r.p} != exports {self.export_offset}'

        # exports (96B entries)
        r.p = self.export_offset
        self.exports = []
        for _ in range(self.export_count):
            e = Export()
            e.class_index = r.i32()
            e.super_index = r.i32()
            e.template_index = r.i32()
            e.outer = r.i32()
            e.object_name = r.name()
            e.flags = r.u32()
            e.serial_size = r.i64()
            e.serial_offset = r.i64()
            e.tail = r.raw(96 - 44)      # 52 bytes of trailing fields
            self.exports.append(e)
        assert r.p == self.depends_offset, f'exports end {r.p} != depends {self.depends_offset}'
        assert self.depends_offset + 4 * self.export_count == self.asset_registry_offset, \
            'depends block size mismatch'
        assert self.total_header_size == len(self.data), 'header != file size'
        self.rest = self.data[self.depends_offset:]   # depends + preload + padding
        self.uexp_growth = 0    # extra bytes appended to .uexp (bumps bulk_data_start)

    # ---------- helpers ----------

    def name_str(self, nm):
        s = self.names[nm[0]]
        if nm[1]:
            s += f'_{nm[1] - 1}'
        return s

    def import_path(self, tbl_idx):
        im = self.imports[tbl_idx]
        if self.name_str(im.class_name) == 'Package':
            return self.name_str(im.object_name)
        parts = [self.name_str(im.object_name)]
        cur = im.outer
        while cur:
            assert cur < 0, f'import outer points to export? {cur}'
            o = self.imports[-cur - 1]
            parts.append(self.name_str(o.object_name))
            if self.name_str(o.class_name) == 'Package':
                break
            cur = o.outer
        return '/'.join(reversed(parts))

    def find_import(self, path):
        for i in range(len(self.imports)):
            if self.import_path(i) == path:
                return i
        return None

    def add_name(self, s):
        if s in self.name_index:
            return self.name_index[s]
        self.names.append(s)
        self.name_index[s] = len(self.names) - 1
        return len(self.names) - 1

    def add_package_import(self, pkg_path):
        im = Import()
        im.class_package = (self.add_name('/Script/CoreUObject'), 0)
        im.class_name = (self.add_name('Package'), 0)
        im.outer = 0
        im.object_name = (self.add_name(pkg_path), 0)
        im.optional = self.imports[-1].optional
        self.imports.append(im)
        return -(len(self.imports) - 1) - 1     # FPackageIndex for the new import

    def add_object_import(self, cls_pkg, cls_name, pkg_fpi, obj_name):
        """Append an object import inside the package import pkg_fpi; returns FPackageIndex."""
        im = Import()
        im.class_package = (self.add_name(cls_pkg), 0)
        im.class_name = (self.add_name(cls_name), 0)
        im.outer = pkg_fpi
        im.object_name = (self.add_name(obj_name), 0)
        im.optional = self.imports[-1].optional
        self.imports.append(im)
        return -(len(self.imports) - 1) - 1

    def repoint_import(self, tbl_idx, pkg_fpi, new_obj_name):
        im = self.imports[tbl_idx]
        im.outer = pkg_fpi
        im.object_name = (self.add_name(new_obj_name), 0)

    # ---------- serialization ----------

    def serialize(self):
        names_w = W()
        for s in self.names:
            names_w.fstring(s)
            names_w.u16(0); names_w.u16(0)
        names_bytes = bytes(names_w.b)

        imp_w = W()
        for im in self.imports:
            imp_w.nm(im.class_package)
            imp_w.nm(im.class_name)
            imp_w.i32(im.outer)
            imp_w.nm(im.object_name)
            imp_w.i32(im.optional)
        imports_bytes = bytes(imp_w.b)

        delta = (len(names_bytes) - (self.import_offset - self.name_offset)) \
            + (len(imports_bytes) - (self.export_offset - self.import_offset))
        names_delta = len(names_bytes) - (self.import_offset - self.name_offset)
        imp_delta = len(imports_bytes) - (self.export_offset - self.import_offset)
        old_plen = 0 if self.orig_package_name == '' else 4 + len(self.orig_package_name.encode('latin1')) + 1
        new_plen = 0 if self.package_name == '' else 4 + len(self.package_name.encode('latin1')) + 1
        summary_delta = new_plen - old_plen
        total_delta = summary_delta + names_delta + imp_delta

        def shift(v):
            # sections at/after the export table move by everything
            return v + total_delta if v >= self.export_offset else v
        def shift_imp(v):
            # import table start moves by summary + names growth
            return v + summary_delta + names_delta if v >= self.import_offset else v
        def shift_mid(v):
            # anything inside the summary that points at the name table
            return v + summary_delta if v >= self.name_offset else v

        w = W()
        w.u32(MAGIC)
        w.i32(self.legacy_version)
        w.i32(self.legacy_ue3)
        w.i32(self.ver_ue4)
        w.i32(self.ver_ue5)
        w.i32(self.ver_licensee)
        w.raw(self.saved_hash)
        w.i32(self.total_header_size + total_delta)
        w.i32(self.custom_count)
        w.fstring(self.package_name)
        w.u32(self.package_flags)
        w.i32(len(self.names)); w.i32(self.name_offset + summary_delta)
        w.i32(self.softobj_count); w.i32(shift_imp(self.softobj_offset))
        w.i32(self.gather_count); w.i32(shift(self.gather_offset))
        w.i32(self.export_count); w.i32(shift(self.export_offset))
        w.i32(len(self.imports)); w.i32(shift_imp(self.import_offset))
        w.i32(self.cellx_count); w.i32(shift(self.cellx_offset))
        w.i32(self.celli_count); w.i32(shift(self.celli_offset))
        w.i32(shift(self.metadata_offset))
        w.i32(shift(self.depends_offset))
        w.i32(self.softref_count); w.i32(shift(self.softref_offset))
        w.i32(shift(self.searchable_offset))
        w.i32(shift(self.thumbnail_offset))
        w.i32(len(self.generations))
        for g in self.generations:
            w.i32(g[0])
            w.i32(g[1] if g[1] != self.name_count else len(self.names))
        for eng in (self.saved_engine, self.compat_engine):
            w.u16(eng[0]); w.u16(eng[1]); w.u16(eng[2]); w.i32(eng[3]); w.fstring(eng[4])
        w.u32(self.compression_flags)
        w.i32(0)
        w.u32(self.package_source)
        w.i32(0)
        w.i32(shift(self.asset_registry_offset))
        w.i64(self.bulk_data_start + total_delta + self.uexp_growth)
        w.i32(shift(self.world_tile_offset))
        w.i32(0)
        w.i32(self.preload_count); w.i32(shift(self.preload_offset))
        w.i32(self.names_ref_count)
        w.i64(self.payload_toc)
        w.i32(self.data_resource_offset)
        assert w.b == self.data[:self.summary_end] if total_delta == 0 else True, 'summary mismatch'
        w.b += names_bytes
        w.b += imports_bytes

        ew = W()
        for e in self.exports:
            ew.i32(e.class_index)
            ew.i32(e.super_index)
            ew.i32(e.template_index)
            ew.i32(e.outer)
            ew.nm(e.object_name)
            ew.u32(e.flags)
            ew.i64(e.serial_size)
            ew.i64(e.serial_offset + total_delta)
            ew.raw(e.tail)
        w.b += bytes(ew.b)
        w.b += self.rest
        out = bytes(w.b)
        assert len(out) == self.total_header_size + total_delta, 'size mismatch'
        return out

    def write(self, out_uasset, uexp_path=None, out_uexp=None):
        open(out_uasset, 'wb').write(self.serialize())
        if uexp_path:
            open(out_uexp, 'wb').write(open(uexp_path, 'rb').read())
