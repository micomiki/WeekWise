from datetime import date

def signup(client,email):
    result=client.post('/api/auth/register',json={'email':email,'display_name':'Student','password':'strong-pass-123'})
    assert result.status_code==201,result.text
    return {'Authorization':'Bearer '+result.json()['token']}

def assignment(client,headers):
    c=client.post('/api/courses',headers=headers,json={'title':'Algebra'})
    assert c.status_code==201,c.text
    a=client.post('/api/assignments',headers=headers,json={'title':'Homework','course_id':c.json()['id'],'due_at':'2026-12-01T16:00:00+01:00'})
    assert a.status_code==201,a.text
    return a.json()['id']

def test_task_crud_progress_order_and_ownership(client):
    user1=signup(client,'one@example.org'); aid=assignment(client,user1)
    a=client.post('/api/planning/tasks',headers=user1,json={'assignment_id':aid,'title':'Read chapter','estimated_minutes':None})
    assert a.status_code==201,a.text
    tid=a.json()['id']
    b=client.post('/api/planning/tasks',headers=user1,json={'assignment_id':aid,'title':'Practice','estimated_minutes':60})
    assert b.status_code==201
    assert [t['title'] for t in client.get('/api/planning/tasks',headers=user1).json()]==['Read chapter','Practice']
    assert client.patch(f'/api/planning/tasks/{tid}',headers=user1,json={'completed':True,'title':'Read chapters'}).json()['completed'] is True
    assert client.patch(f'/api/planning/tasks/{tid}',headers=user1,json={'completed':False}).json()['completed'] is False
    other=signup(client,'other@example.org')
    assert client.get('/api/planning/tasks',headers=other).json()==[]
    assert client.patch(f'/api/planning/tasks/{tid}',headers=other,json={'completed':True}).status_code==404
    assert client.post('/api/planning/tasks',headers=other,json={'assignment_id':aid,'title':'Steal'}).status_code==404
    assert client.delete(f'/api/planning/tasks/{tid}',headers=user1).status_code==200

def test_availability_unknown_zero_and_overload(client):
    headers=signup(client,'planner@example.org');aid=assignment(client,headers)
    task=client.post('/api/planning/tasks',headers=headers,json={'assignment_id':aid,'title':'Write'}).json()['id']
    assert client.put('/api/planning/availability',headers=headers,json={'day':'2026-11-23','minutes':-1}).status_code==422
    week=client.get('/api/planning/week?start=2026-11-23',headers=headers).json()
    assert week['days'][0]['available_minutes'] is None
    assert week['days'][0]['overload_minutes'] is None
    assert client.put('/api/planning/availability',headers=headers,json={'day':'2026-11-23','minutes':0}).status_code==200
    assert client.post('/api/planning/allocations',headers=headers,json={'task_id':task,'day':'2026-11-23','minutes':120}).status_code==201
    assert client.get('/api/planning/week?start=2026-11-23',headers=headers).json()['days'][0]['overload_minutes']==120
    client.put('/api/planning/availability',headers=headers,json={'day':'2026-11-23','minutes':720})
    for i in range(2):
        response=client.post('/api/planning/allocations',headers=headers,json={'task_id':task,'day':'2026-11-23','minutes':540})
        assert response.status_code==201,response.text
    day=client.get('/api/planning/week?start=2026-11-23',headers=headers).json()['days'][0]
    assert day['planned_minutes']==1200 and day['available_minutes']==720 and day['overload_minutes']==480
    assert client.get('/api/planning/week?start=2026-11-24',headers=headers).status_code==422
    client.delete('/api/planning/availability/2026-11-23',headers=headers)
    assert client.get('/api/planning/week?start=2026-11-23',headers=headers).json()['days'][0]['overload_minutes'] is None

def test_allocation_ownership_cleanup_and_persistence(client):
    headers=signup(client,'owner@example.org'); other=signup(client,'outsider@example.org');aid=assignment(client,headers)
    t=client.post('/api/planning/tasks',headers=headers,json={'assignment_id':aid,'title':'Task'}).json()['id']
    assert client.post('/api/planning/allocations',headers=other,json={'task_id':t,'day':'2026-11-24','minutes':90}).status_code==404
    a=client.post('/api/planning/allocations',headers=headers,json={'task_id':t,'day':'2026-11-24','minutes':90}).json()['id']
    assert client.patch(f'/api/planning/allocations/{a}',headers=other,json={'minutes':20}).status_code==404
    assert client.patch(f'/api/planning/allocations/{a}',headers=headers,json={'minutes':30}).json()['minutes']==30
    assert len(client.get('/api/planning/allocations?start=2026-11-23&end=2026-11-29',headers=headers).json())==1
    assert client.delete(f'/api/planning/tasks/{t}',headers=headers).status_code==200
    assert client.get('/api/planning/allocations?start=2026-11-23&end=2026-11-29',headers=headers).json()==[]
