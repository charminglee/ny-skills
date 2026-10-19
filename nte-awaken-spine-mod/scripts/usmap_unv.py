"""usmap parser + UE5 unversioned property blob walker.
Parses NTE_v1.3.usmap, decodes tagless property blobs (fragment bitstream) into
(schemaIdx -> prop path, raw bytes, decoded hint).
"""
import struct
from collections import namedtuple

PType = {0: "Byte", 1: "Bool", 2: "Int", 3: "Float", 4: "Object", 5: "Name",
         6: "Delegate", 7: "Double", 8: "Array", 9: "Struct", 10: "Str",
         11: "Text", 12: "Interface", 13: "MulticastDelegate", 14: "WeakObj",
         15: "LazyObj", 16: "AssetObj", 17: "SoftObj", 18: "UInt64",
         19: "UInt32", 20: "UInt16", 21: "Int64", 22: "Int16", 23: "Int8",
         24: "Map", 25: "Set", 26: "Enum", 27: "FieldPath",
         28: "Optional", 29: "Utf8Str", 30: "AnsiStr"}
# matches UAssetAPI EUsmapPropertyType (this usmap is UAssetGUI-compatible)


class R:
    def __init__(self, d, p=0):
        self.d, self.p = d, p
    def u8(self):
        v = self.d[self.p]; self.p += 1; return v
    def u16(self):
        v = struct.unpack_from("<H", self.d, self.p)[0]; self.p += 2; return v
    def i16(self):
        v = struct.unpack_from("<h", self.d, self.p)[0]; self.p += 2; return v
    def i32(self):
        v = struct.unpack_from("<i", self.d, self.p)[0]; self.p += 4; return v
    def u32(self):
        v = struct.unpack_from("<I", self.d, self.p)[0]; self.p += 4; return v
    def i64(self):
        v = struct.unpack_from("<q", self.d, self.p)[0]; self.p += 8; return v
    def raw(self, n):
        v = self.d[self.p:self.p+n]; self.p += n; return v
    def istr(self):
        ln = self.u16()
        s = self.d[self.p:self.p+ln].decode("latin1"); self.p += ln
        return s


class Usmap:
    def __init__(self, path):
        d = open(path, "rb").read()
        r = R(d)
        assert r.u16() == 0x30C4
        self.version = r.u8()
        hasver = r.i32()
        assert hasver == 0, "versioned usmap not handled"
        comp = r.u8()  # version>=PackageVersioning(1) reads this flag
        csize = r.u32(); dsize = r.u32()
        assert comp == 0, f"compressed usmap ({comp}) not handled"
        self.names = [r.istr() for _ in range(r.i32())]
        # enums
        self.enums = {}
        for _ in range(r.i32()):
            en = self.name(r.i32())
            cnt = r.i16() if self.version >= 3 else r.u8()   # LargeEnums=3
            vals = {}
            for _ in range(cnt):
                if self.version >= 4:  # ExplicitEnumValues=4
                    v = r.i64(); vals[v] = self.name(r.i32())
                else:
                    vals[len(vals)] = self.name(r.i32())
            self.enums[en] = vals
        # schemas
        self.schemas = {}
        self.schema_order = []
        for _ in range(r.i32()):
            nm = self.name(r.i32())
            sup = self.name(r.i32())
            num_props = r.u16()
            ser_cnt = r.u16()
            props = {}
            for _ in range(ser_cnt):
                idx = r.u16()
                arr = r.u8()
                pname = self.name(r.i32())
                pdata = self._prop(r)
                props[idx] = (pname, arr, pdata)
            self.schemas[nm] = {"super": sup, "num": num_props, "props": props}
            self.schema_order.append(nm)

    def name(self, i):
        return self.names[i] if 0 <= i < len(self.names) else f"?name{i}"

    def _prop(self, r):
        t = r.u8()
        info = {"type": t}
        if t == 26:     # Enum: inner type + enum name
            info["inner"] = self._prop(r)
            info["enum"] = self.name(r.i32())
        elif t == 9:    # Struct: struct type name
            info["struct"] = self.name(r.i32())
        elif t in (8, 25, 28):  # Array/Set/Optional: inner
            info["inner"] = self._prop(r)
        elif t == 24:   # Map
            info["inner"] = self._prop(r)
            info["value"] = self._prop(r)
        return info

    def type_name(self, pdata):
        return PType.get(pdata["type"], f"t{pdata['type']}")


# ---------- unversioned blob walker ----------

FRAG_SKIP = 0x7F
FRAG_ZERO = 0x80
FRAG_LAST = 0x100
FRAG_SHIFT = 9


def decode_blob(usmap, class_name, blob, max_props=4096):
    """Walk the unversioned fragment header; return list of (schemaIdx, isNonZero, raw_or_None)."""
    r = R(blob)
    frags = []
    zero_bits = 0
    unmasked = 0
    while True:
        packed = r.u16()
        skip = packed & FRAG_SKIP
        hasz = bool(packed & FRAG_ZERO)
        vnum = (packed >> FRAG_SHIFT) & 0x7F
        last = bool(packed & FRAG_LAST)
        frags.append((skip, hasz, vnum, last))
        if hasz:
            zero_bits += vnum
        else:
            unmasked += vnum
        if last:
            break
        if len(frags) > 1024:
            raise ValueError("fragment run too long")
    # zero mask
    zeromask = None
    if zero_bits > 0:
        nb = 1 if zero_bits <= 8 else (2 if zero_bits <= 16 else ((zero_bits + 31)//32)*4)
        mb = r.raw(nb)
        bits = []
        for i in range(zero_bits):
            bits.append((mb[i // 8] >> (i % 8)) & 1 == 1)   # FBitArray: bit i of byte i/8
        zeromask = bits
    # walk schema positions
    out = []
    si = 0
    zi = 0
    fi = 0
    values_read = 0

    def skip_to_values():
        nonlocal si, fi, values_read
        si += frags[fi][0]
        while frags[fi][2] == 0:
            if frags[fi][3]:
                raise ValueError("last fragment in skip")
            fi += 1
            si += frags[fi][0]
        values_read = frags[fi][2]

    if unmasked > 0 or (zeromask is not None and not all(zeromask)):
        skip_to_values()
    total = sum(f[2] for f in frags)
    n = 0
    while n < total:
        skip, hasz, vnum, last = frags[fi]
        is_nz = (not hasz) or (not zeromask[zi])
        out.append((si, is_nz, None))
        if is_nz:
            out[-1] = (si, True, None)  # value position marker; raw filled later
        zi += 1 if hasz else 0
        n += 1
        values_read -= 1
        si += 1
        if values_read == 0:
            if last:
                break
            fi += 1
            skip_to_values()
        if n > max_props:
            raise ValueError("prop walk overflow")
    # now read raw bytes for nonzero entries, in order
    res = []
    for si, nz, _ in out:
        if nz:
            res.append((si, True, r))   # caller reads lazily
        else:
            res.append((si, False, None))
    return res, r, frags


def flatten_props(usmap, class_name, _depth=0):
    """Return {schemaIdx: (path, pdata)} for a class incl. super chain."""
    if class_name not in usmap.schemas or _depth > 12:
        return {}
    s = usmap.schemas[class_name]
    out = {}
    for idx, (pname, arr, pdata) in s["props"].items():
        out[idx] = (f"{class_name}.{pname}", pdata)
    return out


# ---------- value skipping / reading per type ----------

SIMPLE_SIZE = {0:1, 1:1, 2:4, 3:4, 4:4, 5:8, 6:8, 7:8, 14:4, 15:4, 16:4,
               17:4, 18:8, 19:4, 20:2, 21:8, 22:2, 23:1, 26:1, 27:0, 28:0,
               29:0, 30:0}
# delegates (6,13): empty inline array i32

class BlobReader:
    def __init__(self, usmap, data):
        self.u = usmap
        self.d = data
        self.p = 0
    def take(self, n):
        v = self.d[self.p:self.p+n]; self.p += n; return v
    def skip_val(self, pdata, path=""):
        t = pdata["type"]
        if t in (8, 25):        # array/set: i32 count + elements
            n = struct.unpack_from("<i", self.d, self.p)[0]; self.p += 4
            for _ in range(max(n, 0)):
                self.skip_val(pdata["inner"], path+"[]")
        elif t == 24:           # map
            n = struct.unpack_from("<i", self.d, self.p)[0]; self.p += 4
            for _ in range(max(n, 0)):
                self.skip_val(pdata["inner"], path+"[k]")
                self.skip_val(pdata["value"], path+"[v]")
        elif t == 28:           # optional: byte present flag + value
            has = self.d[self.p]; self.p += 1
            if has:
                self.skip_val(pdata["inner"], path+"opt")
        elif t == 9:            # struct: recurse via usmap struct schema
            st = pdata.get("struct")
            if st and st in self.u.schemas:
                # struct schemas have own-local indices too
                s = self.u.schemas[st]
                # order props by index
                for idx in sorted(s["props"]):
                    pn, arr, pd = s["props"][idx]
                    for _ in range(max(arr, 1)):
                        self.skip_val(pd, f"{path}.{pn}")
            elif st == "LinearColor":
                self.take(16)
            else:
                raise ValueError(f"unknown struct {st} at {path}")
        elif t == 10:           # str: FString
            n = struct.unpack_from("<i", self.d, self.p)[0]; self.p += 4
            if n < 0:
                self.take(-n*2)
            elif n > 0:
                self.take(n)
        elif t == 11:           # text: kind byte + ...
            kind = struct.unpack_from("<b", self.d, self.p)[0]; self.p += 1
            if kind == -1:
                self.take(4)    # invariant: i32 idx? actually name idx
            elif kind == 0:
                pass            # culture-invariant empty
            else:
                raise ValueError(f"text kind {kind} at {path}")
        elif t in (6, 13):      # delegate / multicast: inline array
            n = struct.unpack_from("<i", self.d, self.p)[0]; self.p += 4
            self.take(8*n)
        else:
            sz = SIMPLE_SIZE.get(t)
            if sz is None:
                raise ValueError(f"no size for type {t} at {path}")
            self.take(sz)


def decode_class_blob(usmap, class_name, blob):
    """Return list of (flatIdx, path, pdata, rawbytes|None) for a tagless blob."""
    entries, r, frags = decode_blob(usmap, class_name, blob)
    # build chain: class then supers
    chain = []
    c = class_name
    while c in usmap.schemas and len(chain) < 16:
        chain.append(c)
        c = usmap.schemas[c]["super"]
    cum = []
    base = 0
    for cn in chain:
        cum.append((base, base + usmap.schemas[cn]["num"], cn))
        base += usmap.schemas[cn]["num"]
    def locate(idx):
        for lo, hi, cn in cum:
            if lo <= idx < hi:
                return cn, idx - lo
        return None, None
    br = BlobReader(usmap, blob)
    results = []
    # redo the walk consuming values in order
    p = r.p   # position after header+zeromask
    br.p = p
    flat = []
    si = 0; zi = 0; fi = 0; values_read = 0
    total = sum(f[2] for f in frags)
    def skip_to_values():
        nonlocal si, fi, values_read
        si += frags[fi][0]
        while frags[fi][2] == 0:
            if frags[fi][3]:
                raise ValueError("last frag in skip")
            fi += 1
            si += frags[fi][0]
        values_read = frags[fi][2]
    if total > 0:
        skip_to_values()
    for n in range(total):
        skip, hasz, vnum, last = frags[fi]
        is_nz = (not hasz) or (not zeromask_flags[zi])
        start = br.p
        cn, li = locate(si)
        pdata = None; path = None
        if cn is not None:
            props = usmap.schemas[cn]["props"]
            if li in props:
                pn, arr, pdata = props[li]
                path = f"{cn}.{pn}"
        try:
            if pdata is not None:
                br.skip_val(pdata, path or "?")
            end = br.p
            results.append((si, path, is_nz, blob[start:end], pdata))
        except Exception as e:
            results.append((si, path, is_nz, blob[start:start+8] + b"..ERR:" + str(e).encode(), pdata))
            break
        zi += 1 if hasz else 0
        si += 1
        values_read -= 1
        if values_read == 0:
            if last:
                break
            fi += 1
            skip_to_values()
    return results, br.p, len(blob)
