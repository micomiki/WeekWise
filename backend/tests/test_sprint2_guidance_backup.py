from datetime import datetime, timedelta, timezone

def signup(client,email):
    r=client.post('/api/auth/register',json={'email':email,'display_name':'Test User','password':'strong-password-123'})
    assert r.status_code==201,r.text
    return {'Authorization':'Bearer '+r.json()['token']}

def seed(client,h):
    c=client.post('/api/courses',headers=h,json={'title':'School course'}).json()['id']
    a=client.post('/api/assignments',headers=h,json={'course_id':c,'title':'Project','due_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}).json()['id']
    t=client.post('/api/planning/tasks',headers=h,json={'assignment_id':a,'title':'Write tests','estimated_minutes':60}).json()['id']
    assert client.put('/api/planning/availability',headers=h,json={'day':'2026-11-23','minutes':120}).status_code==200
    assert client.post('/api/planning/allocations',headers=h,json={'task_id':t,'day':'2026-11-23','minutes':60}).status_code==201
    return c,a,t

def test_suggestions_rank_and_explain(client):
    h=signup(client,'suggestions@example.org');_,a,t=seed(client,h)
    result=client.get('/api/weekwise/suggestions',headers=h)
    assert result.status_code==200,result.text
    assert result.json()['suggested']['task_id']==t
    assert 'Estimated effort: 60' in result.json()['suggested']['reason']
    assert client.patch(f'/api/planning/tasks/{t}',headers=h,json={'completed':True}).status_code==200
    assert client.get('/api/weekwise/suggestions',headers=h).json()['suggested'] is None

def test_missing_estimates_are_not_zero_and_auth_required(client):
    h=signup(client,'missing@example.org');c=client.post('/api/courses',headers=h,json={'title':'Test'}).json()['id']
    a=client.post('/api/assignments',headers=h,json={'course_id':c,'title':'Later','due_at':'2027-01-01T10:00:00Z'}).json()['id']
    client.post('/api/planning/tasks',headers=h,json={'assignment_id':a,'title':'Unknown'})
    result=client.get('/api/weekwise/suggestions',headers=h).json()['suggested']
    assert result['estimated_minutes'] is None and 'unknown' in result['reason']
    assert client.get('/api/weekwise/suggestions').status_code in (401,403)

def test_backup_round_trip_and_isolation(client):
    h=signup(client,'restore@example.org');other=signup(client,'other-restore@example.org');seed(client,h);seed(client,other)
    backup=client.get('/api/weekwise/backup/export',headers=h).json()
    assert backup['version']==1 and len(backup['tasks'])==1
    assert client.post('/api/weekwise/backup/validate',headers=h,json=backup).json()['valid']
    assert client.post('/api/weekwise/backup/restore',headers=h,json={'backup':backup,'confirm':False}).status_code==400
    client.post('/api/courses',headers=h,json={'title':'Temporary'})
    result=client.post('/api/weekwise/backup/restore',headers=h,json={'backup':backup,'confirm':True})
    assert result.status_code==200,result.text
    exported=client.get('/api/weekwise/backup/export',headers=h).json()
    assert len(exported['courses'])==1 and len(exported['tasks'])==1 and len(exported['allocations'])==1
    assert len(client.get('/api/weekwise/backup/export',headers=other).json()['courses'])==1

def test_invalid_restore_cannot_replace_saved_work(client):
    h=signup(client,'invalid@example.org');seed(client,h)
    backup=client.get('/api/weekwise/backup/export',headers=h).json()
    bad={**backup,'tasks':[{**backup['tasks'][0],'assignment_id':999999}]}
    assert client.post('/api/weekwise/backup/validate',headers=h,json=bad).status_code==422
    assert client.post('/api/weekwise/backup/restore',headers=h,json={'backup':bad,'confirm':True}).status_code==422
    assert client.get('/api/weekwise/backup/export',headers=h).json()==backup
    assert client.post('/api/weekwise/backup/restore',headers=h,json={'backup':{**backup,'version':20},'confirm':True}).status_code==422
