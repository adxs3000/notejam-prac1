import unittest
import urllib.parse

from contextlib import contextmanager
from flask import url_for
from flask_testing import TestCase
from notejam import app, db
from notejam.config import TestingConfig
from notejam.models import User, Pad, Note

app.config.from_object(TestingConfig)

class NotejamBaseTestCase(TestCase):
    def setUp(self):
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def create_app(self):
        test_app = app
        test_app.config['TESTING'] = True
        test_app.config['CSRF_ENABLED'] = False
        return test_app

    def create_user(self, **kwargs):
        user = User(email=kwargs['email'])
        user.set_password(kwargs['password'])
        db.session.add(user)
        db.session.commit()
        return user

    def create_pad(self, **kwargs):
        pad = Pad(**kwargs)
        db.session.add(pad)
        db.session.commit()
        return pad

    def create_note(self, **kwargs):
        note = Note(**kwargs)
        db.session.add(note)
        db.session.commit()
        return note

@contextmanager
def signed_in_user(user):
    '''
    Signed in user context
    Usage:
        user = get_user()
        with signed_in_user(user) as c:
            response = c.get(...)
    '''
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = user.id
            sess['_fresh'] = True
        yield c

class SignupTestCase(NotejamBaseTestCase):
    def _get_user_data(self, **kwargs):
        user_data = {
            'email': 'testt@example.com',
            'password': 'secure_password',
            'repeat_password': 'secure_password'
        }
        user_data.update(**kwargs)
        return user_data

    def test_signup_success(self):
        response = self.client.post(url_for("signup"), data=self._get_user_data())
        self.assertRedirects(response, url_for('signin'))
        self.assertEqual(1, User.query.count())

    def test_signup_fail_required_fields(self):
        response = self.client.post(url_for("signup"), data={})
        form_errors = self.get_context_variable('form').errors
        self.assertEqual(set(self._get_user_data().keys()), set(form_errors.keys()))

    def test_signup_fail_email_exists(self):
        data = self._get_user_data()
        self.create_user(**data)
        response = self.client.post(url_for("signup"), data=self._get_user_data())
        form_errors = self.get_context_variable('form').errors
        self.assertEqual(['email'], list(form_errors.keys()))

    def test_signup_fail_invalid_email(self):
        data = self._get_user_data()
        data['email'] = 'invalid email'
        response = self.client.post(url_for("signup"), data=data)
        form_errors = self.get_context_variable('form').errors
        self.assertEqual(['email'], list(form_errors.keys()))

    def test_signup_fail_passwords_dont_match(self):
        invalid_data = self._get_user_data(password='another pass')
        response = self.client.post(url_for('signup'), data=invalid_data)
        form_errors = self.get_context_variable('form').errors
        self.assertEqual(['repeat_password'], list(form_errors.keys()))

class SigninTestCase(NotejamBaseTestCase):
    def _get_user_data(self, **kwargs):
        user_data = {
            'email': 'testt@example.com',
            'password': 'secure_password'
        }
        user_data.update(**kwargs)
        return user_data

    def test_signin_success(self):
        data = self._get_user_data()
        self.create_user(**data)
        response = self.client.post(url_for('signin'), data=data)
        self.assertRedirects(response, url_for('home'))

    def test_signin_fail(self):
        response = self.client.post(url_for('signin'), data=self._get_user_data())
        self.assertIn('Wrong email or password', response.data.decode())

    def test_signin_fail_required_fields(self):
        response = self.client.post(url_for("signin"), data={})
        form_errors = self.get_context_variable('form').errors
        self.assertEqual(set(self._get_user_data().keys()), set(form_errors.keys()))

    def test_signin_fail_invalid_email(self):
        data = self._get_user_data()
        data['email'] = 'invalid email'
        response = self.client.post(url_for("signin"), data=data)
        form_errors = self.get_context_variable('form').errors
        self.assertEqual(['email'], list(form_errors.keys()))

class PadTestCase(NotejamBaseTestCase):

    def test_create_success(self):
        user = self.create_user(email='testt@example.com', password='password')
        with signed_in_user(user) as c:
            response = c.post(url_for('create_pad'), data={'name': 'pad'})
            self.assertRedirects(response, url_for('home'))
            self.assertEqual(1, Pad.query.count())

    def test_create_fail_required_name(self):
        user = self.create_user(email='testt@example.com', password='password')
        with signed_in_user(user) as c:
            response = c.post(url_for('create_pad'), data={})
            form_errors = self.get_context_variable('form').errors
            self.assertEqual(['name'], list(form_errors.keys()))

    def test_create_fail_anonymous_user(self):
        response = self.client.post(url_for('create_pad'), data={'name': 'pad'})
        expected_redirect = url_for('signin') + f"?next={urllib.parse.quote(url_for('create_pad'))}"
        self.assertRedirects(response, expected_redirect)

    def test_edit_success(self):
        user = self.create_user(email='testt@example.com', password='password')
        pad = self.create_pad(name='pad', user=user)
        with signed_in_user(user) as c:
            new_name = 'new pad name'
            response = c.post(url_for('edit_pad', pad_id=pad.id), data={'name': new_name})
            self.assertRedirects(response, url_for('pad_notes', pad_id=pad.id))
            self.assertEqual(new_name, Pad.query.get(pad.id).name)

    def test_edit_fail_required_name(self):
        user = self.create_user(email='testt@example.com', password='password')
        pad = self.create_pad(name='pad', user=user)
        with signed_in_user(user) as c:
            response = c.post(url_for('edit_pad', pad_id=pad.id), data={'name': ''})
            form_errors = self.get_context_variable('form').errors
            self.assertEqual(['name'], list(form_errors.keys()))

    def test_edit_fail_anothers_user(self):
        user = self.create_user(email='email@example.com', password='password')
        pad = self.create_pad(name='pad', user=user)
        another_user = self.create_user(email='another@example.com', password='password')
        with signed_in_user(another_user) as c:
            response = c.post(url_for('edit_pad', pad_id=pad.id), data={})
            self.assertEqual(404, response.status_code)

    def test_delete_success(self):
        user = self.create_user(email='email@example.com', password='password')
        pad = self.create_pad(name='pad', user=user)
        with signed_in_user(user) as c:
            response = c.post(url_for('delete_pad', pad_id=pad.id))
            self.assertRedirects(response, url_for('home'))
            self.assertEqual(0, Pad.query.count())

    def test_delete_fail_anothers_user(self):
        user = self.create_user(email='email@example.com', password='password')
        pad = self.create_pad(name='pad', user=user)
        another_user = self.create_user(email='another@example.com', password='password')
        with signed_in_user(another_user) as c:
            response = c.post(url_for('delete_pad', pad_id=pad.id))
            self.assertEqual(404, response.status_code)

class NoteTestCase(NotejamBaseTestCase):
    def _get_note_data(self, **kwargs):
        note_data = {
            'name': 'note', 'pad': 0, 'text': 'text'
        }
        note_data.update(**kwargs)
        return note_data

    def test_create_success(self):
        user = self.create_user(email='email@example.com', password='password')
        pad = self.create_pad(name='pad', user=user)
        with signed_in_user(user) as c:
            response = c.post(url_for('create_note'), data=self._get_note_data(pad=pad.id))
            self.assertRedirects(response, url_for('home'))
            self.assertEqual(1, Note.query.count())

    def test_create_fail_required_fields(self):
        user = self.create_user(email='email@example.com', password='password')
        pad = self.create_pad(name='pad', user=user)
        with signed_in_user(user) as c:
            response = c.post(url_for('create_note'), data={})
            form_errors = self.get_context_variable('form').errors
            self.assertEqual(set(self._get_note_data().keys()), set(form_errors.keys()))

    def test_create_fail_anothers_pad(self):
        user = self.create_user(email='email@example.com', password='password')
        another_user = self.create_user(email='another@example.com', password='password')
        pad = self.create_pad(name='pad', user=another_user)
        with signed_in_user(user) as c:
            response = c.post(url_for('create_note'), data=self._get_note_data(pad=pad.id))
            self.assertEqual(404, response.status_code)

    def test_edit_success(self):
        user = self.create_user(email='email@example.com', password='password')
        pad = self.create_pad(name='pad', user=user)
        note = self.create_note(name='note', text='text', pad=pad.id, user=user)
        with signed_in_user(user) as c:
            new_name = 'new note name'
            response = c.post(url_for('edit_note', note_id=note.id), data=self._get_note_data(name=new_name))
            self.assertRedirects(response, url_for('home'))
            self.assertEqual(new_name, Note.query.get(note.id).name)

    def test_edit_fail_required_fields(self):
        user = self.create_user(email='email@example.com', password='password')
        pad = self.create_pad(name='pad', user=user)
        note = self.create_note(name='note', text='text', pad=pad.id, user=user)
        with signed_in_user(user) as c:
            response = c.post(url_for('edit_note', note_id=note.id), data={})
            form_errors = self.get_context_variable('form').errors
            self.assertEqual(set(self._get_note_data().keys()), set(form_errors.keys()))

    def test_edit_fail_anothers_user(self):
        user = self.create_user(email='email@example.com', password='password')
        pad = self.create_pad(name='pad', user=user)
        note = self.create_note(name='note', text='text', pad=pad.id, user=user)
        another_user = self.create_user(email='another@example.com', password='password')
        with signed_in_user(another_user) as c:
            response = c.post(url_for('edit_note', note_id=note.id), data={})
            self.assertEqual(404, response.status_code)

    def test_delete_success(self):
        user = self.create_user(email='email@example.com', password='password')
        pad = self.create_pad(name='pad', user=user)
        note = self.create_note(name='note', text='text', pad=pad.id, user=user)
        with signed_in_user(user) as c:
            response = c.post(url_for('delete_note', note_id=note.id))
            self.assertRedirects(response, url_for('home'))
            self.assertEqual(0, Note.query.count())

    def test_delete_fail_anothers_user(self):
        user = self.create_user(email='email@example.com', password='password')
        pad = self.create_pad(name='pad', user=user)
        note = self.create_note(name='note', text='text', pad=pad.id, user=user)
        another_user = self.create_user(email='another@example.com', password='password')
        with signed_in_user(another_user) as c:
            response = c.post(url_for('delete_note', note_id=note.id))
            self.assertEqual(404, response.status_code)

if __name__ == '__main__':
    unittest.main()
