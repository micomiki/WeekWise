from datetime import datetime, timezone, timedelta

def signup(client,email='student@example.org'):
    r=client.post('/api/auth/register',json={'email':email,'display_name':'Example Student','password':'a-strong-password-2026'})
    assert r.status_code==201,r.text
    return {'Authorization':'Bearer '+r.json()['token']}

def test_account_and_authentication(client):
    assert client.get('/api/courses').status_code==401
    h=signup(client)
    assert client.get('/api/auth/me',headers=h).json()['email']=='student@example.org'
    assert client.post('/api/auth/register',json={'email':'student@example.org','display_name':'X','password':'a-strong-password-2026'}).status_code==409
    assert client.post('/api/auth/login',json={'email':'student@example.org','password':'wrong'}).status_code==401
    assert client.post('/api/auth/login',json={'email':'student@example.org','password':'a-strong-password-2026'}).status_code==200

def test_course_archive_retains_assignments(client):
    h=signup(client)
    bad=client.post('/api/courses',headers=h,json={'title':'   '})
    assert bad.status_code==422
    course=client.post('/api/courses',headers=h,json={'title':'Italian B1','institution':'Language school'}).json()
    due=(datetime.now(timezone.utc)+timedelta(days=3)).isoformat()
    a=client.post('/api/assignments',headers=h,json={'course_id':course['id'],'title':'Vocabulary assignment','due_at':due})
    assert a.status_code==201,a.text
    assert a.json()['estimated_minutes'] is None
    archived=client.patch('/api/courses/'+str(course['id']),headers=h,json={'archived':True})
    assert archived.json()['archived'] is True
    assert len(client.get('/api/assignments',headers=h).json())==1
    assert client.post('/api/assignments',headers=h,json={'course_id':course['id'],'title':'Another','due_at':due}).status_code==404

def test_user_isolation_and_deadline_validation(client):
    h1=signup(client,'first@example.org');h2=signup(client,'second@example.org')
    c=client.post('/api/courses',headers=h1,json={'title':'Private course'}).json()
    assert client.get('/api/courses',headers=h2).json()==[]
    assert client.patch(f"/api/courses/{c['id']}",headers=h2,json={'title':'Stolen'}).status_code==404
    bad=client.post('/api/assignments',headers=h1,json={'course_id':c['id'],'title':'Bad date','due_at':'2026-11-16T14:00:00'})
    assert bad.status_code==422
    bad=client.post('/api/assignments',headers=h2,json={'course_id':c['id'],'title':'No access','due_at':'2026-11-16T14:00:00+01:00'})
    assert bad.status_code==404
