from core import runtime as rt


def history(action, **kw):
    with rt.lock:
        if action == 'list':
            return rt.items('mission', scoped=False)
        if action == 'load':
            m = rt.get('mission', kw['mission_id'], scoped=False)
            return {'mission': m, 'work_log': [entry for entry in rt.items('work_log', scoped=False) if entry.get('mission_id') == m['id']]}
        if rt.active and rt.get('mission', rt.active['id'], False)['state'] == 'running':
            rt.fail('현재 작업을 완료하거나 중단한 후 선택하세요.', 409)
        if action == 'create':
            name = str(kw['name']).strip()
            if not name or len(name) > 120:
                rt.fail('작업 이름은 1~120자여야 합니다.')
            m = rt.save('mission', {'id': rt.uid(), 'name': name, 'plan': '', 'version': 0,
                 'state': 'ready', 'progress': {}, 'created_at': rt.timestamp(), 'updated_at': rt.timestamp()})
        elif action == 'select':
            m = rt.get('mission', kw['mission_id'], scoped=False)
        else:
            rt.fail('지원하지 않는 history 동작입니다.')
        rt.active = {'id': m['id'], 'generation': rt.uid()}
        rt.context.set(dict(rt.active))
        # A fresh user selection authorizes a fresh execution, never an automatic restart.
        rt.stop_event.clear()
        import config
        config.KILL_SWITCH = False
        if m['state'] == 'cancelled':
            m['state'] = 'ready'
            rt.save('mission', m)
        return {'mission': m, 'context_id': rt.active['generation'], 'work_log': rt.items('work_log')}


def mission(action, **kw):
    with rt.lock:
        m = rt.current()
        if action == 'status' and kw['mode'] == 'get':
            return m
        if action in ('plan', 'workflow'):
            if kw['mode'] == 'get':
                return {'plan': m['plan'], 'version': m['version']}
            if action == 'plan' and m['version']:
                rt.fail('기존 계획은 workflow로 수정하세요.', 409)
            if action == 'workflow' and rt.number(kw['version'], 0, integer=True) != m['version']:
                rt.fail('계획서가 변경되었습니다. 최신 계획을 읽으세요.', 409)
            if not isinstance(kw['text'], str) or not kw['text'].strip():
                rt.fail('계획서는 비어 있지 않은 문자열이어야 합니다.')
            m['plan'] = kw['text']
            m['version'] += 1
        elif action == 'run':
            rt.check_stop()
            if not m['plan']:
                rt.fail('계획서가 필요합니다.', 409)
            if m['state'] == 'running':
                rt.fail('이미 실행 중입니다.', 409)
            m['state'] = 'running'
        elif action == 'status':
            data = rt.options(kw['data'], {'current_step', 'completed_steps', 'current_action', 'state'})
            if 'completed_steps' in data and not isinstance(data['completed_steps'], list):
                rt.fail('completed_steps는 배열이어야 합니다.')
            if 'state' in data:
                if data['state'] not in ('running', 'completed'):
                    rt.fail('state는 running/completed만 가능합니다.')
                if m['state'] not in ('running',):
                    rt.fail('run 이후 상태를 갱신하세요.', 409)
                m['state'] = data['state']
            m['progress'].update({k:v for k,v in data.items() if k != 'state'})
        elif action == 'cancel':
            return rt.stop(str(kw['reason']))
        elif action == 'work_log':
            if kw['mode'] == 'list':
                return rt.items('work_log')
            if not isinstance(kw['entry'], dict):
                rt.fail('entry는 JSON 객체여야 합니다.')
            entry = dict(kw['entry'])
            entry.pop('id', None)
            entry.pop('created_at', None)
            return rt.log_work(entry)
        m['updated_at'] = rt.timestamp()
        return rt.save('mission', m)


def interaction(action, **kw):
    if action == 'ask_user':
        rt.check_stop()
        if not isinstance(kw['question'],str) or not isinstance(kw['options'],list) or any(not isinstance(v,str) for v in kw['options']):
            rt.fail('question은 문자열, options는 문자열 배열이어야 합니다.')
        q = rt.save('question', {'id': rt.uid(), 'question': kw['question'], 'options': kw['options'],
                     'state': 'pending', 'answer': None, 'created_at': rt.timestamp()}, rt.current()['id'])
        # Endpoint-only: client polls status. An unanswered question never becomes approval.
        return q
    if action == 'questions':
        return rt.items('question')
    with rt.lock:
        q = rt.get('question', kw['question_id'])
        if action == 'answer':
            if q['state'] != 'pending':
                rt.fail('이미 종료된 질문입니다.', 409)
            q.update(answer=kw['answer'], state='answered')
            rt.save('question', q, rt.current()['id'])
        elif q['state'] == 'pending' and rt.stop_event.is_set():
            q['state'] = 'cancelled'
            rt.save('question', q, rt.current()['id'])
        return q


def watch(action, **kw):
    if action == 'start':
        rt.fail('WATCH_CONDITION_UNDEFINED: Watch 조건은 아직 확정되지 않았습니다.', 409)
    if action == 'list':
        return rt.items('watch')
    item = rt.get('watch', kw['watch_id'])
    if action == 'stop':
        item['state'] = 'stopped'
        rt.save('watch', item, rt.current()['id'])
    return item
