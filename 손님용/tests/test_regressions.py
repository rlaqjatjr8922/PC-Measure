import unittest
from io import BytesIO
from unittest.mock import patch, MagicMock
from pathlib import Path
import test_features
from test_features import load
from PIL import Image
import api_config
class Regression(unittest.TestCase):
    setUp = test_features.Features.setUp
    request = test_features.Features.request
    def test_all_route_validation(self):
        for g,schema in vars(api_config).items():
            if g.startswith('_') or not isinstance(schema,dict): continue
            for f,s in schema.items():
                path=f'/{g}/{f}'
                with self.subTest(path=path,case='unknown_argument'):
                    self.request(path,{'__unexpected__':1},400)
                if 'mode' in s:
                    with self.subTest(path=path,case='invalid_mode'):
                        self.request(path,{'mode':'__invalid__'},400)
                    variants=s['mode'].items()
                else: variants=[(None,s)]
                for mode,args in variants:
                    if any(v is None for v in args.values()):
                        with self.subTest(path=path,mode=mode,case='missing_required'):
                            self.request(path,{'mode':mode} if mode else {},400)
    def test_saved_image_comparisons(self):
        shot=load('screen','screenshot')
        ids=[]
        for color,area in [('white',{'left':0,'top':0,'width':4,'height':3}),('black',{'left':0,'top':0,'width':4,'height':3}),('white',{'left':1,'top':0,'width':4,'height':3})]:
            stream=BytesIO(); Image.new('RGB',(4,3),color).save(stream,format='PNG')
            with patch.object(shot,'_capture',return_value=(stream.getvalue(),area)):
                ids.append(shot.run(mode='save',target={})['id'])
        for feature in ('diff','assert_changed','assert_unchanged'):
            for after,changed,tolerance in [(ids[0],False,0),(ids[1],True,0),(ids[1],False,255)]:
                result=self.request('/verify/'+feature,{'mode':'saved','before_id':ids[0],'after_id':after,'tolerance':tolerance})
                self.assertEqual(result['changed'],changed)
                if feature!='diff': self.assertEqual(result['passed'],changed if feature=='assert_changed' else not changed)
            self.request('/verify/'+feature,{'mode':'saved','before_id':ids[0],'after_id':ids[2]},400)
    def test_recursive_directory_copy(self):
        self.request('/files/create',{'path':'temp:/folder','kind':'directory'})
        self.request('/files/create',{'path':'temp:/folder/a.txt','content':{'text':'test'}})
        self.request('/files/copy',{'path':'temp:/folder','destination':'temp:/copied','options':{'recursive':True}})
        self.assertEqual(self.request('/files/read',{'path':'temp:/copied/a.txt'})['content'],'test')
    def test_recursive_directory_delete(self):
        self.request('/files/create',{'path':'temp:/folder','kind':'directory'})
        self.request('/files/create',{'path':'temp:/folder/a.txt','content':{'text':'test'}})
        self.request('/files/delete',{'path':'temp:/folder','options':{'recursive':True}})
        self.request('/files/info',{'path':'temp:/folder'},404)
    def test_recursive_directory_move(self):
        self.request('/files/create',{'path':'temp:/folder','kind':'directory'})
        self.request('/files/create',{'path':'temp:/folder/a.txt','content':{'text':'test'}})
        self.request('/files/move',{'path':'temp:/folder','destination':'temp:/moved','options':{'recursive':True}})
        self.assertEqual(self.request('/files/read',{'path':'temp:/moved/a.txt'})['content'],'test')

    def test_directory_rename(self):
        self.request('/files/create',{'path':'temp:/folder','kind':'directory'})
        self.request('/files/create',{'path':'temp:/folder/a.txt','content':{'text':'test'}})
        self.request('/files/rename',{'path':'temp:/folder','name':'renamed'})
        self.assertEqual(self.request('/files/read',{'path':'temp:/renamed/a.txt'})['content'],'test')

    def test_click_duration_and_buttons(self):
        for feature,count,button in [('click',1,'left'),('double_click',2,'left'),('right_click',1,'right')]:
            with self.subTest(feature=feature):
                module=load('mouse',feature)
                gui=MagicMock(); gui.position.return_value=(10,20)
                with patch.object(module,'_gui',return_value=gui), patch.object(module,'_move',return_value={'x':10,'y':20}) as move:
                    module.run(x=10,y=20,options={'duration':.25,'interval':0})
                    move.assert_called_once_with(10,20,.25)
                    self.assertEqual(gui.mouseDown.call_count,count)
                    gui.mouseDown.assert_called_with(button=button)

    def test_file_conflict_and_binary(self):
        import hashlib
        self.request('/files/create',{'path':'temp:/binary','content':{'base64':'AP8='}})
        self.assertEqual(self.request('/files/read',{'path':'temp:/binary','options':{'encoding':'base64'}})['content'],'AP8=')
        self.request('/files/edit',{'path':'temp:/binary','options':{'expected_hash':'wrong'},'content':{'text':'bad'}},409)
        self.request('/files/edit',{'path':'temp:/binary','options':{'expected_hash':hashlib.sha256(bytes([0,255])).hexdigest()},'content':{'text':'ok'}})
        self.assertEqual(self.request('/files/read',{'path':'temp:/binary'})['content'],'ok')

    def test_wait_stable_timeout_and_stop(self):
        import config
        from fastapi import HTTPException
        module=load('verify','wait_stable')
        stream=BytesIO(); Image.new('RGB',(4,3),'white').save(stream,format='PNG')
        with patch.object(module,'_capture',return_value=(stream.getvalue(),{'left':0,'top':0,'width':4,'height':3})):
            self.assertFalse(module.run(target={},options={'interval':.02,'stable_for':1,'max_wait':.04})['stable'])
            config.stop_event.set()
            try:
                with self.assertRaises(HTTPException) as exc:
                    module.run(target={},options={'interval':.02,'max_wait':.04})
                self.assertEqual(exc.exception.status_code,409)
            finally: config.stop_event.clear()

