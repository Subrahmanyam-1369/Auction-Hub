import pytest
from app import app, get_db_connection

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        yield client

def test_index(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b'AuctionHub' in response.data

def test_login_get(client):
    response = client.get('/login')
    assert response.status_code == 200
    assert b'login' in response.data.lower()

def test_user_dashboard_redirect_if_not_logged_in(client):
    response = client.get('/dashboard', follow_redirects=False)
    assert response.status_code == 302
    assert '/login' in response.headers['Location']

def test_user_auctions_redirect_if_not_logged_in(client):
    response = client.get('/dashboard/auctions', follow_redirects=False)
    assert response.status_code == 302
    assert '/login' in response.headers['Location']

# --- Database tests ---
def test_db_query_products():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM normal_products LIMIT 1')
    _ = cursor.fetchall()  # Fetch all results to clear the result set
    assert cursor.column_names is not None
    assert 'id' in cursor.column_names
    assert 'name' in cursor.column_names
    cursor.close()
    conn.close()

def test_db_insert_and_cleanup_product():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
        INSERT INTO normal_products (name, description, image, starting_price, current_bid, end_date, status)
        VALUES (%s, %s, %s, %s, %s, NOW() + INTERVAL 1 DAY, %s)
    ''', ('pytest_product', 'pytest desc', 'pytest.jpg', 100, 100, 'active'))
    conn.commit()
    cursor.execute('SELECT * FROM normal_products WHERE name = %s', ('pytest_product',))
    product = cursor.fetchone()
    assert product is not None
    assert product['name'] == 'pytest_product'
    cursor.execute('DELETE FROM normal_products WHERE name = %s', ('pytest_product',))
    conn.commit()
    cursor.close()
    conn.close() 