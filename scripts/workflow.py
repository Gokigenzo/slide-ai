#!/usr/bin/env python3
"""Local outline workflow. No GenOffice integration or human identity verification."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from datetime import datetime, timezone
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / 'references/request.schema.json').read_text())

class WorkflowError(ValueError):
    pass

def require(ok, message):
    if not ok:
        raise WorkflowError(message)

def load(path):
    def pairs(items):
        out = {}
        for k, v in items:
            require(k not in out, f'Duplicate JSON key: {k}')
            out[k] = v
        return out
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda s: (_ for _ in ()).throw(WorkflowError('Nonfinite number')))

def validate(value, schema, at='$'):
    kinds = {'object': lambda v: type(v) is dict, 'array': lambda v: type(v) is list,
             'string': lambda v: type(v) is str, 'integer': lambda v: type(v) is int,
             'boolean': lambda v: type(v) is bool, 'null': lambda v: v is None}
    types = schema['type']
    types = [types] if isinstance(types, str) else types
    require(any(kinds[t](value) for t in types), f'{at}: invalid type')
    if 'enum' in schema:
        require(any(type(value) is type(x) and value == x for x in schema['enum']), f'{at}: invalid enum')
    if type(value) is str:
        require(len(value.strip()) >= schema.get('minLength', 0), f'{at}: empty string')
    if type(value) is int and 'minimum' in schema:
        require(value >= schema['minimum'], f'{at}: below minimum')
    if type(value) is dict:
        require(set(schema.get('required', [])) <= value.keys(), f'{at}: missing fields')
        props = schema.get('properties', {})
        if schema.get('additionalProperties') is False:
            require(value.keys() <= props.keys(), f'{at}: unknown fields')
        for k, v in value.items():
            validate(v, props[k], at + '.' + k)
    if type(value) is list:
        for i, v in enumerate(value):
            validate(v, schema['items'], f'{at}[{i}]')

def resolve_file(project, value):
    p = Path(value)
    return (p if p.is_absolute() else project / p).resolve()

def owned(project, value):
    p = resolve_file(project, value)
    require(p.is_relative_to(project), 'Output path escapes project')
    return p

def request(path):
    r = load(path)
    validate(r, SCHEMA)
    project = Path(r['project_dir']).expanduser()
    require(project.is_absolute(), 'project_dir must be absolute')
    project = project.resolve()
    require(project.is_dir(), 'project_dir must exist')
    require(os.access(project, os.W_OK), 'project_dir is not writable')
    require(Path(r['output_name']).name == r['output_name'] and r['output_name'].endswith('.pptx')
            and '\\' not in r['output_name'], 'Invalid output_name')
    out = owned(project, r['outline_path'])
    reserved = {'request.json', 'state.json', 'source_manifest.json', '.workflow.lock', 'deck_spec.json'}
    require(out.name not in reserved and out.suffix == '.md', 'Invalid outline_path')
    seen = set()
    for src in r['source_files']:
        p = resolve_file(project, src['path'])
        require(p not in seen, 'Duplicate source path')
        seen.add(p)
        require(p.is_file() and p.stat().st_size > 0, f'Source missing or empty: {p}')
        require(p.suffix.lower().lstrip('.') == src['media_type'], 'Source extension mismatch')
        with p.open('rb') as f:
            head = f.read(16)
        kind = src['media_type']
        if kind == 'pdf': require(head.startswith(b'%PDF-'), 'Invalid PDF signature')
        if kind == 'png': require(head.startswith(b'\x89PNG\r\n\x1a\n'), 'Invalid PNG signature')
        if kind in ('jpg', 'jpeg'): require(head.startswith(b'\xff\xd8'), 'Invalid JPEG signature')
        if kind in ('docx', 'pptx'):
            with zipfile.ZipFile(p) as z:
                require('[Content_Types].xml' in z.namelist(), 'Invalid Office container')
                prefix = 'word/' if kind == 'docx' else 'ppt/'
                require(any(n.startswith(prefix) for n in z.namelist()), 'Office type mismatch')
        if kind in ('txt', 'md'): p.read_text(encoding='utf-8')
    if r['operation'] in ('create', 'revise'):
        require(any(s['role'] == 'content' for s in r['source_files']), 'Content source required')
    if r['operation'] in ('revise', 'audit'):
        require(r['target_deck'] is not None, 'target_deck required')
    if r['target_deck'] is not None:
        target = resolve_file(project, r['target_deck'])
        require(target.is_file() and target.suffix.lower() == '.pptx', 'Invalid target deck')
        with zipfile.ZipFile(target) as z:
            require('ppt/presentation.xml' in z.namelist(), 'Invalid target PPTX')
    r['project_dir'] = str(project)
    return r

def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.workflow-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

@contextlib.contextmanager
def lock(project):
    with (project / '.workflow.lock').open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield

def save_state(project, state):
    state['revision'] += 1
    state['updated_at'] = datetime.now(timezone.utc).isoformat()
    atomic(project / 'state.json', state)

def invalidate(project, state):
    state['approval'] = None
    state['phase'] = 'awaiting_outline_approval'
    save_state(project, state)

def strings(xs, nonempty=False):
    require(type(xs) is list and (xs or not nonempty), 'Expected string list')
    require(all(type(x) is str and x.strip() for x in xs), 'Empty/nonstring list item')

def manifest(project, r):
    m = load(project / 'source_manifest.json')
    require(type(m) is dict and set(m) == {'schema_version', 'sections'} and type(m['schema_version']) is int
            and m['schema_version'] == 1, 'Invalid manifest')
    require(type(m['sections']) is list and m['sections'], 'Empty sections')
    content = {resolve_file(project, s['path']) for s in r['source_files'] if s['role'] == 'content'}
    ids, covered = [], set()
    for s in m['sections']:
        require(type(s) is dict and set(s) == {'section_id','heading','locator','source_path','key_points'}, 'Invalid section')
        for key in ('section_id','heading','locator','source_path'):
            require(type(s[key]) is str and s[key].strip(), 'Invalid section string')
        strings(s['key_points'], True)
        p = resolve_file(project, s['source_path'])
        require(p in content, 'Section points outside content sources')
        covered.add(p); ids.append(s['section_id'])
    require(len(ids) == len(set(ids)), 'Duplicate section IDs')
    require(covered == content, 'Unmapped content source')
    return m

def slides(project, r, m):
    text = owned(project, r['outline_path']).read_text(encoding='utf-8')
    blocks = re.findall(r'^```slide-spec\s*\n(.*?)^```\s*$', text, re.M | re.S)
    require(blocks, 'No slide-spec blocks')
    specs = []
    fields = {'slide_id','kind','section_ids','title','main_points','supporting_points','examples','visuals','speaker_notes'}
    order = [s['section_id'] for s in m['sections']]
    first = []; ids = []
    for block in blocks:
        # Reuse strict JSON parser, including duplicate-key checks, without temp files.
        def pairs(items):
            d = {}
            for k,v in items:
                require(k not in d, 'Duplicate slide JSON key'); d[k] = v
            return d
        s = json.loads(block, object_pairs_hook=pairs)
        require(type(s) is dict and set(s) == fields, 'Invalid slide fields')
        for k in ('slide_id','title','speaker_notes'):
            require(type(s[k]) is str and s[k].strip() and 'TODO' not in s[k], f'Invalid {k}')
        require(s['kind'] in ('knowledge','cover','example','diagram'), 'Invalid slide kind')
        for k in ('section_ids','main_points','supporting_points','visuals'): strings(s[k])
        require(len(s['section_ids']) == len(set(s['section_ids'])), 'Duplicate section on slide')
        require(s['kind'] == 'cover' or s['section_ids'], 'Missing section mapping')
        for sid in s['section_ids']:
            require(sid in order, 'Unknown section_id')
            if sid not in first: first.append(sid)
        require(type(s['examples']) is list, 'Invalid examples')
        for e in s['examples']:
            require(type(e) is dict and set(e) == {'origin','locator','text'}, 'Invalid example')
            require(e['origin'] in ('source','research'), 'Invalid example origin')
            require(all(type(e[k]) is str and e[k].strip() for k in e), 'Invalid example strings')
            require(e['origin'] != 'research' or r['research_enabled'], 'Research disabled')
        n = len(s['main_points'])
        require(2 <= n <= 3 if s['kind'] == 'knowledge' else n <= 3, 'Main point count invalid')
        require(n or s['examples'] or s['visuals'], 'Empty slide')
        specs.append(s); ids.append(s['slide_id'])
    require(len(ids) == len(set(ids)), 'Duplicate slide IDs')
    require(first == order, 'Missing or reordered source sections')
    require(r['slide_count'] is None or len(specs) == r['slide_count'], 'Slide count mismatch')
    return specs

def fingerprint(project, r):
    h = hashlib.sha256()
    def add(name, data):
        h.update(name.encode()); h.update(b'\0'); h.update(len(data).to_bytes(8,'big')); h.update(data)
    add('request', json.dumps(r, sort_keys=True, ensure_ascii=False).encode())
    for s in r['source_files']:
        p = resolve_file(project, s['path']); add(str(p), p.read_bytes())
    if r['target_deck']:
        p = resolve_file(project, r['target_deck']); add('target:'+str(p), p.read_bytes())
    for name in ('source_manifest.json', r['outline_path']):
        add(name, owned(project, name).read_bytes())
    return h.hexdigest()

def run(command, path, evidence=None):
    if command in ('validate','init'):
        r = request(path); project = Path(r['project_dir'])
        if command == 'validate': return {'status':'valid','request':r}
        with lock(project):
            require(not (project/'state.json').exists(), 'Project already initialized')
            rp = project/'request.json'
            if rp.exists(): require(request(rp) == r, 'Existing request differs')
            else: atomic(rp, r)
            atomic(project/'state.json', {'schema_version':1,'revision':0,'phase':'intake','approval':None})
        return {'status':'initialized','project_dir':str(project)}
    project = Path(path).resolve()
    require(project.is_dir(), 'Project missing')
    with lock(project):
        state = load(project/'state.json')
        try:
            r = request(project/'request.json')
            if command == 'refresh':
                invalidate(project,state); return {'status':'approval_invalidated'}
            m = manifest(project,r)
            if command == 'sources':
                state['phase']='sources_validated';state['approval']=None;save_state(project,state)
                return {'status':'sources_validated','sections':len(m['sections'])}
            if command == 'template':
                out = owned(project,r['outline_path'])
                require(not out.exists(), 'Outline exists; will not overwrite user edits')
                scaffold = '# Dàn ý để chỉnh sửa trong VS Code\n\nSửa JSON trong từng block; lưu file rồi xác nhận chốt riêng.\n'
                for i, section in enumerate(m['sections'],1):
                    s={'slide_id':f'slide-{i:03d}','kind':'knowledge','section_ids':[section['section_id']],
                       'title':section['heading'],'main_points':section['key_points'][:3],
                       'supporting_points':[],'examples':[],'visuals':[], 'speaker_notes':'TODO: viết lời dẫn'}
                    scaffold += '\n```slide-spec\n'+json.dumps(s,ensure_ascii=False,indent=2)+'\n```\n'
                with out.open('x',encoding='utf-8') as f: f.write(scaffold)
                state['phase']='awaiting_outline_approval';state['approval']=None;save_state(project,state)
                return {'status':'template_created','path':str(out),'warning':'Draft scaffold; complete and validate before review'}
            specs = slides(project,r,m)
            fp = fingerprint(project,r)
            if state['approval'] and state['approval']['fingerprint'] != fp:
                invalidate(project,state)
            if command == 'check':
                atomic(project/'deck_spec.json',{'schema_version':1,'slides':specs})
                if not state['approval']:
                    state['phase']='awaiting_outline_approval';save_state(project,state)
                return {'status':'structurally_valid','slides':len(specs),'semantic_review_required':True}
            require(r['style'] is not None and r['audience'] is not None, 'Style and audience must be selected')
            if command == 'approve':
                require(type(evidence) is str and evidence.strip(), 'Explicit user approval evidence required')
                state['approval']={'fingerprint':fp,'evidence':evidence,'at':datetime.now(timezone.utc).isoformat()}
                state['phase']='approved';save_state(project,state)
                return {'status':'approved','fingerprint':fp,'human_identity_verified':False}
            require(command == 'gate', 'Unknown command')
            require(state['approval'] is not None, 'OUTLINE_APPROVAL_REQUIRED')
            raise WorkflowError('GENOFFICE_NOT_CONNECTED: approval valid; production unavailable in v0.1')
        except (WorkflowError, OSError, ValueError, zipfile.BadZipFile):
            if state.get('approval') and command != 'gate': invalidate(project,state)
            elif state.get('approval') and command == 'gate':
                # Retain valid approval only for the explicit missing-adapter outcome.
                try:
                    current=fingerprint(project,request(project/'request.json'))
                    if current != state['approval']['fingerprint']: invalidate(project,state)
                except (OSError,ValueError,zipfile.BadZipFile): invalidate(project,state)
            raise

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['validate','init','sources','template','refresh','check','approve','gate'])
    parser.add_argument('path');parser.add_argument('--evidence')
    args=parser.parse_args()
    try:
        result=run(args.command,args.path,args.evidence)
        print(json.dumps(result,ensure_ascii=False));return 0
    except (WorkflowError,OSError,ValueError,zipfile.BadZipFile,KeyError,TypeError) as e:
        print(json.dumps({'status':'error','message':str(e)},ensure_ascii=False));return 2
if __name__ == '__main__': sys.exit(main())
