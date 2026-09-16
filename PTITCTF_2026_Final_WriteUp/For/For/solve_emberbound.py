#!/usr/bin/env python3
from pathlib import Path
import sys, struct, hashlib, hmac
MASK=0xffffffff

def u32(b): return struct.unpack('<I', b)[0]
def p32(x): return struct.pack('<I', x & MASK)
def rol32(x,n): return ((x << n) | (x >> (32-n))) & MASK

def hmac_sha256(key,msg):
    return hmac.new(key, msg, hashlib.sha256).digest()

def chacha20_block(key, nonce12, counter):
    const=b'expand 32-byte k'
    st=list(struct.unpack('<16I', const+key+p32(counter)+nonce12))
    x=st[:]
    def qr(a,b,c,d):
        x[a]=(x[a]+x[b])&MASK; x[d]=rol32(x[d]^x[a],16)
        x[c]=(x[c]+x[d])&MASK; x[b]=rol32(x[b]^x[c],12)
        x[a]=(x[a]+x[b])&MASK; x[d]=rol32(x[d]^x[a],8)
        x[c]=(x[c]+x[d])&MASK; x[b]=rol32(x[b]^x[c],7)
    for _ in range(10):
        qr(0,4,8,12); qr(1,5,9,13); qr(2,6,10,14); qr(3,7,11,15)
        qr(0,5,10,15); qr(1,6,11,12); qr(2,7,8,13); qr(3,4,9,14)
    out=[(x[i]+st[i])&MASK for i in range(16)]
    return struct.pack('<16I', *out)

def chacha20_xor(key, nonce12, counter, data):
    out=bytearray()
    c=counter
    for i in range(0,len(data),64):
        ks=chacha20_block(key, nonce12, c)
        c=(c+1)&MASK
        blk=data[i:i+64]
        out.extend(a^b for a,b in zip(blk, ks))
    return bytes(out)

def box_decrypt(key, domain, packet):
    if len(packet) <= 0x2b:
        raise ValueError('packet too short')
    nonce=packet[:12]
    msg = nonce + p32(domain) + b'E'
    enc_key=hmac_sha256(key, msg)
    auth_key=hmac_sha256(key, nonce+p32(domain)+b'A')
    tag=hmac_sha256(auth_key, packet[:-32])
    if tag != packet[-32:]:
        raise ValueError(f'tag fail domain={domain:#x} got={tag.hex()} want={packet[-32:].hex()}')
    ct=packet[12:-32]
    return chacha20_xor(enc_key, nonce, 1, ct)

def update_context(ctx36, packet, idx):
    ctx=bytearray(ctx36)
    if len(ctx)<36: ctx += b'\0'*(36-len(ctx))
    ctr=u32(ctx[32:36])
    if ctr>0x27:
        raise ValueError('bad counter')
    pt=box_decrypt(bytes(ctx[:32]), 0x57000000+ctr, packet)
    if len(pt)!=0x400:
        raise ValueError('bad update pt len')
    st=list(struct.unpack('<8I', ctx[:32]))
    seed=(ctr*0x6d2b79f5)&MASK
    r11=3
    off=0
    while r11 != 0x83:
        aidx=r11 & 7
        bidx=(r11+2)&7
        mix=(st[aidx]+seed)&MASK
        x=(rol32(mix,7) ^ st[bidx]) & MASK
        d0=(u32(pt[off:off+4]) ^ x) & MASK
        # validate fields
        if d0 & 0x00f8f800:
            raise ValueError(f'bad opcode fields at {r11} {d0:#x}')
        op=d0 & 0xff
        r9=(d0 >> 8) & 0xff
        r8=(d0 >> 16) & 0xff
        rot=(d0 >> 24) & 0xff
        if not (1 <= rot <= 0x1f):
            raise ValueError(f'bad rot {rot}')
        if r9 == r8:
            raise ValueError('same indexes')
        raw2=(rol32(x,11) ^ u32(pt[off+4:off+8])) & MASK
        imm=(raw2 ^ 0xd8715a3b) & MASK
        a=st[r9]
        b=st[r8]
        if op == 0x09:
            st[r9]=b
            st[r8]=(rol32((b+imm)&MASK,rot) ^ a) & MASK
        elif op in (0x04,0xd2):
            st[r9]=rol32(b ^ a ^ imm, rot)
        elif op in (0x99,0xf4):
            st[r9]=(((b ^ imm) * 0x9e3779b1) + rol32(a, rot)) & MASK
        elif op == 0xf1:
            st[r9]=(rol32((b+imm)&MASK, rot) ^ a) & MASK
        elif op in (0xc0,0xfb):
            tmp=(rol32(b,rot) ^ imm) & MASK
            st[r9]=(a - tmp) & MASK
        elif op == 0xad:
            st[r9]=(((imm | 1) * a) + b) & MASK
        elif op == 0x6b:
            eax=(raw2 ^ 0x278ea5c4) & MASK
            t1=imm & a
            t2=(a + b) & MASK
            eax &= b
            t2=rol32(t2,rot)
            st[r9]=(eax ^ t1 ^ t2) & MASK
        elif op in (0x2b,): # same as f1
            st[r9]=(rol32((b+imm)&MASK, rot) ^ a) & MASK
        elif op in (0x2e,): # target 66a2 same as op 0x09 block? assigns st[r9]=b, st[r8]=f
            st[r9]=b
            st[r8]=(rol32((b+imm)&MASK,rot) ^ a) & MASK
        elif op in (0x3e,): # same as ad
            st[r9]=(((imm | 1) * a) + b) & MASK
        elif op in (0x44,0x54):
            st[r9]=(rol32(b ^ imm, rot) + a) & MASK
        elif op == 0x58:
            eax=(raw2 ^ 0x278ea5c4) & MASK
            t1=imm & a
            t2=(a + b) & MASK
            eax &= b
            t2=rol32(t2,rot)
            st[r9]=(eax ^ t1 ^ t2) & MASK
        else:
            raise ValueError(f'unknown op {op:#x} at instr {r11}')
        r11 += 1
        seed=(seed+0x10204081)&MASK
        off += 8
    state_bytes=struct.pack('<8I', *st)
    newkey=hashlib.sha256(state_bytes + p32(ctr)).digest()
    return newkey + p32((ctr+1)&MASK)

def tea_stream_block(block_idx, key32):
    # sub_140004A00: key is first 16 bytes interpreted as 4 u32 only
    k=struct.unpack('<4I', key32[:16])
    a=block_idx & MASK
    v5=1905964227
    v4=0
    while True:
        v6=(v4 + k[v4 & 3]) & MASK
        v4=(v4 - 1640531527) & MASK
        a=(a + (v6 ^ (v5 + ((v5>>5) ^ ((16*v5)&MASK))))) & MASK
        v5=(v5 + (((v4 + k[(v4>>11)&3])&MASK) ^ (a + ((a>>5)^((16*a)&MASK))))) & MASK
        if v4 == ((-957401312)&MASK):
            break
    return p32(a)+p32(v5)

def fnv_check_value(data):
    h=0x811C9DC5
    last=0
    for b in data:
        last = h ^ b
        h = (last * 0x01000193) & MASK
    return last & MASK

# VM from sub_140004A90 decompiled switch
def run_vm(code):
    mem=[0]*0x510  # v77: 1296 dwords? valid 0..0x50f
    stack=[0]*128
    sp=0
    pc=0x325
    steps=0
    while True:
        steps+=1
        if steps==40000000 or pc>0x5cc:
            raise RuntimeError('VM limit')
        pos=5*pc
        op=code[pos]
        imm=(u32(code[pos+1:pos+5]) ^ ((pc*0x45D9F3B - 0x658EC39B)&MASK)) & MASK
        pc += 1
        def binop(f):
            nonlocal sp
            if sp <= 1: raise RuntimeError('stack underflow')
            sp -= 1
            stack[sp-1]=f(stack[sp-1]&MASK, stack[sp]&MASK)&MASK
        if op in (0x02,0x10,0xF7):
            def mod(a,b):
                if b==0: raise RuntimeError('mod zero')
                return a % b
            binop(mod)
        elif op in (0x04,0x3E,0x60):
            binop(lambda a,b: a & b)
        elif op in (0x08,0x1E,0x61):
            binop(lambda a,b: 1 if a==b else 0)
        elif op in (0x09,0x0F,0x1F):
            binop(lambda a,b: (a >> (b & 31)))
        elif op in (0x18,0x8F,0x99):
            pc=imm
        elif op in (0x1A,0x37,0x57):
            if imm + 16 > 0x510 or sp != 0:
                raise RuntimeError('bad output')
            return bytes(mem[imm+i] & 0xff for i in range(16))
        elif op in (0x1C,0x2E,0x66):
            binop(lambda a,b: 1 if a < b else 0)
        elif op in (0x20,0x3C,0x82):
            binop(lambda a,b: (a ^ b) + 2*(a & b)) # add without + op? == a+b
        elif op in (0x2B,0x5A,0xE8):
            binop(lambda a,b: (a - b)&MASK)
        elif op in (0x31,0x36,0x6A):
            if sp > 0x7f or imm > 0x50f: raise RuntimeError('bad load')
            stack[sp]=mem[imm]; sp+=1
        elif op in (0x39,0xEA,0xEE):
            if sp > 0x7f: raise RuntimeError('bad push')
            stack[sp]=imm; sp+=1
        elif op in (0x40,0x71,0xEB):
            if sp == 0: raise RuntimeError('stack underflow loadind')
            addr=stack[sp-1]
            if addr > 0x50f: raise RuntimeError('bad ind addr')
            stack[sp-1]=mem[addr]
        elif op in (0x42,0xD5,0xDB):
            if sp <= 1: raise RuntimeError('stack underflow storeind')
            addr=stack[sp-2]
            if addr > 0x50f: raise RuntimeError('bad store addr')
            val=stack[sp-1]
            sp-=2
            mem[addr]=val&MASK
        elif op in (0x43,0x98,0xCB):
            if sp == 0: raise RuntimeError('stack underflow jz')
            sp-=1
            if stack[sp] == 0:
                pc=imm
        elif op in (0x4A,0x92,0xCF):
            binop(lambda a,b: a ^ b)
        elif op in (0x86,0xCE,0xE6):
            binop(lambda a,b: (a*b)&MASK)
        elif op in (0x9D,0xBB,0xCD):
            if sp == 0 or imm > 0x50f: raise RuntimeError('bad store')
            sp-=1
            mem[imm]=stack[sp]&MASK
        elif op in (0xB6,0xE4,0xF9):
            binop(lambda a,b: a | b)
        elif op in (0xBC,0xD6,0xD9):
            binop(lambda a,b: (a << (b & 31))&MASK)
        else:
            raise RuntimeError(f'bad op {op:#x} pc={pc-1:#x}')

def solve(path):
    img=Path(path).read_bytes()
    ctx=bytearray(img[0x104780:0x104780+32]+b'\0\0\0\0')
    for i in range(40):
        packet=img[0xFA0A0+i*0x42C:0xFA0A0+(i+1)*0x42C]
        ctx=bytearray(update_context(ctx, packet, i))
    print('derived ctx:', bytes(ctx[:32]).hex())
    packet=img[0xF7F20:0xF7F20+0x1F61]
    key=bytes(ctx[:32])
    for i in range(8):
        pt=box_decrypt(key, 0x46000000+i, packet)
        key=pt[:32]
        packet=pt[32:]
    # final stream decrypt using sub_4A00
    plain=bytearray()
    for off in range(0, len(packet), 8):
        ks=tea_stream_block(off>>3, key)
        blk=packet[off:off+8]
        plain.extend(b^ks[j] for j,b in enumerate(blk))
    plain=bytes(plain[:7425])
    h=fnv_check_value(plain)
    print('fnv_last:', hex(h))
    out=run_vm(plain)
    print('VM output:', out.decode('ascii','replace'))

if __name__=='__main__':
    solve(sys.argv[1] if len(sys.argv)>1 else '/mnt/data/140000000.Emberbound.recovered.exe')
