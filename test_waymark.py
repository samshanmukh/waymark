import unittest
from unittest.mock import patch
import server as s

class Routes(unittest.TestCase):
 def setUp(self):s.operate('reset',{})
 def nodes(self):
  s.STATE['nodes']=[{'id':'n1','name':'Atrium','signs':['ATRIUM']},{'id':'n2','name':'East lifts','signs':['LIFTS','EAST WING']},{'id':'n3','name':'Lounge','signs':['LOUNGE']}]
  s.STATE['edges']=[{'id':'a','a':'n1','b':'n2','blocked':False},{'id':'b','a':'n2','b':'n3','blocked':False}]
  s.STATE.update(current='n1',goal='n3');s.reroute()
 def test_only_taught_paths(self):
  self.nodes();self.assertEqual(s.STATE['route'],['n1','n2','n3'])
  s.operate('block',{'id':'a'});self.assertEqual(s.STATE['route'],[])
 def test_reverse_path(self):
  self.nodes();self.assertEqual(s.route('n3','n1',s.STATE['nodes'],s.STATE['edges']),['n3','n2','n1'])
 def test_alternative_path(self):
  self.nodes();s.STATE['edges'] += [{'id':'c','a':'n1','b':'n3','blocked':False}]
  s.operate('block',{'id':'a'});self.assertEqual(s.STATE['route'],['n1','n3'])
 def test_confidence_cannot_bypass_signs(self):
  self.nodes();self.assertIsNone(s.accept_match({'match_id':'n2','confidence':1,'signs':[]},s.STATE['nodes'],'n2'))
 def test_wrong_node_cannot_advance(self):
  self.nodes();self.assertIsNone(s.accept_match({'match_id':'n3','confidence':1,'signs':['LOUNGE']},s.STATE['nodes'],'n2'))
 def test_unknown_node_rejected(self):
  self.nodes();self.assertIsNone(s.accept_match({'match_id':'invented','confidence':1,'signs':['LIFTS']},s.STATE['nodes']))
 def test_repeated_image_cannot_advance(self):
  self.nodes();obs={'name':'Lifts','signs':['LIFTS','EAST WING'],'cues':[],'match_id':'n2','confidence':.98,'reason':'East sign'}
  with patch.object(s,'infer',side_effect=lambda *a:dict(obs)):
   s.operate('verify',{'fixture':'lifts'});self.assertEqual(s.STATE['last']['decision'],'confirm');self.assertEqual(s.STATE['current'],'n1')
   s.operate('verify',{'fixture':'lifts'});self.assertEqual(s.STATE['current'],'n1')
   s.operate('verify',{'fixture':'lifts2'});self.assertEqual(s.STATE['current'],'n2')
 def test_ambiguous_view_clears_confirmation(self):
  self.nodes();good={'match_id':'n2','confidence':.98,'signs':['LIFTS'],'reason':'Sign'}
  with patch.object(s,'infer',side_effect=[dict(good),{'match_id':None,'confidence':.2,'signs':[],'reason':'Unreadable'}]):
   s.operate('verify',{'fixture':'lifts'});s.operate('verify',{'fixture':'unclear'})
  self.assertIsNone(s.STATE['pending']);self.assertEqual(s.STATE['current'],'n1')
 def test_malformed_json_fails_closed(self):
  with self.assertRaises(ValueError):s.json_output('{"match_id":')
 def test_fixture_path_traversal_rejected(self):
  with self.assertRaises(ValueError):s.get_image({'fixture':'../.env'})
 def test_upload_type_rejected(self):
  with self.assertRaises(ValueError):s.get_image({'image':'data:image/png;base64,aGVsbG8='})
if __name__=='__main__':unittest.main()
