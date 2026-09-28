"""Exercise Flask against the six-table database with disposable auth data."""

from datetime import datetime, timezone
import argparse
import json
import os
import secrets
import sys

from manage import ROOT, HERE, connect, fingerprint

sys.path.insert(0, str(ROOT / 'backend'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', default='college')
    args = parser.parse_args()
    target = args.database
    before = fingerprint(target)
    auth_probe = 'college_auth_probe_' + secrets.token_hex(4)
    conn = connect()
    cur = conn.cursor()
    checks = []

    def check(label, condition):
        if not condition:
            raise AssertionError(label)
        checks.append(label)
        print('PASS', label)

    cur.execute(f'CREATE DATABASE `{auth_probe}`')
    try:
        cur.execute(f'CREATE TABLE `{auth_probe}`.app_users LIKE college_auth.app_users')
        os.environ['DB_NAME'] = target
        os.environ['DB_AUTH_NAME'] = auth_probe
        from app import app
        from flask_jwt_extended import create_access_token
        from werkzeug.security import generate_password_hash
        password = secrets.token_urlsafe(24)
        cur.execute(f'INSERT INTO `{auth_probe}`.app_users (username,password_hash,role) VALUES (%s,%s,%s)',
                    ('verification_user', generate_password_hash(password), 'user'))
        conn.commit()
        client = app.test_client()
        response = client.post('/login', json={'username':'verification_user', 'password':password})
        check('login reads separate authentication database', response.status_code == 200)
        token = response.get_json()['token']
        check('wrong password is rejected', client.post('/login', json={'username':'verification_user','password':'wrong'}).status_code == 401)
        response = client.post('/signup', json={'username':'verification_signup','password':password})
        check('signup uses separate authentication database', response.status_code == 200 and response.get_json()['role'] == 'user')
        headers = {'Authorization':'Bearer ' + token}
        check('schema endpoint exposes only six academic tables', len(client.get('/schema').get_json()) == 6)
        check('unauthenticated query is rejected', client.post('/query',json={'question':'show students'}).status_code == 401)
        for question, count in [('show students',15),('show courses and faculty',15),('show students with marks above 90',2),('count students by class',15)]:
            response = client.post('/query',headers=headers,json={'question':question})
            check('API: ' + question, response.status_code == 200 and len(response.get_json()['data']) == count)
        response = client.post('/query/refine',headers=headers,json={'previous_sql':'SELECT * FROM results ORDER BY result_id','feedback':'sort by marks descending'})
        check('refinement sorts marks from results', response.status_code == 200 and float(response.get_json()['data'][0]['marks']) == 95)
        check('user cannot use admin routes', client.get('/admin/row?table=students&id=1', headers=headers).status_code == 403)
        with app.app_context():
            admin_token = create_access_token(identity='verification_admin',additional_claims={'role':'admin'})
        admin_headers = {'Authorization':'Bearer ' + admin_token}
        response = client.get('/admin/row?table=students&id=1',headers=admin_headers)
        check('admin fetch uses entity-specific primary keys', response.status_code == 200 and response.get_json()['row']['srn'] == 'PES2026001')
        response = client.put('/admin/update',headers=admin_headers,json={'table':'results','id':1,'data':{'marks':101}})
        check('admin cannot save invalid marks', response.status_code == 400)
        response = client.put('/admin/update',headers=admin_headers,json={'table':'results','id':1,'data':{'exam_id':2}})
        check('admin cannot save a result for another class', response.status_code == 400)
        response = client.put('/admin/update',headers=admin_headers,json={'table':'results','id':15,'data':{'marks':87}})
        check('valid admin update succeeds', response.status_code == 200)
        response = client.put('/admin/update',headers=admin_headers,json={'table':'results','id':15,'data':{'marks':86}})
        check('admin probe restored original value', response.status_code == 200)
        check('app verification preserved all six tables', before == fingerprint(target))
        (HERE / 'app_verification.json').write_text(json.dumps({'checked_at_utc':datetime.now(timezone.utc).isoformat(), 'database':target, 'passed_checks':checks},indent=2)+'\n')
    finally:
        cur.execute(f'DROP DATABASE `{auth_probe}`')
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()
