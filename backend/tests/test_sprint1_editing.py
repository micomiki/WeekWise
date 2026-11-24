from datetime import datetime, timedelta, timezone
from test_foundation import signup


def test_course_edit_keeps_assignments_and_preserves_isolation(client):
    alice = signup(client, 'alice@example.org')
    bob = signup(client, 'bob@example.org')
    course = client.post('/api/courses', headers=alice, json={'title': 'Italian A1', 'institution': 'School'}).json()
    due = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    assignment = client.post('/api/assignments', headers=alice, json={
        'course_id': course['id'], 'title': 'Vocabulary', 'due_at': due
    }).json()
    assert client.patch(f"/api/courses/{course['id']}", headers=bob, json={'title': 'Other'}).status_code == 404
    renamed = client.patch(f"/api/courses/{course['id']}", headers=alice,
                           json={'title': 'Italian B1', 'institution': 'Language School'})
    assert renamed.status_code == 200
    assert renamed.json()['title'] == 'Italian B1'
    assert client.get('/api/assignments', headers=alice).json()[0]['id'] == assignment['id']
    assert client.patch(f"/api/courses/{course['id']}", headers=alice, json={'title': '   '}).status_code == 422


def test_assignment_edit_validates_date_and_unknown_effort(client):
    headers = signup(client)
    course = client.post('/api/courses', headers=headers, json={'title': 'Biology'}).json()
    due = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    assignment = client.post('/api/assignments', headers=headers, json={
        'course_id': course['id'], 'title': 'Lab', 'due_at': due
    }).json()
    path = f"/api/assignments/{assignment['id']}"
    assert client.patch(path, headers=headers, json={'due_at':'2027-01-01T10:00:00'}).status_code == 422
    assert client.patch(path, headers=headers, json={'estimated_minutes': -1}).status_code == 422
    edited = client.patch(path, headers=headers, json={
        'title': 'Lab final', 'notes': 'Review measurements', 'estimated_minutes': 90,
        'due_at': (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
    })
    assert edited.status_code == 200, edited.text
    assert edited.json()['title'] == 'Lab final'
    assert edited.json()['estimated_minutes'] == 90
    assert edited.json()['notes'] == 'Review measurements'
    reopened_unknown = client.patch(path, headers=headers, json={'estimated_minutes':None})
    assert reopened_unknown.status_code == 200
    assert reopened_unknown.json()['estimated_minutes'] is None
    persisted = client.get('/api/assignments', headers=headers).json()
    assert persisted[0]['title'] == 'Lab final'
    assert persisted[0]['notes'] == 'Review measurements'


def test_deadline_order_and_overdue_summary(client):
    headers = signup(client)
    course = client.post('/api/courses', headers=headers, json={'title':'Economics'}).json()
    now=datetime.now(timezone.utc)
    for title, days in [('Later', 12), ('Overdue', -2), ('Soon', 3)]:
        response=client.post('/api/assignments', headers=headers, json={
            'course_id':course['id'],'title':title,
            'due_at':(now+timedelta(days=days)).isoformat()
        })
        assert response.status_code == 201
    listed=client.get('/api/assignments', headers=headers).json()
    assert [a['title'] for a in listed] == ['Overdue', 'Soon', 'Later']
    overview=client.get('/api/overview',headers=headers).json()
    assert overview['overdue']==1
    assert overview['due_soon']==1
