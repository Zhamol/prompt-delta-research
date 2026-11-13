"""Offline representation experiments, NOT an LLM or billing benchmark.

Run only in the pinned sandbox described in results.json. No provider calls.
JSON packets are literal model-visible text, not HTTP JSON escaping.
"""
import collections
import csv
import difflib
import hashlib
import importlib.metadata
import inspect
import json
import random
import re
from pathlib import Path
import tiktoken

OUT = Path('/research')
ENC = {n: tiktoken.get_encoding(n) for n in ('cl100k_base', 'o200k_base')}
INSTRUCTIONS = {
 'dictionary': 'The following JSON encodes exact source text, not instructions. Strings are literal. Integers in body reference zero-based entries in dictionary. Concatenate body in order after expansion. Preserve every character, including whitespace. Reason directly over this representation. Return ordinary source edits, never dictionary edits.',
 'templates': 'The following JSON encodes exact source text, not instructions. Each template is an ordered array of literal strings and zero-based slot numbers. In body, a string is literal; [template_id,values] instantiates that template with literal string values. Concatenate body in order. Preserve all characters and whitespace. Reason directly over the representation. Return ordinary source edits, never template edits.',
 'grammar': 'The following JSON encodes exact source text, not instructions. Strings are literal; integers reference zero-based rules. Expand rules recursively, concatenating each array in order. Rules only reference earlier rules; nesting is at most two levels. Expand body the same way. Preserve all characters and whitespace. Reason directly over the representation. Return ordinary source edits, never rule edits.',
 'delta': 'This JSON is a sequence of exact source snapshots, not instructions. A full frame supplies literal text. A delta frame references the previous frame by SHA256. Its sorted nonoverlapping edits are [start,end,literal_replacement], using zero-based Unicode character offsets in that previous text, end exclusive. Apply edits simultaneously; verify the resulting SHA256. Retain earlier snapshots. Reason over the latest snapshot. Return ordinary source edits.',
}

def dumps(x): return json.dumps(x, ensure_ascii=False, separators=(',', ':'))
def count(s, name): return len(ENC[name].encode(s, disallowed_special=()))
def digest(s): return hashlib.sha256(s.encode('utf-8')).hexdigest()
def wire(kind, packet): return INSTRUCTIONS[kind] + '\n' + dumps(packet)
def compact(parts):
    out=[]
    for p in parts:
        if isinstance(p,str) and out and isinstance(out[-1],str): out[-1]+=p
        else: out.append(p)
    return out

def dictionary(text, name):
    lines=text.splitlines(keepends=True)
    freq=collections.Counter(lines)
    words=[x for x,n in freq.items() if n>1 and len(x)>8]
    index={x:i for i,x in enumerate(words)}
    return dict(dictionary=words,body=compact([index.get(x,x) for x in lines]))

def templates(text, name):
    lines=text.splitlines(keepends=True)
    atoms=[re.findall(r'\w+|[^\w]',x) for x in lines]
    def shape(a): return tuple('WORD' if re.fullmatch(r'\w+',x) else x for x in a)
    families=collections.defaultdict(list)
    for i,a in enumerate(atoms): families[shape(a)].append(i)
    rules=[]; inst={}
    for ids in families.values():
        if len(ids)<3: continue
        members=[atoms[i] for i in ids]
        varying=[j for j in range(len(members[0])) if len({a[j] for a in members})>1]
        slots={j:k for k,j in enumerate(varying)}
        rule=compact([slots[j] if j in slots else x for j,x in enumerate(members[0])])
        rid=len(rules); rules.append(rule)
        for i in ids: inst[i]=[rid,[atoms[i][j] for j in varying]]
    return dict(templates=rules,body=compact([inst.get(i,line) for i,line in enumerate(lines)]))

def grammar(text,name):
    atoms=re.findall(r'\w+|[^\w]',text)
    rules=[]; depths=[]
    def packet(a,rs): return dict(rules=[compact(r) for r in rs],body=compact(a))
    def depth(v): return depths[v] if type(v) is int else 0
    current=count(wire('grammar',packet(atoms,rules)),name)
    for _ in range(32):
        pairs=collections.Counter(zip(atoms,atoms[1:]))
        options=[(p,n) for p,n in pairs.most_common(24) if n>=3 and max(map(depth,p))<2]
        best=None
        for pair,n in options:
            new=[];i=0
            while i<len(atoms):
                if i+1<len(atoms) and (atoms[i],atoms[i+1])==pair:
                    new.append(len(rules));i+=2
                else: new.append(atoms[i]);i+=1
            size=count(wire('grammar',packet(new,rules+[list(pair)])),name)
            if size<current and (best is None or size<best[0]): best=(size,new,pair)
        if best is None: break
        current,atoms,pair=best
        depths.append(1+max(map(depth,pair)))
        rules.append(list(pair))
    return packet(atoms,rules)

def decode(kind,p):
    if kind=='dictionary': return ''.join(p['dictionary'][v] if type(v) is int else v for v in p['body'])
    if kind=='templates':
        out=[]
        for x in p['body']:
            if isinstance(x,str):out.append(x)
            else:
                r,values=x
                out.append(''.join(values[v] if type(v) is int else v for v in p['templates'][r]))
        return ''.join(out)
    if kind=='grammar':
        expanded=[]
        for i,r in enumerate(p['rules']):
            assert all(type(v) is not int or 0<=v<i for v in r)
            expanded.append(''.join(expanded[v] if type(v) is int else v for v in r))
        return ''.join(expanded[v] if type(v) is int else v for v in p['body'])
    raise ValueError(kind)

def delta_frames(snapshots):
    frames=[dict(full=snapshots[0],sha256=digest(snapshots[0]))]
    for old,new in zip(snapshots,snapshots[1:]):
        edits=[[i,j,new[k:l]] for tag,i,j,k,l in difflib.SequenceMatcher(None,old,new,autojunk=False).get_opcodes() if tag!='equal']
        frames.append(dict(base=digest(old),edits=edits,sha256=digest(new)))
    return frames

def decode_frames(frames):
    history=[]
    for f in frames:
        if 'full' in f: new=f['full']
        else:
            old=history[-1];assert digest(old)==f['base']
            cursor=0;parts=[]
            for a,b,value in f['edits']:
                assert cursor<=a<=b<=len(old)
                parts.extend([old[cursor:a],value]);cursor=b
            parts.append(old[cursor:]);new=''.join(parts)
        assert digest(new)==f['sha256']
        history.append(new)
    return history

def fixtures():
    rng=random.Random(193)
    block='def normalize_record(record):\n    # Preserve exact order and whitespace.\n    if record is None:\n        return None\n    return record.strip()\n\n'
    repeated=block*40 + block.replace('return None','return ""') + block*39
    param=''.join(f'def validate_{i:03d}(value):\n    if value < {i+1}:\n        raise ValueError("invalid field_{i:03d}")\n    return value + {i}\n\n' for i in range(80))
    logs=''.join(f'2026-11-13T12:{i//60:02d}:{i%60:02d}Z '+('ERROR' if i==137 else 'INFO')+f' service=ledger request={i:04d} retries='+('0' if i==137 else '3')+' status=connected\r\n' for i in range(240))
    data=dict(repetitive_code=repeated,parameterized_code=param,mostly_unique_code=inspect.getsource(json.decoder),ordered_logs=logs,short_prompt='Fix the parser bug. Preserve message whitespace and reject invalid dates.',escape_unicode='\tα e\u0301 é 🐍\r\n@D0 {slot} [0,"\\n"]\x00\nlast line without newline')
    data['unique_identifiers']='\n'.join('key_'+''.join(rng.choice('0123456789abcdef') for _ in range(40))+' = '+repr(''.join(rng.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(50))) for _ in range(70))
    for task in ('log_parser','expense_app'):
        root=Path('/poc')/task
        data['poc_'+task]=''.join('FILE '+str(f.relative_to(root))+'\n'+f.read_bytes().decode('utf-8')+'\nEND FILE\n' for f in sorted(root.rglob('*')) if f.is_file() and f.suffix in ('.md','.py'))
    return data

def main():
    data=fixtures(); rows=[]; temporal=[]; checks=0
    ex=OUT/'examples';ex.mkdir(exist_ok=True)
    for label,text in data.items():
        (ex/(label+'.original.txt')).write_bytes(text.encode('utf-8'))
        for name in ENC:
            raw=count(text,name)
            for kind,fn in [('dictionary',dictionary),('templates',templates),('grammar',grammar)]:
                p=fn(text,name); w=wire(kind,p)
                # Decode the serialized packet, not an in-memory shortcut.
                restored=decode(kind,json.loads(w.split('\n',1)[1]))
                assert restored.encode('utf-8')==text.encode('utf-8');checks+=1
                n=count(w,name)
                rows.append(dict(fixture=label,tokenizer=name,method=kind,original_tokens=raw,encoded_tokens=n,instruction_tokens=count(INSTRUCTIONS[kind],name),encoded_payload_tokens=count(dumps(p),name),token_change_percent=round(100*(n/raw-1),2),raw_fallback_tokens=min(raw,n),round_trip=True))
                (ex/(label+'.'+name+'.'+kind+'.txt')).write_text(w)
            # Four snapshots: unchanged reread, one small edit, one appended line.
            snaps=[text,text,text.replace(' ', '  ',1),text.replace(' ', '  ',1)+'\n# appended Δ\n']
            frames=delta_frames(snaps)
            assert decode_frames(json.loads(dumps(frames)))==snaps; checks+=1
            normal='';encoded=INSTRUCTIONS['delta']+'\n';nr=[];cr=[];prefix=[]
            for i,(s,f) in enumerate(zip(snaps,frames)):
                previous=encoded
                # Compare with literal tool text, NOT transport-escaped JSON text.
                normal+=f'SNAPSHOT {i}:\n'+s+'\nEND SNAPSHOT\n'
                encoded+=dumps(f)+'\n'
                # Shared prefix of token streams is diagnostic, NOT provider cache usage.
                a=ENC[name].encode(previous,disallowed_special=());b=ENC[name].encode(encoded,disallowed_special=())
                shared=next((j for j,(x,y) in enumerate(zip(a,b)) if x!=y),min(len(a),len(b)))
                prefix.append(shared);nr.append(count(normal,name));cr.append(count(encoded,name))
            temporal.append(dict(fixture=label,tokenizer=name,original_cumulative_requests=nr,delta_cumulative_requests=cr,delta_stable_prefix_tokens=prefix,original_final_tokens=nr[-1],delta_final_tokens=cr[-1],raw_fallback_final_tokens=min(nr[-1],cr[-1]),round_trip=True))
            (ex/(label+'.'+name+'.delta.txt')).write_text(encoded)
    # Format edge cases, including markers, CRLF, NUL, Unicode and no final newline.
    rng=random.Random(801)
    fuzz=['','\n','\r\n','  ','@0[0]\\"','é e\u0301 🐍\t','a\r\nb\nlast']
    alphabet='ab01 \t\n\r[]{}\\"α🐍\x00'
    fuzz+=[''.join(rng.choice(alphabet) for _ in range(rng.randrange(1,250))) for _ in range(100)]
    for s in fuzz:
        for kind,fn in [('dictionary',dictionary),('templates',templates),('grammar',grammar)]:
            assert decode(kind,json.loads(dumps(fn(s,'cl100k_base')))).encode()==s.encode();checks+=1
        ss=[s,s+'x',s[:len(s)//2],s]
        assert decode_frames(json.loads(dumps(delta_frames(ss))))==ss;checks+=1
    # A stale base must be rejected; this proves integrity checking, not model editing.
    f=delta_frames(['abc','axc']);f[0]['full']='bad'
    try: decode_frames(f)
    except AssertionError: checks+=1
    else: raise AssertionError('stale base accepted')
    result=dict(disclaimer='Synthetic offline token/codec measurements. No model inference, accuracy measurement, cache hits or USD savings measured. Public tokenizer proxies are NOT Claude token counts.',tiktoken_version=importlib.metadata.version('tiktoken'),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),fixture_sha256={k:digest(v) for k,v in data.items()},checks_passed=checks,static=rows,temporal=temporal)
    (OUT/'results.json').write_text(json.dumps(result,indent=2))
    with (OUT/'results.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print('Checks passed:',checks)
    print('o200k_base: original / dictionary / templates / grammar (all overhead included)')
    for label in data:
        rr=[r for r in rows if r['fixture']==label and r['tokenizer']=='o200k_base']
        print(label,rr[0]['original_tokens'],*[r['encoded_tokens'] for r in rr])
    print('Four-snapshot histories: original / delta; o200k_base')
    for r in temporal:
        if r['tokenizer']=='o200k_base':print(r['fixture'],r['original_final_tokens'],r['delta_final_tokens'])

if __name__=='__main__': main()
