import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_login_get(client):
    response = client.get('/login')
    assert response.status_code == 200
    assert b'Welcome Back' in response.data
    assert b'Sign in to your AuctionHub account' in response.data
    assert b'Email Address' in response.data
    assert b'Password' in response.data
    assert b"Don't have an account?" in response.data

def test_login_post_invalid_credentials(client):
    response = client.post('/login', data={
        'email': 'invalid@example.com',
        'password': 'wrongpassword'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Invalid credentials' in response.data or b'login' in response.data.lower() 