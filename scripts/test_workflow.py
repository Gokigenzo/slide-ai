import importlib.util, json, tempfile, unittest
from pathlib import Path
p=Path(__file__).with_name('workflow.py')
s=importlib.util.spec_from_file_location('workflow',p);w=importlib.util.module_from_spec(s);s.loader.exec_module(w)
class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.p=Path(self.temp.name);(self.p/'source.md').write_text('# A\nPoint one\nPoint two')
  self.r={'schema_version':1,'operation':'create','project_dir':str(self.p),'source_files':[{'path':'source.md','role':'content','media_type':'md'}],'target_deck':None,'audience':'Students','language':'vi','usage':'presentation_and_self_study','slide_count':1,'duration_minutes':None,'style':'academic_minimal','output_name':'slides.pptx','research_enabled':True,'outline_path':'outline.md'}
  self.rp=self.p/'request.json';self.write(self.rp,self.r)
 def tearDown(self):self.temp.cleanup()
 def write(self,p,v):p.write_text(json.dumps(v))
 def prepare(self):
  w.run('init',self.rp)
  self.write(self.p/'source_manifest.json',{'schema_version':1,'sections':[{'section_id':'a','heading':'A','locator':'lines 1-3','source_path':'source.md','key_points':['Point one','Point two']}]})
  w.run('sources',self.p);w.run('template',self.p)
  o=self.p/'outline.md';o.write_text(o.read_text().replace('TODO: viết lời dẫn','Explain the concepts'))
  w.run('check',self.p)
 def test_strict_types(self):
  for v in ('1',True,0,-1):
   with self.subTest(v=v):
    r=dict(self.r,slide_count=v);self.write(self.rp,r)
    with self.assertRaises(w.WorkflowError):w.request(self.rp)
 def test_unknown_field(self):
  self.write(self.rp,dict(self.r,surprise=1))
  with self.assertRaises(w.WorkflowError):w.request(self.rp)
 def test_missing_file(self):
  (self.p/'source.md').unlink()
  with self.assertRaises(w.WorkflowError):w.request(self.rp)
 def test_outline_escape(self):
  self.write(self.rp,dict(self.r,outline_path='../outline.md'))
  with self.assertRaises(w.WorkflowError):w.request(self.rp)
 def test_template_not_overwritten(self):
  self.prepare();before=(self.p/'outline.md').read_bytes()
  with self.assertRaises(w.WorkflowError):w.run('template',self.p)
  self.assertEqual(before,(self.p/'outline.md').read_bytes())
 def test_gate_requires_user(self):
  self.prepare()
  with self.assertRaisesRegex(w.WorkflowError,'APPROVAL_REQUIRED'):w.run('gate',self.p)
  with self.assertRaises(w.WorkflowError):w.run('approve',self.p)
 def test_genoffice_block(self):
  self.prepare();w.run('approve',self.p,'User explicitly approved current outline')
  with self.assertRaisesRegex(w.WorkflowError,'GENOFFICE_NOT_CONNECTED'):w.run('gate',self.p)
  self.assertEqual(w.load(self.p/'state.json')['phase'],'approved')
 def test_outline_change_invalidates(self):
  self.prepare();w.run('approve',self.p,'Approved')
  with (self.p/'outline.md').open('a') as f:f.write('\nUser edit\n')
  with self.assertRaisesRegex(w.WorkflowError,'APPROVAL_REQUIRED'):w.run('gate',self.p)
  self.assertIsNone(w.load(self.p/'state.json')['approval'])
 def test_source_change_invalidates(self):
  self.prepare();w.run('approve',self.p,'Approved');(self.p/'source.md').write_text('Changed')
  with self.assertRaisesRegex(w.WorkflowError,'APPROVAL_REQUIRED'):w.run('gate',self.p)
  self.assertIsNone(w.load(self.p/'state.json')['approval'])
 def test_missing_mapping(self):
  self.prepare();o=self.p/'outline.md';o.write_text(o.read_text().replace('"a"','"b"'))
  with self.assertRaisesRegex(w.WorkflowError,'Unknown section'):w.run('check',self.p)
 def test_slide_count(self):
  self.prepare();self.r['slide_count']=2;self.write(self.rp,self.r)
  with self.assertRaisesRegex(w.WorkflowError,'count mismatch'):w.run('check',self.p)
 def test_style_missing(self):
  self.prepare();self.r['style']=None;self.write(self.rp,self.r)
  with self.assertRaisesRegex(w.WorkflowError,'Style'):w.run('approve',self.p,'Approved')
if __name__=='__main__':unittest.main()
