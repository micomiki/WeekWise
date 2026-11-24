from datetime import datetime, timedelta, timezone
from test_sprint2_guidance_backup import signup

def create_assignment(client, headers, title, days):
    course=client.post('/api/courses', headers=headers, json={'title':title+' course'}).json()['id']
    return client.post('/api/assignments', headers=headers, json={
        'course_id':course,'title':title,
        'due_at':(datetime.now(timezone.utc)+timedelta(days=days)).isoformat()
    }).json()['id']

def add(client, headers, assignment, name, prereqs=None, minutes=None):
    resp=client.post('/api/planning/tasks', headers=headers,json={
        'assignment_id':assignment,'title':name,'depends_on_ids':prereqs or [],'estimated_minutes':minutes
    })
    assert resp.status_code==201,resp.text
    return resp.json()['id']

def test_assignment_deadline_and_within_assignment_prerequisites(client):
    h=signup(client,'deps1@example.org')
    urgent=create_assignment(client,h,'Urgent',1)
    later=create_assignment(client,h,'Later',7)
    gather=add(client,h,urgent,'Gather data')
    filter_id=add(client,h,urgent,'Filter data',[gather])
    document=add(client,h,urgent,'Document',[filter_id],2)
    other=add(client,h,later,'Other assignment task')
    result=client.get('/api/weekwise/suggestions',headers=h).json()
    assert result['suggested']['task_id']==gather
    assert result['items'][0]['task_id']==gather
    assert any(t['task_id']==document and not t['ready'] for t in result['items'])
    assert any(t['task_id']==other and t['ready'] for t in result['items'])
    assert client.patch(f'/api/planning/tasks/{gather}',headers=h,json={'completed':True}).status_code==200
    assert client.get('/api/weekwise/suggestions',headers=h).json()['suggested']['task_id']==filter_id
    client.patch(f'/api/planning/tasks/{filter_id}',headers=h,json={'completed':True})
    assert client.get('/api/weekwise/suggestions',headers=h).json()['suggested']['task_id']==document

def test_reject_cycle_self_cross_assignment_and_other_account(client):
    h=signup(client,'deps2@example.org')
    other=signup(client,'deps3@example.org')
    aid=create_assignment(client,h,'First',3)
    other_aid=create_assignment(client,h,'Second',4)
    a=add(client,h,aid,'A')
    b=add(client,h,aid,'B',[a])
    c=add(client,h,aid,'C',[b])
    d=add(client,h,other_aid,'D')
    assert client.patch(f'/api/planning/tasks/{a}',headers=h,json={'depends_on_ids':[c]}).status_code==422
    assert client.patch(f'/api/planning/tasks/{a}',headers=h,json={'depends_on_ids':[a]}).status_code==422
    assert client.patch(f'/api/planning/tasks/{b}',headers=h,json={'depends_on_ids':[d]}).status_code==422
    assert client.patch(f'/api/planning/tasks/{b}',headers=h,json={'depends_on_ids':[a,a]}).status_code==422
    assert client.patch(f'/api/planning/tasks/{b}',headers=other,json={'depends_on_ids':[a]}).status_code==404
    assert client.get('/api/planning/tasks',headers=h).json()[0]['depends_on_ids']==[]

def test_delete_dependency_and_backup_round_trip(client):
    h=signup(client,'deps4@example.org')
    aid=create_assignment(client,h,'Course',2)
    a=add(client,h,aid,'First')
    b=add(client,h,aid,'Second',[a])
    backup=client.get('/api/weekwise/backup/export',headers=h).json()
    assert next(t for t in backup['tasks'] if t['id']==b)['depends_on_ids']==[a]
    assert client.post('/api/weekwise/backup/validate',headers=h,json=backup).status_code==200
    assert client.post('/api/weekwise/backup/restore',headers=h,json={'backup':backup,'confirm':True}).status_code==200
    restored=client.get('/api/weekwise/backup/export',headers=h).json()
    first=next(t for t in restored['tasks'] if t['title']=='First')
    second=next(t for t in restored['tasks'] if t['title']=='Second')
    assert second['depends_on_ids']==[first['id']]
    bad={**backup,'tasks':[{**t,'depends_on_ids':[t['id']]} if t['title']=='Second' else t for t in backup['tasks']]}
    assert client.post('/api/weekwise/backup/restore',headers=h,json={'backup':bad,'confirm':True}).status_code==422
    assert client.get('/api/weekwise/backup/export',headers=h).json()==restored
    assert client.delete(f"/api/planning/tasks/{first['id']}",headers=h).status_code==200
    assert next(t for t in client.get('/api/planning/tasks',headers=h).json() if t['title']=='Second')['depends_on_ids']==[]

def test_older_backups_without_dependency_fields_still_restore(client):
    h=signup(client,'deps5@example.org')
    aid=create_assignment(client,h,'Old',3)
    add(client,h,aid,'Old task')
    backup=client.get('/api/weekwise/backup/export',headers=h).json()
    for task in backup['tasks']:task.pop('depends_on_ids')
    response=client.post('/api/weekwise/backup/restore',headers=h,json={'backup':backup,'confirm':True})
    assert response.status_code==200,response.text
