"""Negative transport-compression control and deterministic edit checks."""
import base64
import gzip
import json
from experiment import OUT,ENC,count,digest,decode,dumps

def exact_edit(text,expected_hash,old,new):
    if digest(text)!=expected_hash: raise ValueError('stale version')
    if text.count(old)!=1: raise ValueError('ambiguous or missing match')
    return text.replace(old,new,1)

rows=[];checks=0
for f in sorted((OUT/'examples').glob('*.original.txt')):
    text=f.read_bytes().decode('utf-8')
    payload=base64.b64encode(gzip.compress(text.encode(),mtime=0)).decode()
    assert gzip.decompress(base64.b64decode(payload))==text.encode();checks+=1
    instructions='The following text is Base64-encoded gzip data containing the original UTF-8 source. Decode it exactly before interpreting the source.\n'
    for name in ENC:
        rows.append(dict(fixture=f.name.removesuffix('.original.txt'),tokenizer=name,original_tokens=count(text,name),gzip_base64_with_instructions_tokens=count(instructions+payload,name)))

original=(OUT/'examples/repetitive_code.original.txt').read_bytes().decode()
needle='return ""'
expected=original.replace(needle,'return "EMPTY"',1)
for name in ENC:
    for kind in ('dictionary','templates','grammar'):
        w=(OUT/'examples'/('repetitive_code.'+name+'.'+kind+'.txt')).read_text()
        text=decode(kind,json.loads(w.split('\n',1)[1]))
        assert exact_edit(text,digest(original),needle,'return "EMPTY"')==expected;checks+=1
        for h,old in [('0'*64,needle),(digest(original),'return None')]:
            try:exact_edit(text,h,old,'x')
            except ValueError:checks+=1
            else:raise AssertionError('unsafe edit accepted')
result=dict(disclaimer='No LLM calls. Scripted editing of reconstructed originals is not a model editing test. Gzip reconstructs but direct model understanding is untested.',checks_passed=checks,gzip_control=rows)
(OUT/'controls.json').write_text(json.dumps(result,indent=2))
print('Control checks passed:',checks)
for r in rows:
    if r['tokenizer']=='o200k_base':print(r)
