"""Index ASTC payloads in the existing split resource ZIP without extracting it."""
import io, json, mmap, struct, sys, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/tools'))
import rsbtool

class ResourceZip(io.RawIOBase):
    def __init__(self, apk):
        self.file = open(apk, 'rb')
        self.map = mmap.mmap(self.file.fileno(), 0, access=mmap.ACCESS_READ)
        self.parts = []
        self.pos = self.size = 0
        with zipfile.ZipFile(apk) as z:
            for x in sorted((i for i in z.infolist() if 'pvz2data.zip.00' in i.filename), key=lambda i:i.filename):
                assert x.compress_type == 0
                names, extra = struct.unpack_from('<HH', self.map, x.header_offset + 26)
                self.parts.append((self.size, x.file_size, x.header_offset + 30 + names + extra))
                self.size += x.file_size
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos
    def read(self, n=-1):
        n = min(self.size-self.pos, self.size if n < 0 else n)
        result = bytearray()
        for begin, size, physical in self.parts:
            if begin <= self.pos < begin + size:
                count = min(n, begin + size-self.pos)
                result += self.map[physical+self.pos-begin:physical+self.pos-begin+count]
                self.pos += count; n -= count
            if n == 0: break
        return bytes(result)

def texture_hash(data, w, h, fmt):
    x = 1469598103934665603
    for c in data: x = ((x ^ c) * 1099511628211) & 0xffffffffffffffff
    return x ^ w*73856093 ^ h*19349663 ^ fmt*83492791 ^ len(data)*2654435761

def build(apk, output):
    import zlib
    rows = []; formats = {}; files = []
    with zipfile.ZipFile(ResourceZip(apk)) as z:
        candidates = [x for x in z.infolist() if x.filename.endswith('.rsb.smf')]
        order = {'init.rsb.smf':0, 'uicommon.rsb.smf':1, 'dynamic.rsb.smf':2, 'egypt.rsb.smf':3}
        candidates.sort(key=lambda x:(order.get(Path(x.filename).name, 10), x.filename))
        for x in candidates:
            b = z.read(x); head = rsbtool.parse_head(b); filename = Path(x.filename).name
            files.append((filename,len(b))); before = len(rows)
            groups = rsbtool.read_rsgp_info(b, head['rsgpInfo_BeginOffset'], head['rsgp_Number'], head['rsgpInfo_EachLength'])
            for g in groups:
                start = g['fields'][0]; d = memoryview(b)[start:]
                flags = struct.unpack_from('<I',d,0x10)[0]
                part, packed, raw = struct.unpack_from('<III', d, 0x28)
                if not raw: continue
                count, first = struct.unpack_from('<II', b, g['at']+0xc4)
                ln, off = struct.unpack_from('<II',d,0x48)
                entries = rsbtool.read_string_list(d, off, ln, 1)
                part_data = None
                for name, info in entries:
                    if info[0] != 1: continue
                    _, offset, size, atlas, _, _, w, h = info
                    assert atlas < count
                    ptx = head['ptxInfo_BeginOffset']+(first+atlas)*head['ptxInfo_EachLength']
                    width,height,_,fmt = struct.unpack_from('<IIII', b, ptx)
                    assert (w,h)==(width,height)
                    formats[fmt] = formats.get(fmt,0)+1
                    astc = {161:(5,5,0x93b2),162:(6,6,0x93b4)}.get(fmt)
                    if not astc: continue
                    bx,by,glformat=astc
                    if size != ((w+bx-1)//bx)*((h+by-1)//by)*16: continue
                    if part_data is None:
                        part_data = zlib.decompress(d[part:part+packed]) if flags & 1 else d[part:part+raw]
                    payload = part_data[offset:offset+size]
                    assert len(payload)==size
                    digest = texture_hash(payload,w,h,glformat)
                    rows.append((filename,len(b),start+part,packed,raw,int(bool(flags&1)),offset,size,w,h,glformat,digest))
            print(filename, 'prefetch textures',len(rows)-before,flush=True)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    header=['// Generated from the v16r10 resource ZIP; contains metadata only.', 'static const PrefetchTexture kPrefetchTextures[] = {']
    for row in rows:
        header.append(' {'+json.dumps(row[0])+','+','.join(str(v) for v in row[1:-1])+f',UINT64_C({row[-1]})'+'},')
    header += ['};',f'static const size_t kPrefetchTextureCount = {len(rows)};']
    (output/'prefetch_index.inc').write_text('\n'.join(header)+'\n',encoding='utf8')
    (output/'prefetch-index.json').write_text(json.dumps(dict(source=str(apk),files=files,format_counts=formats,texture_count=len(rows)),indent=2),encoding='utf8')

if __name__ == '__main__': build(sys.argv[1],sys.argv[2])
