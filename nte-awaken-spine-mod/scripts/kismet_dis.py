"""Minimal Kismet bytecode disassembler for UE5 cooked packages (retoc legacy output).
Usage: python kismet_dis.py <pkg_base_no_ext> <export_index>
Handles the opcodes needed to read control flow and constants; bails loudly on unknowns.
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uepkg

OPS = {
    0x00: "LocalVariable", 0x01: "InstanceVariable", 0x02: "DefaultVariable",
    0x04: "Return", 0x06: "Jump", 0x07: "JumpIfNot", 0x09: "Assert",
    0x0B: "Nothing", 0x0C: "NothingInt32", 0x0F: "Let", 0x11: "BitFieldConst",
    0x12: "ClassContext", 0x13: "MetaCast", 0x14: "LetBool", 0x15: "EndParmValue",
    0x16: "EndFunctionParms", 0x17: "Self", 0x18: "Skip", 0x19: "Context",
    0x1A: "Context_FailSilent", 0x1B: "VirtualFunction", 0x1C: "FinalFunction",
    0x1D: "IntConst", 0x1E: "FloatConst", 0x1F: "StringConst", 0x20: "ObjectConst",
    0x21: "NameConst", 0x22: "RotationConst", 0x23: "VectorConst", 0x24: "ByteConst",
    0x25: "IntZero", 0x26: "IntOne", 0x27: "True", 0x28: "False", 0x29: "TextConst",
    0x2A: "NoObject", 0x2B: "TransformConst", 0x2C: "IntConstByte", 0x2D: "NoInterface",
    0x2E: "DynamicCast", 0x2F: "StructConst", 0x30: "EndStructConst", 0x31: "SetArray",
    0x32: "EndArray", 0x33: "PropertyConst", 0x34: "UnicodeStringConst",
    0x35: "Int64Const", 0x36: "UInt64Const", 0x37: "DoubleConst", 0x38: "PrimitiveCast",
    0x39: "SetSet", 0x3A: "EndSet", 0x3B: "SetMap", 0x3C: "EndMap", 0x3D: "SetConst",
    0x3E: "EndSetConst", 0x3F: "MapConst", 0x40: "EndMapConst", 0x41: "Vector3fConst",
    0x42: "StructMemberContext", 0x43: "LetMulticastDelegate", 0x44: "LetDelegate",
    0x45: "LocalVirtualFunction", 0x46: "LocalFinalFunction", 0x48: "LocalOutVariable",
    0x4A: "DeprecatedOp4A", 0x4B: "InstanceDelegate", 0x4C: "PushExecutionFlow",
    0x4D: "PopExecutionFlow", 0x4E: "ComputedJump", 0x4F: "PopExecutionFlowIfNot",
    0x50: "Breakpoint", 0x51: "InterfaceContext", 0x52: "ObjToInterfaceCast",
    0x53: "EndOfScript", 0x54: "CrossInterfaceCast", 0x55: "InterfaceToObjCast",
    0x5A: "WireTracepoint", 0x5B: "SkipOffsetConst", 0x5C: "AddMulticastDelegate",
    0x5D: "ClearMulticastDelegate", 0x5E: "Tracepoint", 0x5F: "LetObj",
    0x60: "LetWeakObjPtr", 0x61: "BindDelegate", 0x62: "RemoveMulticastDelegate",
    0x63: "CallMulticastDelegate", 0x64: "LetValueOnPersistentFrame", 0x65: "ArrayConst",
    0x66: "EndArrayConst", 0x67: "SoftObjectConst", 0x68: "CallMath",
    0x69: "SwitchValue", 0x6A: "InstrumentationEvent", 0x6B: "ArrayGetByRef",
    0x6C: "ClassSparseDataVariable", 0x6D: "FieldPathConst",
}


class Dis:
    def __init__(self, pkg, code):
        self.pkg = pkg
        self.d = code
        self.p = 0

    def err(self, msg):
        raise RuntimeError(f"@0x{self.p-1:x}: {msg} bytes={self.d[self.p-1:self.p+16].hex()}")

    def u8(self):
        v = self.d[self.p]; self.p += 1; return v
    def i16(self):
        import struct
        v = struct.unpack_from("<h", self.d, self.p)[0]; self.p += 2; return v
    def u16(self):
        import struct
        v = struct.unpack_from("<H", self.d, self.p)[0]; self.p += 2; return v
    def i32(self):
        import struct
        v = struct.unpack_from("<i", self.d, self.p)[0]; self.p += 4; return v
    def u32(self):
        import struct
        v = struct.unpack_from("<I", self.d, self.p)[0]; self.p += 4; return v
    def i64(self):
        import struct
        v = struct.unpack_from("<q", self.d, self.p)[0]; self.p += 8; return v
    def f32(self):
        import struct
        v = struct.unpack_from("<f", self.d, self.p)[0]; self.p += 4; return v
    def f64(self):
        import struct
        v = struct.unpack_from("<d", self.d, self.p)[0]; self.p += 8; return v

    def prop_pointer(self):
        """XFER_PROP_POINTER, FFieldPath format: i32 count + count x FName + i32 owner."""
        cnt = self.i32()
        names = [self.nameref() for _ in range(cnt)]
        owner = self.i32()
        return "=".join(names) + "@" + self.ref_str(owner)

    def objref(self):
        i = self.i32()
        return self.ref_str(i)

    def ref_str(self, i):
        pkg = self.pkg
        if i == 0:
            return "null"
        if i < 0:
            idx = -1 - i
            if idx < len(pkg.imports):
                return f"imp[{idx}]:{pkg.import_path(idx)}"
            return f"imp?{idx}"
        if i - 1 < len(pkg.exports):
            return f"exp[{i-1}]:{pkg.name_str(pkg.exports[i-1].object_name)}"
        return f"exp?{i-1}"

    def nameref(self):
        i = self.i32(); n = self.i32()
        if 0 <= i < len(self.pkg.names):
            s = self.pkg.names[i]
            return f"{s}" + (f"_{n-1}" if n else "")
        return f"name?{i}"

    def parms(self, out):
        while True:
            op = self.d[self.p]
            if op == 0x16:
                self.p += 1
                out.append("EndParms")
                return
            self.expr(out)

    def fstring_ascii(self):
        s = bytearray()
        while self.d[self.p] != 0:
            s.append(self.d[self.p]); self.p += 1
        self.p += 1
        return s.decode("ascii", "replace")

    def textconst(self, out):
        kind = self.u8()
        if kind == 0:
            out.append("Text(hist=none)")
        elif kind == -1:
            out.append("Text(invariant)")
        elif kind in (1, 2):
            n = self.i32()
            self.p += n * (2 if n < 0 else 1)
            out.append("Text(argfmt)")
        elif kind == 3:
            ns = self.fstring_ascii()
            key = self.fstring_ascii()
            src = self.fstring_ascii()
            out.append(f"Text({src!r})")
        else:
            self.err(f"TextConst kind {kind}")

    def expr(self, out, depth=0):
        op = self.u8()
        name = OPS.get(op)
        if name is None:
            self.err(f"unknown opcode 0x{op:02x}")
        if op in (0x00, 0x48):          # LocalVariable/LocalOutVariable: prop pointer
            out.append(f"{name}({self.prop_pointer()})")
        elif op == 0x02:                # DefaultVariable: prop pointer + expr
            out.append(f"{name}({self.prop_pointer()})")
            self.expr(out, depth + 1)
        elif op == 0x01:                # InstanceVariable: prop pointer only
            out.append(f"{name}({self.prop_pointer()})")
        elif op == 0x04:
            cp = self.u32(); out.append(f"Return({cp:#x})")
        elif op == 0x06:
            off = self.u32(); out.append(f"Jump(->{off:#x})")
        elif op == 0x07:
            off = self.u32(); out.append(f"JumpIfNot(->{off:#x})")
            self.expr(out, depth + 1)
        elif op == 0x09:
            off = self.u16(); k = self.u8(); out.append(f"Assert({off},{k})")
            self.expr(out, depth + 1)
        elif op == 0x0B:
            out.append("Nothing")
        elif op == 0x0C:
            out.append(f"NothingInt32({self.u32()})")
        elif op == 0x0F:                # Let: prop pointer + variable expr + value expr
            out.append(f"Let(value_ptr={self.prop_pointer()})")
            self.expr(out, depth + 1)
            self.expr(out, depth + 1)
        elif op == 0x11:                # BitFieldConst: u8 mask + prop pointer
            m = self.u8()
            out.append(f"BitFieldConst({m:02x},{self.prop_pointer()})")
        elif op in (0x12, 0x19, 0x1A):  # Context: objexpr + u32 offset + prop pointer + ctxexpr
            out.append(f"{name}:")
            self.expr(out, depth + 1)
            sk = self.u32()
            out.append(f"  {name}.offset={sk:#x} rvalue={self.prop_pointer()}")
            self.expr(out, depth + 1)
        elif op == 0x13:
            out.append(f"MetaCast({self.objref()})")
            self.expr(out, depth + 1)
        elif op == 0x14:
            out.append("LetBool")
            self.expr(out, depth + 1)
            self.expr(out, depth + 1)
        elif op in (0x18,):             # Skip: u32 + expr
            sk = self.u32()
            out.append(f"Skip({sk:#x})")
            self.expr(out, depth + 1)
        elif op == 0x1B:
            fn = self.fstring_ascii()
            out.append(f"VirtualFunction({fn})")
            self.parms(out)
        elif op == 0x1C:
            fr = self.objref()
            out.append(f"FinalFunction({fr})")
            self.parms(out)
        elif op == 0x1D:
            out.append(f"IntConst({self.i32()})")
        elif op == 0x1E:
            out.append(f"FloatConst({self.f32()})")
        elif op == 0x1F:
            out.append(f"StringConst({self.fstring_ascii()!r})")
        elif op == 0x20:
            out.append(f"ObjectConst({self.objref()})")
        elif op == 0x21:
            out.append(f"NameConst({self.nameref()})")
        elif op == 0x24:
            out.append(f"ByteConst({self.u8()})")
        elif op in (0x17, 0x25, 0x26, 0x27, 0x28, 0x2A, 0x2D):
            out.append(name)
        elif op == 0x29:
            self.textconst(out)
        elif op == 0x2B:                # TransformConst 4x f64 rot? + vec: 11 f64
            self.p += 11 * 8
            out.append("TransformConst")
        elif op == 0x2C:
            out.append(f"IntConstByte({self.u8()})")
        elif op == 0x2E:
            out.append(f"DynamicCast({self.objref()})")
            self.expr(out, depth + 1)
        elif op == 0x2F:
            sr = self.objref(); sz = self.i32()
            out.append(f"StructConst({sr},size={sz})")
            while True:
                if self.d[self.p] == 0x30:
                    self.p += 1; out.append("EndStruct"); break
                self.expr(out, depth + 1)
        elif op == 0x31:
            out.append("SetArray")
            self.expr(out, depth + 1)
            self.parms(out)
        elif op == 0x33:
            out.append(f"PropertyConst({self.nameref()})")
        elif op == 0x34:
            n = self.i32()
            s = self.d[self.p:self.p + n * 2].decode("utf-16-le", "replace"); self.p += n * 2
            out.append(f"UnicodeStringConst({s!r})")
        elif op == 0x35:
            out.append(f"Int64Const({self.i64()})")
        elif op == 0x36:
            out.append(f"UInt64Const({self.i64()})")
        elif op == 0x37:
            out.append(f"DoubleConst({self.f64()})")
        elif op == 0x38:
            conv = self.u8()
            out.append(f"PrimitiveCast({conv})")
            self.expr(out, depth + 1)
        elif op in (0x39, 0x3B, 0x3D, 0x3F):
            out.append(name)
            self.expr(out, depth + 1)   # inner set/map size expr
            while self.d[self.p] != OPS_INV.get(name.replace("Set", "End").replace("Map", "End"), 0):
                self.expr(out, depth + 1)
        elif op == 0x41:
            self.p += 12
            out.append("Vector3fConst")
        elif op == 0x42:
            fr = self.objref()
            out.append(f"StructMemberContext({fr})")
            self.expr(out, depth + 1)
        elif op in (0x43, 0x44):
            out.append(name)
            self.expr(out, depth + 1)
            self.expr(out, depth + 1)
        elif op == 0x45:
            fr = self.objref()
            out.append(f"LocalVirtualFunction({fr})")
            self.parms(out)
        elif op == 0x46:
            fr = self.objref()
            out.append(f"LocalFinalFunction({fr})")
            self.parms(out)
        elif op == 0x4B:
            out.append(f"InstanceDelegate({self.nameref()})")
        elif op == 0x4C:
            out.append(f"PushExecutionFlow({self.u32():#x})")
        elif op == 0x4D:
            out.append("PopExecutionFlow")
        elif op == 0x4F:
            out.append(f"PopExecutionFlowIfNot({self.u32():#x})")
        elif op == 0x50:
            out.append("Breakpoint")
        elif op in (0x51,):
            out.append("InterfaceContext")
            self.expr(out, depth + 1)
        elif op in (0x52, 0x54, 0x55):
            out.append(f"{name}({self.objref()})")
            self.expr(out, depth + 1)
        elif op == 0x4E:
            out.append("ComputedJump")
            self.expr(out, depth + 1)
        elif op == 0x53:
            out.append("EndOfScript")
        elif op == 0x5A:
            out.append(f"WireTracepoint({self.u32():#x})")
        elif op == 0x5B:
            out.append(f"SkipOffsetConst({self.u32():#x})")
        elif op == 0x5E:  # Tracepoint: func name
            out.append(f"Tracepoint({self.nameref()})")
        elif op in (0x5F, 0x60):
            out.append(name)
            self.expr(out, depth + 1)
            self.expr(out, depth + 1)
        elif op == 0x61:  # BindDelegate: name + delegate + object
            out.append(f"BindDelegate({self.nameref()})")
            self.expr(out, depth + 1)
            self.expr(out, depth + 1)
        elif op == 0x63:  # CallMulticastDelegate: ref + parms
            out.append(f"CallMulticastDelegate({self.objref()})")
            self.parms(out)
        elif op == 0x64:  # LetValueOnPersistentFrame: prop pointer + expr
            out.append(f"LetValueOnPersistentFrame({self.prop_pointer()})")
            self.expr(out, depth + 1)
        elif op == 0x65:  # ArrayConst: prop pointer + count + exprs
            out.append(f"ArrayConst({self.prop_pointer()}, n={self.i32()})")
            while self.d[self.p] != 0x66:
                self.expr(out, depth + 1)
            self.p += 1
            out.append("EndArrayConst")
        elif op == 0x67:
            out.append("SoftObjectConst")
            self.expr(out, depth + 1)
        elif op == 0x68:  # CallMath: ref + parms
            out.append(f"CallMath({self.objref()})")
            self.parms(out)
        elif op == 0x69:  # SwitchValue: u16 cases, u32 endgoto, index, cases, default
            n = self.u16(); endgo = self.u32()
            out.append(f"SwitchValue(cases={n},endgoto={endgo:#x})")
            out.append("  index:")
            self.expr(out, depth + 1)
            for ci in range(n):
                out.append(f"  case{ci}:")
                self.expr(out, depth + 1)
                go = self.u32()
                out.append(f"    goto {go:#x}")
                self.expr(out, depth + 1)
            out.append("  default:")
            self.expr(out, depth + 1)
        elif op == 0x6A:  # InstrumentationEvent: u8 (+name if inline)
            ev = self.u8()
            extra = f" event={self.nameref()}" if ev == 2 else ""
            out.append(f"InstrumentationEvent({ev}{extra})")
        elif op == 0x6B:
            out.append("ArrayGetByRef")
            self.expr(out, depth + 1)
            self.expr(out, depth + 1)
        elif op == 0x6C:
            out.append(f"ClassSparseDataVariable({self.prop_pointer()})")
        elif op == 0x6D:
            out.append("FieldPathConst")
            self.expr(out, depth + 1)
        else:
            self.err(f"unhandled {name}")

    def run(self):
        out = []
        while self.p < len(self.d):
            before = self.p
            out.append(f"{before:#06x}:")
            try:
                self.expr(out)
            except (RuntimeError, struct.error) as e:
                out.append(f"<<STAGNANT@{before:#x}: {e}>>")
                break
            if self.p == before:
                out.append(f"<<NO PROGRESS@{before:#x}>>")
                break
        return out


OPS_INV = {}


def find_script(payload):
    """Locate the UFunction Script TArray (i32 len + bytes) inside a cooked export payload."""
    import struct as _s
    last = payload.rfind(b"S")
    if last < 0:
        raise RuntimeError("no EndOfScript tail found")
    script_end = last + 3
    for hdr in range(last, -1, -1):
        L = _s.unpack_from("<i", payload, hdr)[0]
        if 0 < L == script_end - (hdr + 4):
            return payload[hdr + 4:hdr + 4 + L], hdr, L
    raise RuntimeError("no script length header found")


def disassemble(pkg_base, export_idx):
    pkg = uepkg.Package(pkg_base + ".uasset")
    e = pkg.exports[export_idx]
    uexp = open(pkg_base + ".uexp", "rb").read()
    start = e.serial_offset - len(pkg.data)
    payload = uexp[start:start + e.serial_size]
    code, hdr, L = find_script(payload)
    print(f"# script TArray at payload+{hdr}, {L} bytes")
    print(f"# {pkg_base.split('/')[-1]} export[{export_idx}] {pkg.name_str(e.object_name)} "
          f"uexp[{start}:{start + e.serial_size}]")
    dis = Dis(pkg, code)
    lines = dis.run()
    for l in lines:
        print(l)


if __name__ == "__main__":
    OPS_INV = {v: k for k, v in OPS.items()}
    disassemble(sys.argv[1], int(sys.argv[2]))
