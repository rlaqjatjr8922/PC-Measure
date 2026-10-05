from copy import deepcopy
from jsonschema import Draft202012Validator
from remote.client import request,GROUPS
REMOTE_GROUPS=frozenset(GROUPS)
TEXT={'type':'string','minLength':1,'pattern':r'\S'}
def field(key,default):
    if key in ('x','y','start_x','start_y','end_x','end_y','amount','hwnd','width','height','monitor','window','clicks','tolerance','limit','timeout'): s={'type':'integer'}
    elif key in ('interval','duration'): s={'type':'number','minimum':0}
    elif key=='keys': s={'oneOf':[TEXT,{'type':'array','items':TEXT,'minItems':1}]}
    elif key=='content': s={'type':'object','oneOf':[{'required':['text']},{'required':['base64']}],'properties':{'text':{'type':'string'},'base64':{'type':'string'}},'additionalProperties':False}
    elif key in ('data','target','options') and not isinstance(default,list): s={'type':'object'}
    elif isinstance(default,list): s={'type':'array','items':TEXT}
    else: s=deepcopy(TEXT)
    if key in ('hwnd','width','height','clicks'): s['minimum']=1
    if key=='monitor': s['minimum']=0
    if key=='button': s['enum']=['left','right','middle']
    if key=='scope': s['enum']=['query','none','program','all']
    if key=='privilege': s['enum']=['normal','admin']
    if key=='screenshot': s={'enum':['query',True,False]}
    if key=='condition': s['enum']=['screen_changed','file_exists','file_changed','window_exists']
    if key=='kind': s['enum']=['file','directory']
    if default is not ...: s['default']=deepcopy(default)
    return s

def flat(params,mode=None):
    props={k:field(k,v) for k,v in params.items()}; required=[k for k,v in params.items() if v is ...]
    if mode is not None: props['mode']={'type':'string','const':mode}; required.append('mode')
    return dict(type='object',properties=props,required=required,additionalProperties=False)

def schema(params,path):
    if 'mode' not in params: return flat(params)
    branches=[flat(p,m) for m,p in params['mode'].items()]
    props={k:v for b in branches for k,v in b['properties'].items() if k!='mode'}
    props['mode']={'type':'string','enum':list(params['mode'])}
    return dict(type='object',properties=props,required=['mode'],oneOf=branches)

def validated(params,data,path):
    if not isinstance(data,dict): raise ValueError('reason: JSON 객체가 필요합니다.')
    if 'mode' in params:
        mode=data.get('mode')
        if not isinstance(mode,str) or mode not in params['mode']: raise ValueError('reason: 올바른 mode가 필요합니다: '+', '.join(params['mode']))
        selected=params['mode'][mode]; spec=flat(selected,mode)
    else: selected=params; spec=flat(params)
    errors=list(Draft202012Validator(spec).iter_errors(data))
    if errors: raise ValueError('reason: '+'.'.join(map(str,errors[0].path))+': '+errors[0].message)
    result={k:deepcopy(v) for k,v in selected.items() if v is not ...}; result.update(data)
    return result

def invoke(path,parameters):
    result=request(path,parameters)
    return result.get('response',result)
