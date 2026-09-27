"""Start the configured server without an interactive startup prompt."""
import config
import server
import uvicorn
from core import runtime as rt
from core.missions import history

if __name__ == '__main__':
    if config.PORT != 8002:
        raise RuntimeError('PC-Control-Server must use port 8002.')
    rt.init()
    missions = history('list')
    if missions:
        history('select', mission_id=missions[0]['id'])
        print('Selected the first saved mission.', flush=True)
    else:
        print('No saved mission; server starts ready for mission creation.', flush=True)
    uvicorn.run(server.app, host=config.HOST, port=8002)