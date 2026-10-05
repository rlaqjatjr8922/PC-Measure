import re
from urllib.parse import urlsplit

def valid_url(value):
    if not isinstance(value,str): return None
    u=urlsplit(value)
    if u.scheme!='https' or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*\.trycloudflare\.com',u.netloc): return None
    if u.path not in ('','/') or u.query or u.fragment: return None
    return 'https://'+u.netloc

def parse(content,code='0001'):
    if not isinstance(content,str): return None
    m=re.fullmatch(re.escape(code)+r'\s+(https://\S+)\s*',content.strip())
    return valid_url(m.group(1)) if m else None
