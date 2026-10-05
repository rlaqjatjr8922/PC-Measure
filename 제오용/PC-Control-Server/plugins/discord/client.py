import os
import httpx

def setting(name):
    import config
    return str(getattr(config,name,''))

def messages(before=None):
    token=setting('DISCORD_BOT_TOKEN')
    channel=setting('DISCORD_CHANNEL_ID')
    if not token or not channel.isdigit():
        raise RuntimeError('DISCORD_BOT_TOKEN / DISCORD_CHANNEL_ID config.py 설정이 필요합니다.')
    params={'limit':100}
    if before: params['before']=before
    try:
        with httpx.Client(timeout=10,follow_redirects=False) as client:
            response=client.get('https://discord.com/api/v10/channels/'+channel+'/messages',params=params,headers={'Authorization':'Bot '+token})
        if response.status_code!=200: raise RuntimeError('Discord 조회 실패 (HTTP '+str(response.status_code)+')')
        data=response.json()
        if not isinstance(data,list): raise RuntimeError('Discord 메시지 응답 형식 오류')
        return data
    except (httpx.HTTPError,ValueError):
        raise RuntimeError('Discord 연결 또는 응답 오류') from None
