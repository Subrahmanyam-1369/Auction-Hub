from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
import os
from datetime import datetime, timedelta
import json
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import bcrypt
from werkzeug.utils import secure_filename
import secrets # Add secrets for token generation

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key_here')

# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# MySQL connection helper
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('MYSQL_HOST', 'localhost'),
        port=int(os.getenv('MYSQL_PORT', 3306)),
        user=os.getenv('MYSQL_USER', 'root'),
        password=os.getenv('MYSQL_PASSWORD', 'password'),
        database=os.getenv('MYSQL_DB', 'auctionhub')
    )

# Initialize database tables
def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create normal_products table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS normal_products (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT NOT NULL,
                image VARCHAR(255),
                starting_price DECIMAL(15,2) NOT NULL,
                current_bid DECIMAL(15,2) DEFAULT NULL,
                end_date DATETIME NOT NULL,
                status ENUM('active', 'ended') DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create mortgage_products table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mortgage_products (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT NOT NULL,
                image VARCHAR(255),
                starting_price DECIMAL(15,2) NOT NULL,
                current_bid DECIMAL(15,2) DEFAULT NULL,
                end_date DATETIME NOT NULL,
                status ENUM('active', 'ended') DEFAULT 'active',
                property_address VARCHAR(255),
                property_size INT,
                mortgage_details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create notifications table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                message TEXT NOT NULL,
                type VARCHAR(50),
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Create watchlist table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watchlist (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                product_id INT NOT NULL,
                product_type ENUM('normal', 'mortgage') NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE KEY (user_id, product_id, product_type)
            )
        ''')
        
        # Create password_resets table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS password_resets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                token VARCHAR(100) NOT NULL UNIQUE,
                expires_at DATETIME NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
        cursor.close()
        conn.close()
        print("Database initialized successfully (including password_resets table)")
    except Exception as e:
        print(f"Error initializing database: {str(e)}")
        # If database connection fails, we'll handle errors in each route

# Try to initialize database on startup
try:
    init_db()
except Exception as e:
    print(f"Failed to initialize database: {str(e)}")

# Fake database for demonstration (replace with MySQL in production)
# Demo data for testing UI
users = {
    'user1@example.com': {'password': 'password1', 'name': 'John Doe', 'role': 'user'},
    'admin@example.com': {'password': 'admin123', 'name': 'Admin User', 'role': 'admin'}
}

products = [
    {
        'id': 1,
        'name': 'Vintage Watch',
        'description': 'A rare vintage watch from the 1950s in excellent condition.',
        'starting_price': 500,
        'current_bid': 750,
        'image': 'watch.jpg',
        'end_date': (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S'),
        'type': 'normal'
    },
    {
        'id': 2,
        'name': 'Luxury Apartment',
        'description': 'A beautiful 3-bedroom apartment in the heart of the city.',
        'starting_price': 250000,
        'current_bid': 275000,
        'image': 'apartment.jpg',
        'end_date': (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S'),
        'type': 'mortgage'
    },
    {
        'id': 3,
        'name': 'Antique Painting',
        'description': 'A stunning 18th-century oil painting by a renowned artist.',
        'starting_price': 1200,
        'current_bid': 1500,
        'image': 'painting.jpg',
        'end_date': (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d %H:%M:%S'),
        'type': 'normal'
    }
]

bids = [
    {'id': 1, 'user_email': 'user1@example.com', 'product_id': 1, 'amount': 750, 'time': '2023-04-28 14:35:00'},
    {'id': 2, 'user_email': 'user1@example.com', 'product_id': 3, 'amount': 1500, 'time': '2023-04-29 10:15:00'}
]

# Set up Jinja environment
def format_currency(value):
    if value is None:
        return "N/A"
    return "${:,.2f}".format(value)

def has_auction_ended(end_date):
    if not end_date:
        return False
    try:
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
        return datetime.now() > end_date_obj
    except:
        return False

app.jinja_env.filters['currency'] = format_currency
app.jinja_env.globals['has_auction_ended'] = has_auction_ended

# Routes
@app.route('/')
def index():
    featured_auctions = []
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # --- Update product statuses before querying --- 
        try:
            cursor.execute("UPDATE normal_products SET status = 'ended' WHERE status = 'active' AND end_date <= NOW()")
            # We don't update mortgage here as we only feature normal ones for now
        except Error as update_err:
            print(f"Warning: Failed to update product statuses in index route: {update_err}")
        # --- End status update ---

        # Fetch a few active, recently added normal products
        cursor.execute('''
            SELECT 
                p.id, p.name, p.description, p.image,
                SUBSTRING_INDEX(p.image, ',', 1) as main_image, 
                p.current_bid, p.starting_price, p.end_date, p.status,
                'normal' as type,
                CASE 
                    WHEN p.status = 'ended' THEN 'Ended'
                    WHEN TIMESTAMPDIFF(DAY, NOW(), p.end_date) > 0 THEN CONCAT(TIMESTAMPDIFF(DAY, NOW(), p.end_date), 'd')
                    WHEN TIMESTAMPDIFF(HOUR, NOW(), p.end_date) > 0 THEN CONCAT(TIMESTAMPDIFF(HOUR, NOW(), p.end_date), 'h')
                    ELSE CONCAT(TIMESTAMPDIFF(MINUTE, NOW(), p.end_date), 'm')
                END as time_left
            FROM normal_products p
            WHERE p.status = 'active' 
            ORDER BY p.created_at DESC 
            LIMIT 4
        ''',)
        featured_auctions = cursor.fetchall()

        # Fallback image if main_image is empty
        for auction in featured_auctions:
            if not auction['main_image'] or auction['main_image'].isspace():
                 auction['main_image'] = 'placeholder.jpg' # Default placeholder image

    except Error as db_error:
        print(f"Database error fetching featured auctions for index: {str(db_error)}")
        # Don't flash error on landing page, just show empty section
    except Exception as e:
        print(f"Error fetching featured auctions for index: {str(e)}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return render_template('index.html', featured_auctions=featured_auctions)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
        except Error as e:
            flash('Database connection error.')
            return render_template('login.html')

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            session['user'] = user['email']
            session['name'] = user['name']
            session['role'] = user['role']
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid credentials. Please try again.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
            user = cursor.fetchone()
            if user:
                flash('Email already exists. Please login.')
                cursor.close()
                conn.close()
                return redirect(url_for('login'))
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute('INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, %s)',
                           (name, email, hashed_password, 'user'))
            conn.commit()
            cursor.close()
            conn.close()
            flash('Registration successful. Please login.')
            return redirect(url_for('login'))
        except Error as e:
            flash('Database error during registration.')
            return render_template('register.html')
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('name', None)
    session.pop('role', None)
    return redirect(url_for('index'))

# User routes
@app.route('/dashboard')
def user_dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # --- Update product statuses before querying --- 
        try:
            # Update normal products
            cursor.execute("UPDATE normal_products SET status = 'ended' WHERE status = 'active' AND end_date <= NOW()")
            # Update mortgage products (if applicable - though not used in new arrivals)
            cursor.execute("UPDATE mortgage_products SET status = 'ended' WHERE status = 'active' AND end_date <= NOW()")
            # No commit needed here if autocommit is off, will be part of the transaction
        except Error as update_err:
            # Log the error but proceed
            print(f"Warning: Failed to update product statuses in user_dashboard: {update_err}")
        # --- End status update ---
        
        # Get user id
        cursor.execute('SELECT id FROM users WHERE email = %s', (session['user'],))
        user_result = cursor.fetchone()
        
        if not user_result:
            flash('User not found')
            return redirect(url_for('logout'))
        
        user_id = user_result['id']
        
        # Get active bids count
        cursor.execute('''
            SELECT COUNT(*) as count FROM bids 
            WHERE user_id = %s AND product_type = 'normal'
        ''', (user_id,))
        active_bids_count = cursor.fetchone()['count'] or 0
        
        # Get auctions won count
        cursor.execute('''
            SELECT COUNT(DISTINCT b.product_id, b.product_type) as count 
            FROM bids b
            LEFT JOIN normal_products np ON b.product_id = np.id AND b.product_type = 'normal'
            LEFT JOIN mortgage_products mp ON b.product_id = mp.id AND b.product_type = 'mortgage'
            WHERE 
                b.user_id = %s 
                AND (
                    (b.product_type = 'normal' AND np.status = 'ended' AND b.amount >= np.current_bid)
                    OR
                    (b.product_type = 'mortgage' AND mp.status = 'ended' AND b.amount >= mp.current_bid)
                )
        ''', (user_id,))
        auctions_won_count = cursor.fetchone()['count'] or 0
        
        # Get watchlist count
        cursor.execute('''
            SELECT COUNT(*) as count FROM watchlist
            WHERE user_id = %s
        ''', (user_id,))
        watchlist_count = cursor.fetchone()['count'] or 0
        
        # Get recent activity (bids, wins, watchlist additions)
        try:
            cursor.execute('''
                SELECT 'bid' as activity_type, b.amount, p.name as product_name, b.bid_time as time
                FROM bids b
                JOIN normal_products p ON b.product_id = p.id AND b.product_type = 'normal'
                WHERE b.user_id = %s
                ORDER BY b.bid_time DESC
                LIMIT 10
            ''', (user_id,))
            recent_activity = cursor.fetchall()
        except Exception as activity_error:
            print(f"Error fetching activity: {str(activity_error)}")
            recent_activity = []
        
        # Get new arrivals (recently added active products)
        try:
            cursor.execute('''
                SELECT id, name, description, image, starting_price, current_bid, end_date, status, 'normal' as type
                FROM normal_products
                WHERE status = 'active'  -- Ensure we only fetch active ones
                ORDER BY created_at DESC -- Order by most recently created
                LIMIT 3
            ''')
            new_arrivals = cursor.fetchall()
        except Exception as arrivals_error:
            print(f"Error fetching new arrivals: {str(arrivals_error)}")
            new_arrivals = []
        
        # Get mortgage auctions (for premium users)
        try:
            cursor.execute('''
                SELECT id, name, description, image, starting_price, current_bid, end_date, status, 
                       property_address, property_size, mortgage_details, 'mortgage' as type
                FROM mortgage_products
                WHERE status = 'active'
                ORDER BY created_at DESC
                LIMIT 3
            ''')
            mortgage_auctions = cursor.fetchall()
        except Exception as mortgage_error:
            print(f"Error fetching mortgage auctions: {str(mortgage_error)}")
            mortgage_auctions = []
        
        cursor.close()
        conn.close()
        
        return render_template('user/dashboard.html', 
                              name=session['name'],
                              active_bids_count=active_bids_count,
                              auctions_won_count=auctions_won_count,
                              watchlist_count=watchlist_count,
                              recent_activity=recent_activity,
                              new_arrivals=new_arrivals,
                              mortgage_auctions=mortgage_auctions)
    
    except Exception as e:
        print(f"Dashboard Error: {str(e)}")
        flash('An error occurred while loading the dashboard.')
        return render_template('user/dashboard.html', 
                              name=session.get('name', 'User'),
                              active_bids_count=0,
                              auctions_won_count=0,
                              watchlist_count=0,
                              recent_activity=[],
                              new_arrivals=[],
                              mortgage_auctions=[])

@app.route('/dashboard/auctions')
def user_auctions():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get filter and sort parameters
        status_filter = request.args.get('status', 'active') # Default to active
        sort_order = request.args.get('sort', 'end_date_asc') # Default sort: ending soonest
        
        # Get user ID for watchlist status
        cursor.execute('SELECT id FROM users WHERE email = %s', (session['user'],))
        user = cursor.fetchone()
        user_id = user['id'] if user else None
        
        # Construct the WHERE clause based on status filter
        status_condition = ""
        if status_filter == 'active':
            status_condition = "WHERE p.status = 'active'"
        elif status_filter == 'ending-soon':
            status_condition = "WHERE p.status = 'active' AND p.end_date <= DATE_ADD(NOW(), INTERVAL 24 HOUR)"
        elif status_filter == 'ended':
            status_condition = "WHERE p.status = 'ended'"
        elif status_filter == 'won':
            if user_id:
                status_condition = f"""
                    WHERE p.status = 'ended' AND p.id IN (
                        SELECT b.product_id 
                        FROM bids b 
                        WHERE b.user_id = {user_id} 
                        AND b.product_type = 'normal' 
                        AND b.amount >= p.current_bid
                    )
                """
            else:
                status_condition = "WHERE 1=0" # No results if user not found
        else: # Default or empty status filter means all (or maybe just active? Let's stick to active as default)
             status_condition = "WHERE p.status = 'active'" 

        # Construct ORDER BY clause based on sort_order
        order_by_clause = "ORDER BY "
        if sort_order == 'newest':
            order_by_clause += "p.created_at DESC"
        elif sort_order == 'price_asc':
            order_by_clause += "COALESCE(p.current_bid, p.starting_price) ASC"
        elif sort_order == 'price_desc':
            order_by_clause += "COALESCE(p.current_bid, p.starting_price) DESC"
        else: # Default sort (ending soonest for active, end date desc for others)
            if status_filter == 'active' or status_filter == 'ending-soon':
                 order_by_clause += "p.end_date ASC" 
            else:
                 order_by_clause += "p.end_date DESC"

        # --- Update product statuses before querying --- 
        try:
            # Update normal products
            cursor.execute("UPDATE normal_products SET status = 'ended' WHERE status = 'active' AND end_date <= NOW()")
            # Update mortgage products (if applicable)
            cursor.execute("UPDATE mortgage_products SET status = 'ended' WHERE status = 'active' AND end_date <= NOW()")
            # We don't commit here yet, the main query will run within the same logical transaction context
        except Error as update_err:
            # Log the error but proceed, the bid query might still work with potentially stale statuses
            print(f"Warning: Failed to update product statuses before fetching bids: {update_err}")
        # --- End status update ---

        # Get normal auctions with complete details
        query = f'''
            SELECT 
                p.id, 
                p.name, 
                p.description, 
                p.image,
                SUBSTRING_INDEX(p.image, ',', 1) as main_image, 
                p.starting_price, 
                p.current_bid, 
                p.end_date, 
                p.status,
                CASE 
                    WHEN p.status = 'ended' THEN 'Ended'
                    WHEN TIMESTAMPDIFF(DAY, NOW(), p.end_date) > 0 THEN CONCAT(TIMESTAMPDIFF(DAY, NOW(), p.end_date), 'd ', MOD(TIMESTAMPDIFF(HOUR, NOW(), p.end_date), 24), 'h')
                    WHEN TIMESTAMPDIFF(HOUR, NOW(), p.end_date) > 0 THEN CONCAT(TIMESTAMPDIFF(HOUR, NOW(), p.end_date), 'h ', MOD(TIMESTAMPDIFF(MINUTE, NOW(), p.end_date), 60), 'm')
                    ELSE CONCAT(TIMESTAMPDIFF(MINUTE, NOW(), p.end_date), 'm')
                END as time_left,
                TIMESTAMPDIFF(DAY, NOW(), p.end_date) as days_left,
                MOD(TIMESTAMPDIFF(HOUR, NOW(), p.end_date), 24) as hours_left,
                EXISTS(SELECT 1 FROM watchlist w WHERE w.user_id = {user_id or 0} AND w.product_id = p.id AND w.product_type = 'normal') as in_watchlist
            FROM normal_products p
            {status_condition}
            {order_by_clause} 
        '''
        
        cursor.execute(query)
        normal_auctions = cursor.fetchall()

        # Add images_list for each auction
        for auction in normal_auctions:
            if auction.get('image'):
                auction['images_list'] = [img.strip() for img in auction['image'].split(',') if img.strip()]
            else:
                auction['images_list'] = []

        for auction in normal_auctions:
            # Add relative time for easier display
            if auction['status'] == 'ended':
                auction['time_left'] = "Ended"
            else:
                days_left = auction['days_left']
                hours_left = auction['hours_left']
                if days_left > 0:
                    auction['time_left'] = f"{days_left}d {hours_left}h"
                elif hours_left > 0:
                    auction['time_left'] = f"{hours_left}h"
                else:
                    auction['time_left'] = "< 1h"
        
        cursor.close()
        conn.close()
        
        return render_template('user/auctions.html', 
                              normal_auctions=normal_auctions, 
                              status_filter=status_filter,
                              user_id=user_id)
    except Exception as e:
        print(f"Error in user_auctions: {str(e)}")
        flash('An error occurred while loading auctions.')
        return render_template('user/auctions.html', normal_auctions=[], status_filter='')

@app.route('/dashboard/bids')
def user_bids():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get user id
        cursor.execute('SELECT id FROM users WHERE email = %s', (session['user'],))
        user_result = cursor.fetchone()
        user_id = user_result['id'] if user_result else None
        
        if not user_id:
            flash('User not found')
            return redirect(url_for('logout'))
        
        # --- Update product statuses before querying bids --- 
        try:
            # Update normal products
            cursor.execute("UPDATE normal_products SET status = 'ended' WHERE status = 'active' AND end_date <= NOW()")
            # Update mortgage products (if applicable)
            cursor.execute("UPDATE mortgage_products SET status = 'ended' WHERE status = 'active' AND end_date <= NOW()")
            # We don't commit here yet, the main query will run within the same logical transaction context
        except Error as update_err:
            # Log the error but proceed, the bid query might still work with potentially stale statuses
            print(f"Warning: Failed to update product statuses before fetching bids: {update_err}")
        # --- End status update ---

        # Fetch bids using LEFT JOINs
        query = '''
            SELECT 
                b.id as bid_id,
                b.amount as bid_amount,
                b.bid_time,
                b.product_type,
                b.product_id,
                COALESCE(np.name, mp.name) as product_name,
                COALESCE(np.image, mp.image) as product_image, 
                COALESCE(np.current_bid, mp.current_bid) as current_bid,
                COALESCE(np.starting_price, mp.starting_price) as starting_price,
                COALESCE(np.end_date, mp.end_date) as end_date, 
                COALESCE(np.status, mp.status) as product_status
            FROM bids b
            LEFT JOIN normal_products np ON b.product_id = np.id AND b.product_type = 'normal'
            LEFT JOIN mortgage_products mp ON b.product_id = mp.id AND b.product_type = 'mortgage'
            WHERE b.user_id = %s
            ORDER BY b.bid_time DESC
        '''
        cursor.execute(query, (user_id,))
        all_bids = cursor.fetchall()
        
        # Process bids to add main image and status
        active_bids_count = 0
        won_auctions_count = 0
        total_spent = 0.0

        for bid in all_bids:
            if bid['product_image']:
                bid['main_image'] = bid['product_image'].split(',')[0].strip()
            else:
                bid['main_image'] = 'default_product.jpg'
                
            # Determine bid status (winning, outbid, ended, etc.)
            current_product_bid = bid['current_bid'] or bid['starting_price']
            # Ensure amounts are float for comparison
            bid_amount_float = float(bid['bid_amount']) 
            current_product_bid_float = float(current_product_bid)
            
            if bid['product_status'] == 'ended':
                if bid_amount_float >= current_product_bid_float:
                    bid['bid_status'] = 'Won'
                    bid['status_class'] = 'bg-green-100 text-green-800'
                    won_auctions_count += 1
                    total_spent += bid_amount_float # Add to spent only if won
                else:
                    bid['bid_status'] = 'Lost'
                    bid['status_class'] = 'bg-gray-100 text-gray-800'
            elif bid['product_status'] == 'active':
                active_bids_count += 1 # Count any bid on an active auction as an active bid
                if bid_amount_float >= current_product_bid_float:
                    bid['bid_status'] = 'Winning'
                    bid['status_class'] = 'bg-green-100 text-green-800'
                else:
                    bid['bid_status'] = 'Outbid'
                    bid['status_class'] = 'bg-red-100 text-red-800'
            else:
                bid['bid_status'] = 'Unknown' # Should not happen with active/ended status
                bid['status_class'] = 'bg-gray-100 text-gray-800'
        
        cursor.close()
        conn.close()
        
        return render_template('user/bids.html', 
                               bids=all_bids,
                               active_bids_count=active_bids_count,
                               won_auctions_count=won_auctions_count,
                               total_spent=total_spent)
        
    except Error as db_error:
        print(f"Database error in user_bids: {str(db_error)}")
        flash(f'Database error occurred: {db_error.msg}')
        return render_template('user/bids.html', bids=[])
    except Exception as e:
        print(f"Error in user_bids: {str(e)}")
        flash('An error occurred while loading your bids.')
        return render_template('user/bids.html', bids=[])

@app.route('/dashboard/profile')
def user_profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Fetch user details
        cursor.execute('''
            SELECT id, name, email, role, created_at, premium, bio, phone, location 
            FROM users 
            WHERE email = %s
        ''', (session['user'],))
        user = cursor.fetchone()
        
        if not user:
            flash('User not found')
            # Close cursor and connection before redirecting
            cursor.close()
            conn.close()
            return redirect(url_for('logout'))
        
        # # Get user stats (removed)
        # user_id = user['id']
        
        # # Get active bids count (removed)
        # cursor.execute('''
        #     SELECT COUNT(DISTINCT b.id) as count 
        #     FROM bids b
        #     LEFT JOIN normal_products np ON b.product_id = np.id AND b.product_type = 'normal'
        #     LEFT JOIN mortgage_products mp ON b.product_id = mp.id AND b.product_type = 'mortgage'
        #     WHERE b.user_id = %s AND (
        #         (np.id IS NOT NULL AND np.status = 'active') OR 
        #         (mp.id IS NOT NULL AND mp.status = 'active')
        #     )
        # ''', (user_id,))
        # active_bids_count = cursor.fetchone()['count'] or 0
        
        # # Get auctions won count (removed)
        # cursor.execute('''
        #     SELECT COUNT(DISTINCT b.product_id, b.product_type) as count 
        #     FROM bids b
        #     LEFT JOIN normal_products np ON b.product_id = np.id AND b.product_type = 'normal'
        #     LEFT JOIN mortgage_products mp ON b.product_id = mp.id AND b.product_type = 'mortgage'
        #     WHERE 
        #         b.user_id = %s 
        #         AND (
        #             (b.product_type = 'normal' AND np.status = 'ended' AND b.amount >= np.current_bid)
        #             OR
        #             (b.product_type = 'mortgage' AND mp.status = 'ended' AND b.amount >= mp.current_bid)
        #         )
        # ''', (user_id,))
        # auctions_won_count = cursor.fetchone()['count'] or 0
        
        # # Get auctions participated count (removed)
        # cursor.execute('''
        #     SELECT COUNT(DISTINCT product_id, product_type) as count 
        #     FROM bids 
        #     WHERE user_id = %s
        # ''', (user_id,))
        # auctions_participated_count = cursor.fetchone()['count'] or 0
        
        # # Calculate total spent on won auctions (removed)
        # cursor.execute('''
        #     SELECT SUM(b.amount) as total 
        #     FROM bids b
        #     LEFT JOIN normal_products np ON b.product_id = np.id AND b.product_type = 'normal'
        #     LEFT JOIN mortgage_products mp ON b.product_id = mp.id AND b.product_type = 'mortgage'
        #     WHERE 
        #         b.user_id = %s 
        #         AND (
        #             (b.product_type = 'normal' AND np.status = 'ended' AND b.amount >= np.current_bid)
        #             OR
        #             (b.product_type = 'mortgage' AND mp.status = 'ended' AND b.amount >= mp.current_bid)
        #         )
        # ''', (user_id,))
        # total_spent_result = cursor.fetchone()
        # total_spent = total_spent_result['total'] if total_spent_result and total_spent_result['total'] else 0.0
        
        cursor.close()
        conn.close()
        
        # Format registration date
        reg_date = user['created_at']
        membership_duration = "Unknown"
        if reg_date:
            try:
                delta = datetime.now() - reg_date
                years = delta.days // 365
                months = (delta.days % 365) // 30
                if years > 0:
                    membership_duration = f"{years} Year{'s' if years > 1 else ''}, {months} Month{'s' if months > 1 else ''}"
                elif months > 0:
                    membership_duration = f"{months} Month{'s' if months > 1 else ''}"
                else:
                     membership_duration = f"{delta.days} Day{'s' if delta.days > 1 else ''}"
            except Exception as date_err:
                 print(f"Error formatting membership duration: {date_err}")
                 membership_duration = "Error"
        
        return render_template('user/profile.html', 
                              user=user,
                            #   active_bids=active_bids_count,
                            #   auctions_won=auctions_won_count,
                            #   auctions_participated=auctions_participated_count, # Pass the new count
                            #   total_spent=total_spent,
                              membership_duration=membership_duration)
        
    except Error as db_error:
         print(f"Database error in user_profile: {str(db_error)}")
         flash(f'Database error loading profile: {db_error.msg}')
         # Redirect to dashboard if profile fails to load
         return redirect(url_for('user_dashboard')) 
    except Exception as e:
        print(f"Error in user_profile: {str(e)}")
        flash('An error occurred while loading your profile.')
        # Redirect to dashboard if profile fails to load
        return redirect(url_for('user_dashboard'))

@app.route('/dashboard/profile/update', methods=['GET', 'POST'])
def update_profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    user_id = None
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get current user ID first
        cursor.execute('SELECT id, password_hash FROM users WHERE email = %s', (session['user'],))
        user_info = cursor.fetchone()
        
        if not user_info:
            flash('User not found')
            return redirect(url_for('logout'))
            
        user_id = user_info['id']
        current_hash = user_info['password_hash']
        
        # --- Handle POST Request --- 
        if request.method == 'POST':
            # Get form data
            name = request.form.get('name')
            bio = request.form.get('bio')
            phone = request.form.get('phone')
            location = request.form.get('location')
            current_password = request.form.get('current_password')
            new_password = request.form.get('password')
            
            # Build update query dynamically
            update_fields = []
            update_values = []
            
            if name:
                update_fields.append("name = %s")
                update_values.append(name)
                session['name'] = name # Update session name
                
            if bio is not None: # Allow clearing bio
                 update_fields.append("bio = %s")
                 update_values.append(bio)
                 
            if phone is not None: # Allow clearing phone
                 update_fields.append("phone = %s")
                 update_values.append(phone)
                 
            if location is not None: # Allow clearing location
                 update_fields.append("location = %s")
                 update_values.append(location)
            
            # Update basic profile info if fields were provided
            if update_fields:
                sql = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
                update_values.append(user_id)
                cursor.execute(sql, tuple(update_values))
                conn.commit()
                flash('Profile details updated successfully.')
            
            # Handle password change
            password_updated = False
            # --- Only attempt password change if BOTH fields are filled --- 
            if current_password and new_password:
                # Verify current password
                if bcrypt.checkpw(current_password.encode('utf-8'), current_hash.encode('utf-8')):
                    # Hash and update new password
                    # Add password validation (e.g., length)
                    if len(new_password) < 8:
                         flash('New password must be at least 8 characters long.')
                    else:
                        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                        cursor.execute('UPDATE users SET password_hash = %s WHERE id = %s', 
                                      (hashed_password, user_id))
                        conn.commit()
                        flash('Password updated successfully.')
                        password_updated = True
                else:
                    flash('Current password incorrect. Password not changed.')
            # --- Flash message ONLY if one field is filled, implying intent to change --- 
            elif current_password or new_password: 
                 flash('To change your password, please provide BOTH the current and new password.')
            
            # Password change logic moved to /dashboard/change-password
            
            # Redirect after profile detail updates
            return redirect(url_for('user_profile'))
            
        # --- Handle GET Request --- 
        else: # Method is GET
             # Fetch full user data for the form
            cursor.execute('''
                SELECT id, name, email, role, created_at, premium, bio, phone, location 
                FROM users 
                WHERE id = %s
            ''', (user_id,))
            user = cursor.fetchone()
            
            if not user:
                flash('User data could not be loaded.')
                return redirect(url_for('user_dashboard'))
            
            return render_template('user/update_profile.html', user=user)
            
    except Error as db_error:
         print(f"Database error in update_profile: {str(db_error)}")
         flash(f'Database error updating profile: {db_error.msg}')
         # Redirect based on method
         if request.method == 'POST':
             return redirect(url_for('user_profile')) # Redirect to view profile on POST error
         else:
             return redirect(url_for('user_dashboard')) # Redirect to dash on GET error
             
    except Exception as e:
        print(f"Error in update_profile ({request.method}): {str(e)}")
        flash('An unexpected error occurred while processing your profile.')
        # Redirect based on method
        if request.method == 'POST':
             return redirect(url_for('user_profile'))
        else:
             return redirect(url_for('user_dashboard'))
             
    finally:
        # Ensure cursor and connection are closed
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/dashboard/change-password', methods=['GET', 'POST'])
def change_password():
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get current user ID and hash
        cursor.execute('SELECT id, password_hash FROM users WHERE email = %s', (session['user'],))
        user_info = cursor.fetchone()

        if not user_info:
            flash('User not found')
            return redirect(url_for('logout'))

        user_id = user_info['id']
        current_hash = user_info['password_hash']

        if request.method == 'POST':
            current_password = request.form.get('current_password')
            new_password = request.form.get('password')
            confirm_password = request.form.get('password_confirm')

            # Basic validation
            if not current_password or not new_password or not confirm_password:
                flash('Please fill in all password fields.')
                return render_template('user/change_password.html')

            if new_password != confirm_password:
                flash('New passwords do not match.')
                return render_template('user/change_password.html')

            if len(new_password) < 8:
                flash('New password must be at least 8 characters long.')
                return render_template('user/change_password.html')

            # Verify current password
            if bcrypt.checkpw(current_password.encode('utf-8'), current_hash.encode('utf-8')):
                # Hash and update new password
                hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                cursor.execute('UPDATE users SET password_hash = %s WHERE id = %s', (hashed_password, user_id))
                conn.commit()
                flash('Password updated successfully.')
                return redirect(url_for('user_profile')) # Redirect to profile view on success
            else:
                flash('Current password incorrect.')
                # Re-render the change password page on failure
                return render_template('user/change_password.html')

        # --- Handle GET Request --- 
        else: # Method is GET
            return render_template('user/change_password.html')
            
    except Error as db_error:
         print(f"Database error in change_password: {str(db_error)}")
         flash(f'Database error changing password: {db_error.msg}')
         # Redirect to profile on error
         return redirect(url_for('user_profile'))
             
    except Exception as e:
        print(f"Error in change_password ({request.method}): {str(e)}")
        flash('An unexpected error occurred.')
        # Redirect to profile on error
        return redirect(url_for('user_profile'))
             
    finally:
        # Ensure cursor and connection are closed
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/dashboard/delete-account', methods=['POST'])
def delete_account():
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get user ID
        cursor.execute('SELECT id FROM users WHERE email = %s', (session['user'],))
        user = cursor.fetchone()

        if not user:
            flash('User not found.')
            return redirect(url_for('logout'))

        user_id = user['id']

        # --- IMPORTANT: Add password verification before deleting --- 
        password_to_confirm = request.form.get('password_confirm_delete') # Assuming a password field in the delete form
        cursor.execute('SELECT password_hash FROM users WHERE id = %s', (user_id,))
        user_hash = cursor.fetchone()['password_hash']

        if not password_to_confirm or not bcrypt.checkpw(password_to_confirm.encode('utf-8'), user_hash.encode('utf-8')):
            flash('Incorrect password. Account deletion cancelled.')
            # Redirect back to the update profile page where the delete button is
            return redirect(url_for('update_profile')) 

        # Proceed with deletion
        cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
        conn.commit()

        # Clear session and log out
        session.clear()
        flash('Your account has been successfully deleted.')
        return redirect(url_for('login')) # Redirect to login page after deletion

    except Error as db_error:
        print(f"Database error in delete_account: {str(db_error)}")
        flash(f'Database error deleting account: {db_error.msg}')
        return redirect(url_for('update_profile')) # Redirect back on error
             
    except Exception as e:
        print(f"Error in delete_account: {str(e)}")
        flash('An unexpected error occurred while deleting your account.')
        return redirect(url_for('update_profile')) # Redirect back on error
             
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# Admin routes
@app.route('/admin')
def admin_dashboard():
    if 'user' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Dashboard stats
        cursor.execute('SELECT COUNT(*) as total FROM normal_products')
        normal_total = cursor.fetchone()['total']
        cursor.execute('SELECT COUNT(*) as total FROM mortgage_products')
        mortgage_total = cursor.fetchone()['total']
        total_products = normal_total + mortgage_total
        cursor.execute('SELECT COUNT(*) as active FROM normal_products WHERE end_date > NOW() AND status = "active"')
        normal_active = cursor.fetchone()['active']
        cursor.execute('SELECT COUNT(*) as active FROM mortgage_products WHERE end_date > NOW() AND status = "active"')
        mortgage_active = cursor.fetchone()['active']
        active_auctions = normal_active + mortgage_active
        cursor.execute('SELECT COUNT(*) as total FROM users')
        total_users = cursor.fetchone()['total']
        cursor.execute('SELECT IFNULL(SUM(amount),0) as revenue FROM normal_bids')
        normal_revenue = cursor.fetchone()['revenue']
        cursor.execute('SELECT IFNULL(SUM(amount),0) as revenue FROM mortgage_bids')
        mortgage_revenue = cursor.fetchone()['revenue']
        total_revenue = (normal_revenue or 0) + (mortgage_revenue or 0)
        # Recent activity: latest 5 bids (combine both tables)
        cursor.execute('''
            SELECT b.*, u.name as user, p.name as product, "normal" as type FROM normal_bids b
            JOIN users u ON b.user_id = u.id
            JOIN normal_products p ON b.product_id = p.id
            UNION ALL
            SELECT b.*, u.name as user, p.name as product, "mortgage" as type FROM mortgage_bids b
            JOIN users u ON b.user_id = u.id
            JOIN mortgage_products p ON b.product_id = p.id
            ORDER BY bid_time DESC LIMIT 5
        ''')
        recent_bids = cursor.fetchall()
        # Recent products (latest 5 from both tables)
        cursor.execute('SELECT *, "normal" as type FROM normal_products ORDER BY created_at DESC LIMIT 5')
        recent_normal = cursor.fetchall()
        cursor.execute('SELECT *, "mortgage" as type FROM mortgage_products ORDER BY created_at DESC LIMIT 5')
        recent_mortgage = cursor.fetchall()
        recent_products = recent_normal + recent_mortgage
        recent_products = sorted(recent_products, key=lambda x: x['created_at'], reverse=True)[:5]
        # Recent users (latest 5)
        cursor.execute('SELECT name, email, created_at FROM users ORDER BY created_at DESC LIMIT 5')
        recent_users = cursor.fetchall()
        # Recent premium upgrades (latest 5)
        cursor.execute('SELECT name, email, created_at FROM users WHERE premium = TRUE ORDER BY created_at DESC LIMIT 5')
        recent_premium_upgrades = cursor.fetchall()
        # Recent auctions ended (latest 5)
        cursor.execute('SELECT name, end_date, current_bid, "normal" as type FROM normal_products WHERE end_date < NOW() ORDER BY end_date DESC LIMIT 5')
        ended_normal = cursor.fetchall()
        cursor.execute('SELECT name, end_date, current_bid, "mortgage" as type FROM mortgage_products WHERE end_date < NOW() ORDER BY end_date DESC LIMIT 5')
        ended_mortgage = cursor.fetchall()
        recent_auctions = ended_normal + ended_mortgage
        recent_auctions = sorted(recent_auctions, key=lambda x: x['end_date'], reverse=True)[:5]
        # Dummy analytics data
        analytics_data = {
            'weekly': [10, 20, 15, 30, 25, 40, 35],
            'monthly': [100, 120, 90, 140, 110, 130, 150, 160, 170, 180, 190, 200],
            'yearly': [1200, 1300, 1250, 1400, 1350, 1500, 1600, 1700, 1800, 1900, 2000, 2100]
        }
        cursor.close()
        conn.close()
        return render_template('admin/dashboard.html', 
                              name=session['name'],
                              total_products=total_products,
                              active_auctions=active_auctions,
                              total_users=total_users,
                              total_revenue=total_revenue,
                              recent_activity=recent_bids,
                              recent_products=recent_products,
                              recent_users=recent_users,
                              recent_auctions=recent_auctions,
                              recent_premium_upgrades=recent_premium_upgrades,
                              analytics_data=analytics_data)
    except Exception as e:
        flash('Database error.')
        return redirect(url_for('logout'))

@app.route('/admin/auctions')
def admin_auctions():
    if 'user' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT *, "normal" as type FROM normal_products')
        normal_products_list = cursor.fetchall()
        cursor.execute('SELECT *, "mortgage" as type FROM mortgage_products')
        mortgage_products_list = cursor.fetchall()
        products = normal_products_list + mortgage_products_list
        cursor.close()
        conn.close()
        return render_template('admin/auctions.html', products=products)
    except Exception as e:
        flash('Database error.')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/products/<type>')
def admin_products(type):
    if 'user' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check if tables exist and create them if needed
        try:
            if type == 'normal':
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS normal_products (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        description TEXT NOT NULL,
                        image VARCHAR(255),
                        starting_price DECIMAL(15,2) NOT NULL,
                        current_bid DECIMAL(15,2) DEFAULT NULL,
                        end_date DATETIME NOT NULL,
                        status ENUM('active', 'ended') DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cursor.execute('SELECT * FROM normal_products')
            elif type == 'mortgage':
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS mortgage_products (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        description TEXT NOT NULL,
                        image VARCHAR(255),
                        starting_price DECIMAL(15,2) NOT NULL,
                        current_bid DECIMAL(15,2) DEFAULT NULL,
                        end_date DATETIME NOT NULL,
                        status ENUM('active', 'ended') DEFAULT 'active',
                        property_address VARCHAR(255),
                        property_size INT,
                        mortgage_details TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cursor.execute('SELECT * FROM mortgage_products')
            else:
                products = []
                flash('Invalid product type')
                cursor.close()
                conn.close()
                return redirect(url_for('admin_dashboard'))
                
            products = cursor.fetchall()
                
        except Exception as table_error:
            # Detailed error for missing tables
            flash(f'Error: {str(table_error)}')
            products = []
        
        cursor.close()
        conn.close()
        return render_template('admin/products.html', products=products, type=type)
    except Exception as e:
        flash(f'Database error: {str(e)}')
        return redirect(url_for('admin_dashboard'))

# Create notification function
def create_product_notification(product_name, product_type):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check if notifications table exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                message TEXT NOT NULL,
                type VARCHAR(50),
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        conn.commit()
        
        # Get all user IDs
        cursor.execute('SELECT id FROM users WHERE role = "user"')
        users = cursor.fetchall()
        
        if not users:
            print("No users found to notify")
            return
        
        # Create notification for each user
        message = f"New {product_type} auction added: {product_name}"
        for user in users:
            cursor.execute('''
                INSERT INTO notifications (user_id, message, type, is_read)
                VALUES (%s, %s, %s, %s)
            ''', (user['id'], message, 'new_product', False))
        
        conn.commit()
        print(f"Notification created for {len(users)} users")
    except Exception as e:
        print(f"Error creating notification: {str(e)}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/admin/products/add/<type>', methods=['GET', 'POST'])
def add_product(type):
    if 'user' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if request.method == 'POST':
            name = request.form.get('name')
            description = request.form.get('description')
            starting_price = float(request.form.get('starting_price', 0))
            end_date = request.form.get('end_date')
            
            # Basic validation
            if not name or not description or starting_price <= 0 or not end_date:
                flash('All fields are required and starting price must be positive.')
                return render_template('admin/add_product.html', type=type)
            
            # Handle multiple image names (comma-separated)
            images = request.form.get('images', '')
            # Clean and normalize the comma-separated list
            image_list = [img.strip() for img in images.split(',') if img.strip()]
            # Join back into a comma-separated string for storage
            image_string = ','.join(image_list) if image_list else ''
            
            # Set current_bid to starting_price initially
            current_bid = starting_price
            status = 'active'
            
            if type == 'normal':
                cursor.execute('''
                    INSERT INTO normal_products (name, description, image, starting_price, current_bid, end_date, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''', (name, description, image_string, starting_price, current_bid, end_date, status))
            else:  # mortgage type
                property_address = request.form.get('property_address')
                property_size = request.form.get('property_size', 0)
                mortgage_details = request.form.get('mortgage_details')
                
                cursor.execute('''
                    INSERT INTO mortgage_products 
                    (name, description, image, starting_price, current_bid, end_date, status, property_address, property_size, mortgage_details)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (name, description, image_string, starting_price, current_bid, end_date, status, property_address, property_size, mortgage_details))
            
            # Commit changes and create notification for all users
            conn.commit()
            
            try:
                create_product_notification(name, type)
            except Exception as notify_error:
                # If notification fails, log error but don't fail the whole operation
                print(f"Error creating notification: {str(notify_error)}")
            
            flash('Product added successfully.')
            return redirect(url_for('admin_products', type=type))
        
        cursor.close()
        conn.close()
        return render_template('admin/add_product.html', type=type)
    except Exception as e:
        flash(f'Database error: {str(e)}')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/products/edit/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    if 'user' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    conn = None
    cursor = None
    product = None
    product_type = request.args.get('type') # Get type from URL if present

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Determine product and type accurately
        if product_type == 'normal':
            cursor.execute('SELECT * FROM normal_products WHERE id = %s', (id,))
            product = cursor.fetchone()
        elif product_type == 'mortgage':
            cursor.execute('SELECT * FROM mortgage_products WHERE id = %s', (id,))
            product = cursor.fetchone()
        else: # Type not provided in URL or is invalid, try to infer
            cursor.execute('SELECT * FROM normal_products WHERE id = %s', (id,))
            product = cursor.fetchone()
            if product:
                product_type = 'normal' # Found in normal, set type
            else:
                cursor.execute('SELECT * FROM mortgage_products WHERE id = %s', (id,))
                product = cursor.fetchone()
                if product:
                    product_type = 'mortgage' # Found in mortgage, set type

        # Check if product was found
        if not product:
            flash('Product not found.')
            return redirect(url_for('admin_auctions')) # Or maybe admin_dashboard

        # --- POST Request Handling ---
        if request.method == 'POST':
            name = request.form.get('name')
            description = request.form.get('description')
            starting_price = float(request.form.get('starting_price'))
            end_date = request.form.get('end_date')
            
            # Handle multiple image names (comma-separated)
            images = request.form.get('images', '')
            # Clean and normalize the comma-separated list
            image_list = [img.strip() for img in images.split(',') if img.strip()]
            # Join back into a comma-separated string for storage
            image_string = ','.join(image_list) if image_list else ''

            # Use the determined product_type for update logic
            if product_type == 'normal':
                cursor2 = conn.cursor()
                cursor2.execute('''
                    UPDATE normal_products SET name=%s, description=%s, starting_price=%s, end_date=%s, image=%s WHERE id=%s
                ''', (name, description, starting_price, end_date, image_string, id))
                conn.commit()
                cursor2.close()
            elif product_type == 'mortgage':
                property_address = request.form.get('property_address')
                property_size = request.form.get('property_size')
                mortgage_details = request.form.get('mortgage_details')
                cursor2 = conn.cursor()
                cursor2.execute('''
                    UPDATE mortgage_products SET name=%s, description=%s, starting_price=%s, end_date=%s, image=%s, property_address=%s, property_size=%s, mortgage_details=%s WHERE id=%s
                ''', (name, description, starting_price, end_date, image_string, property_address, property_size, mortgage_details, id))
                conn.commit()
                cursor2.close()
            else:
                 # Should not happen if product was found, but good practice
                 flash('Invalid product type for update.')
                 return redirect(url_for('admin_dashboard'))

            flash('Product updated successfully.')
            # Redirect using the determined product_type
            return redirect(url_for('admin_products', type=product_type))

        # --- GET Request Preparation ---
        # Split the image string into a list for the template
        if product and product.get('image'):
            product['images_list'] = [img.strip() for img in product['image'].split(',') if img.strip()]
        else:
            if product: product['images_list'] = []

        # Always pass the determined 'product_type' to the template
        return render_template('admin/edit_product.html', product=product, type=product_type)
    
    except Exception as e:
        flash('Database error.')
        return redirect(url_for('admin_dashboard'))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/admin/products/delete/<int:id>')
def delete_product(id):
    if 'user' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    type = request.args.get('type', 'normal')
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if type == 'normal':
            cursor.execute('DELETE FROM normal_products WHERE id = %s', (id,))
        else:
            cursor.execute('DELETE FROM mortgage_products WHERE id = %s', (id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Product deleted successfully.')
        return redirect(url_for('admin_products', type=type))
    except Exception as e:
        flash('Database error.')
        return redirect(url_for('admin_dashboard'))

# Add new endpoint to end an auction
@app.route('/admin/api/end_auction', methods=['POST'])
def admin_end_auction():
    # Check if user is admin
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    # Get data from request
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request data'}), 400

    auction_id = data.get('auction_id')
    auction_type = data.get('auction_type')

    if not auction_id or not auction_type or auction_type not in ['normal', 'mortgage']:
        return jsonify({'success': False, 'error': 'Missing or invalid auction ID or type'}), 400

    try:
        # Connect to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        table_name = "normal_products" if auction_type == "normal" else "mortgage_products"
        
        # Update end date to current time to effectively end the auction
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(f"UPDATE {table_name} SET end_date = %s WHERE id = %s", (current_time, auction_id))
        
        # Commit the changes
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Auction ended successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API routes
@app.route('/api/products')
def api_products():
    product_type = request.args.get('type', 'all')
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if product_type == 'all':
            cursor.execute('SELECT *, "normal" as type FROM normal_products')
            normal_products_list = cursor.fetchall()
            cursor.execute('SELECT *, "mortgage" as type FROM mortgage_products')
            mortgage_products_list = cursor.fetchall()
            products = normal_products_list + mortgage_products_list
        elif product_type == 'normal':
            cursor.execute('SELECT *, "normal" as type FROM normal_products')
            products = cursor.fetchall()
        elif product_type == 'mortgage':
            cursor.execute('SELECT *, "mortgage" as type FROM mortgage_products')
            products = cursor.fetchall()
        else:
            products = []
            
        # Process each product to add images_list
        for product in products:
            if product and product.get('image'):
                product['images_list'] = [img.strip() for img in product['image'].split(',') if img.strip()]
            else:
                product['images_list'] = []
        
        cursor.close()
        conn.close()
        return jsonify(products)
    except Exception as e:
        return jsonify({'error': 'Database error'}), 500

@app.route('/api/products/<int:id>')
def api_product(id):
    product_type = request.args.get('type', 'normal')
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if product_type == 'normal':
            # Explicitly handle normal products with detailed fields
            cursor.execute('''
                SELECT 
                    id, 
                    name, 
                    description, 
                    image,
                    starting_price, 
                    current_bid, 
                    end_date, 
                    status,
                    'normal' as type
                FROM normal_products 
                WHERE id = %s
            ''', (id,))
            product = cursor.fetchone()
        else:
            cursor.execute('SELECT *, "mortgage" as type FROM mortgage_products WHERE id = %s', (id,))
            product = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if product:
            # Process product to add images_list
            if product.get('image'):
                product['images_list'] = [img.strip() for img in product['image'].split(',') if img.strip()]
                # Make sure there's always at least one image
                if not product['images_list']:
                    product['images_list'] = ['default_product.jpg']
            else:
                product['images_list'] = ['default_product.jpg']
                
            # Ensure current_bid is never None
            if product['current_bid'] is None:
                product['current_bid'] = product['starting_price']
                
            return jsonify(product)
        else:
            return jsonify({'error': 'Product not found', 'id': id, 'type': product_type}), 404
    except Exception as e:
        print(f"Error in api_product: {str(e)}")
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/bid', methods=['POST'])
def api_bid():
    if 'user' not in session:
        return jsonify({'error': 'You must be logged in to bid'}), 401
    
    try:
        data = request.get_json()
        product_id = int(data.get('product_id'))
        amount = float(data.get('amount', 0))
        product_type = data.get('type', 'normal')
        
        # Validate basic input
        if product_id <= 0:
            return jsonify({'error': 'Invalid product ID'}), 400
            
        if amount <= 0:
            return jsonify({'error': 'Bid amount must be positive'}), 400
            
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get user ID
        cursor.execute('SELECT id FROM users WHERE email = %s', (session['user'],))
        user = cursor.fetchone()
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'error': 'User not found'}), 404
            
        user_id = user['id']
        
        # Get the product details with explicit type conversion
        if product_type == 'normal':
            cursor.execute('''
                SELECT 
                    id, 
                    name, 
                    description, 
                    COALESCE(current_bid, starting_price) as current_bid,
                    starting_price,
                    status
                FROM normal_products 
                WHERE id = %s
            ''', (product_id,))
            product = cursor.fetchone()
        else:
            cursor.execute('''
                SELECT 
                    id, 
                    name, 
                    description, 
                    COALESCE(current_bid, starting_price) as current_bid,
                    starting_price,
                    status
                FROM mortgage_products 
                WHERE id = %s
            ''', (product_id,))
            product = cursor.fetchone()
            
        if not product:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Product not found', 'id': product_id, 'type': product_type}), 404
        
        # Convert bid amounts to float for comparison
        current_bid = float(product['current_bid']) if product['current_bid'] is not None else float(product['starting_price'])
        
        # Print debugging info
        print(f"Bid attempt - Product: {product_id}, Type: {product_type}, Current bid: {current_bid}, New bid: {amount}")
            
        # Check if the product is active
        if product['status'] != 'active':
            cursor.close()
            conn.close()
            return jsonify({'error': 'This auction has ended'}), 400
            
        # Validate bid amount
        if amount <= current_bid:
            cursor.close()
            conn.close()
            return jsonify({
                'error': f'Bid must be higher than current bid of ${current_bid}',
                'current_bid': current_bid
            }), 400
            
        # Start a transaction
        cursor.execute('START TRANSACTION')
        
        try:
            # Update product's current bid
            if product_type == 'normal':
                cursor.execute('UPDATE normal_products SET current_bid = %s WHERE id = %s', (amount, product_id))
                
                # Record in product-specific bid table
                cursor.execute(
                    'INSERT INTO normal_bids (user_id, product_id, amount) VALUES (%s, %s, %s)', 
                    (user_id, product_id, amount)
                )
            else:
                cursor.execute('UPDATE mortgage_products SET current_bid = %s WHERE id = %s', (amount, product_id))
                
                # Record in product-specific bid table
                cursor.execute(
                    'INSERT INTO mortgage_bids (user_id, product_id, amount) VALUES (%s, %s, %s)', 
                    (user_id, product_id, amount)
                )
                
            # Record in unified bids table
            cursor.execute(
                'INSERT INTO bids (user_id, product_id, product_type, amount, status) VALUES (%s, %s, %s, %s, %s)',
                (user_id, product_id, product_type, amount, 'active')
            )
            
            # Add activity record if the table exists
            try:
                cursor.execute(
                    'INSERT INTO activity (user_id, activity_type, product_id, product_type, data) VALUES (%s, %s, %s, %s, %s)',
                    (user_id, 'bid', product_id, product_type, json.dumps({'amount': amount, 'product_name': product['name']}))
                )
            except Exception as activity_error:
                print(f"Warning: Could not create activity record: {str(activity_error)}")
                # Continue with the bid even if activity record fails
            
            # Commit the transaction
            cursor.execute('COMMIT')
            
        except Exception as e:
            # Rollback in case of error
            cursor.execute('ROLLBACK')
            cursor.close()
            conn.close()
            return jsonify({'error': f'Transaction error: {str(e)}'}), 500
            
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True, 
            'current_bid': amount,
            'message': 'Bid placed successfully'
        })
        
    except Exception as e:
        print(f"Bid API error: {str(e)}")
        return jsonify({'error': f'Error: {str(e)}'}), 500

@app.route('/admin/users')
def admin_users():
    if 'user' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT id, name, email, role, created_at FROM users ORDER BY created_at DESC')
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('admin/users.html', users=users)
    except Exception as e:
        flash('Database error.')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/users/remove/<int:user_id>', methods=['POST'])
def admin_remove_user(user_id):
    if 'user' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE id = %s AND role != "admin"', (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('User removed successfully.')
    except Exception as e:
        flash('Error removing user.')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/make_admin/<int:user_id>', methods=['POST'])
def admin_make_admin(user_id):
    if 'user' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET role = "admin" WHERE id = %s', (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('User promoted to admin.')
    except Exception as e:
        flash('Error promoting user.')
    return redirect(url_for('admin_users'))

@app.route('/admin/activity')
def admin_activity():
    if 'user' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Get all recent activity (bids, registrations, upgrades, ended auctions)
        cursor.execute('''
            SELECT b.*, u.name as user, p.name as product, "normal" as type FROM normal_bids b
            JOIN users u ON b.user_id = u.id
            JOIN normal_products p ON b.product_id = p.id
            UNION ALL
            SELECT b.*, u.name as user, p.name as product, "mortgage" as type FROM mortgage_bids b
            JOIN users u ON b.user_id = u.id
            JOIN mortgage_products p ON b.product_id = p.id
            ORDER BY bid_time DESC LIMIT 100
        ''')
        recent_bids = cursor.fetchall()
        cursor.execute('SELECT name, email, created_at FROM users ORDER BY created_at DESC LIMIT 100')
        recent_users = cursor.fetchall()
        cursor.execute('SELECT name, email, created_at FROM users WHERE premium = TRUE ORDER BY created_at DESC LIMIT 100')
        recent_premium_upgrades = cursor.fetchall()
        cursor.execute('SELECT name, end_date, current_bid, "normal" as type FROM normal_products WHERE end_date < NOW() ORDER BY end_date DESC LIMIT 100')
        ended_normal = cursor.fetchall()
        cursor.execute('SELECT name, end_date, current_bid, "mortgage" as type FROM mortgage_products WHERE end_date < NOW() ORDER BY end_date DESC LIMIT 100')
        ended_mortgage = cursor.fetchall()
        recent_auctions = ended_normal + ended_mortgage
        recent_auctions = sorted(recent_auctions, key=lambda x: x['end_date'], reverse=True)[:100]
        cursor.close()
        conn.close()
        return render_template('admin/activity.html', recent_bids=recent_bids, recent_users=recent_users, recent_premium_upgrades=recent_premium_upgrades, recent_auctions=recent_auctions)
    except Exception as e:
        flash('Database error.')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/products/view/<int:id>/<type>')
def admin_view_product(id, type):
    if 'user' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if type == 'normal':
            cursor.execute('SELECT * FROM normal_products WHERE id = %s', (id,))
        else:
            cursor.execute('SELECT * FROM mortgage_products WHERE id = %s', (id,))
        product = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not product:
            flash('Product not found.')
            return redirect(url_for('admin_dashboard'))
        
        # Split the image string into a list for the template
        if product and product.get('image'):
            product['images_list'] = [img.strip() for img in product['image'].split(',') if img.strip()]
            # Store the type with the product for convenience in templates
            product['type'] = type
        else:
            product['images_list'] = []
            product['type'] = type
            
        return render_template('admin/view_product.html', product=product)
    except Exception as e:
        flash('Database error.')
        return redirect(url_for('admin_dashboard'))

@app.route('/api/notifications')
def get_notifications():
    if 'user' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get user ID from session
        cursor.execute('SELECT id FROM users WHERE email = %s', (session['user'],))
        user = cursor.fetchone()
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'error': 'User not found'}), 404
        
        user_id = user['id']
        
        # Get unread notification count
        cursor.execute('SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0', (user_id,))
        unread_count = cursor.fetchone()['count']
        
        # Get latest notifications (limit to 10)
        cursor.execute('''
            SELECT id, message, type, is_read, DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s') as created_at
            FROM notifications 
            WHERE user_id = %s
            ORDER BY created_at DESC LIMIT 10
        ''', (user_id,))
        notifications = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'unread_count': unread_count,
            'notifications': notifications
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/notifications/mark-read/<int:notification_id>', methods=['POST'])
def mark_notification_read(notification_id):
    if 'user' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get user ID from session
        cursor.execute('SELECT id FROM users WHERE email = %s', (session['user'],))
        user = cursor.fetchone()
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'error': 'User not found'}), 404
        
        user_id = user['id']
        
        # Mark notification as read (only if it belongs to this user)
        cursor.execute('''
            UPDATE notifications 
            SET is_read = 1 
            WHERE id = %s AND user_id = %s
        ''', (notification_id, user_id))
        
        updated = cursor.rowcount > 0
        conn.commit()
        cursor.close()
        conn.close()
        
        if updated:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Notification not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/watchlist', methods=['POST'])
def api_watchlist():
    if 'user' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        data = request.json
        product_id = int(data.get('product_id', 0))
        product_type = data.get('product_type')
        action = data.get('action')  # 'add' or 'remove'
        
        # Validate basic input
        if product_id <= 0:
            return jsonify({'error': 'Invalid product ID'}), 400
            
        if not product_type or not action:
            return jsonify({'error': 'Missing required parameters'}), 400
            
        if product_type not in ['normal', 'mortgage']:
            return jsonify({'error': 'Invalid product type'}), 400
            
        if action not in ['add', 'remove']:
            return jsonify({'error': 'Invalid action'}), 400
        
        print(f"Watchlist action: {action}, Product ID: {product_id}, Type: {product_type}")
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get user ID
        cursor.execute('SELECT id FROM users WHERE email = %s', (session['user'],))
        user = cursor.fetchone()
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'error': 'User not found'}), 404
        
        user_id = user['id']
        
        # Get product details for activity record
        product_name = ""
        if product_type == 'normal':
            cursor.execute('SELECT id, name FROM normal_products WHERE id = %s', (product_id,))
            product = cursor.fetchone()
        else:
            cursor.execute('SELECT id, name FROM mortgage_products WHERE id = %s', (product_id,))
            product = cursor.fetchone()
            
        if not product:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Product not found', 'id': product_id, 'type': product_type}), 404
            
        product_name = product['name']
        
        # Begin transaction
        cursor.execute('START TRANSACTION')
        
        try:
            if action == 'add':
                # Check if already in watchlist
                cursor.execute(
                    'SELECT id FROM watchlist WHERE user_id = %s AND product_id = %s AND product_type = %s',
                    (user_id, product_id, product_type)
                )
                
                if cursor.fetchone():
                    cursor.execute('ROLLBACK')
                    cursor.close()
                    conn.close()
                    return jsonify({'success': True, 'message': 'Already in watchlist'}), 200
                    
                # Add to watchlist
                cursor.execute(
                    'INSERT INTO watchlist (user_id, product_id, product_type) VALUES (%s, %s, %s)',
                    (user_id, product_id, product_type)
                )
                
                # Add activity record if the table exists
                try:
                    cursor.execute(
                        'INSERT INTO activity (user_id, activity_type, product_id, product_type, data) VALUES (%s, %s, %s, %s, %s)',
                        (user_id, 'watch', product_id, product_type, json.dumps({'product_name': product_name}))
                    )
                except Exception as activity_error:
                    print(f"Warning: Could not create activity record: {str(activity_error)}")
                    # Continue with the watchlist even if activity record fails
                
                message = 'Added to watchlist'
                
            else:  # remove
                # Remove from watchlist
                cursor.execute(
                    'DELETE FROM watchlist WHERE user_id = %s AND product_id = %s AND product_type = %s',
                    (user_id, product_id, product_type)
                )
                
                # Add activity record for removal if the table exists
                try:
                    cursor.execute(
                        'INSERT INTO activity (user_id, activity_type, product_id, product_type, data) VALUES (%s, %s, %s, %s, %s)',
                        (user_id, 'unwatch', product_id, product_type, json.dumps({'product_name': product_name}))
                    )
                except Exception as activity_error:
                    print(f"Warning: Could not create activity record: {str(activity_error)}")
                    # Continue with the watchlist even if activity record fails
                
                message = 'Removed from watchlist'
                
            # Commit transaction
            cursor.execute('COMMIT')
            
            # Get current watchlist count
            cursor.execute('SELECT COUNT(*) as count FROM watchlist WHERE user_id = %s', (user_id,))
            watchlist_count = cursor.fetchone()['count']
            
        except Exception as e:
            cursor.execute('ROLLBACK')
            cursor.close()
            conn.close()
            return jsonify({'error': f'Transaction error: {str(e)}'}), 500
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': message,
            'watchlist_count': watchlist_count
        })
        
    except Exception as e:
        print(f"Watchlist API error: {str(e)}")
        return jsonify({'error': f'Error: {str(e)}'}), 500

@app.route('/api/watchlist/status', methods=['GET'])
def api_watchlist_status():
    if 'user' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        try:
            product_id = int(request.args.get('product_id', 0))
        except ValueError:
            return jsonify({'error': 'Invalid product ID format'}), 400
            
        product_type = request.args.get('product_type')
        
        if product_id <= 0:
            return jsonify({'error': 'Invalid product ID'}), 400
            
        if not product_type:
            return jsonify({'error': 'Missing product type parameter'}), 400
            
        if product_type not in ['normal', 'mortgage']:
            return jsonify({'error': 'Invalid product type'}), 400
        
        print(f"Checking watchlist status - Product ID: {product_id}, Type: {product_type}")
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get user ID
        cursor.execute('SELECT id FROM users WHERE email = %s', (session['user'],))
        user = cursor.fetchone()
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'error': 'User not found'}), 404
        
        user_id = user['id']
        
        # Check if product exists
        if product_type == 'normal':
            cursor.execute('SELECT id FROM normal_products WHERE id = %s', (product_id,))
        else:
            cursor.execute('SELECT id FROM mortgage_products WHERE id = %s', (product_id,))
            
        product = cursor.fetchone()
        if not product:
            cursor.close()
            conn.close()
            return jsonify({
                'error': 'Product not found',
                'id': product_id, 
                'type': product_type,
                'in_watchlist': False
            }), 200  # Return 200 with in_watchlist false instead of 404
        
        # Check if in watchlist
        cursor.execute(
            'SELECT id FROM watchlist WHERE user_id = %s AND product_id = %s AND product_type = %s',
            (user_id, product_id, product_type)
        )
        
        is_in_watchlist = cursor.fetchone() is not None
        cursor.close()
        conn.close()
        
        return jsonify({
            'in_watchlist': is_in_watchlist,
            'product_id': product_id,
            'product_type': product_type
        })
        
    except Exception as e:
        print(f"Watchlist status API error: {str(e)}")
        return jsonify({'error': f'Error checking watchlist status: {str(e)}'}), 500

# --- Forgot Password Routes --- 

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Find user by email
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            
            if user:
                user_id = user['id']
                # Generate a secure token
                token = secrets.token_urlsafe(32)
                # Set expiry time (e.g., 1 hour from now)
                expires_at = datetime.now() + timedelta(hours=1)
                
                # Store the token in the database
                cursor.execute("INSERT INTO password_resets (user_id, token, expires_at) VALUES (%s, %s, %s)",
                               (user_id, token, expires_at))
                conn.commit()
                
                # *** Email Sending Placeholder ***
                # In a real application, you would send an email here.
                # Example link:
                reset_link = url_for('reset_password', token=token, _external=True)
                print(f"Password reset link for {email} (user_id: {user_id}): {reset_link}") # Print link for testing
                # send_password_reset_email(email, reset_link) # Call your email function
                # **********************************
                
                flash(f'If an account exists for {email}, a password reset link has been sent (check console for testing).', 'info')
                return redirect(url_for('login'))
            else:
                # Still show the same message to prevent email enumeration
                flash('If an account exists for your email, a password reset link has been sent.', 'info')
                return redirect(url_for('login'))
                
        except Error as db_error:
            print(f"Database error in forgot_password: {str(db_error)}")
            flash('An error occurred processing your request.', 'error')
        except Exception as e:
            print(f"Error in forgot_password: {str(e)}")
            flash('An unexpected error occurred.', 'error')
        finally:
            if cursor: cursor.close()
            if conn: conn.close()
            
        # If error occurred, re-render the forgot password page
        return render_template('forgot_password.html')
        
    # Handle GET request
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Find user_id associated with the token and check expiry
        cursor.execute("SELECT user_id, expires_at FROM password_resets WHERE token = %s", (token,))
        reset_request = cursor.fetchone()
        
        if not reset_request or reset_request['expires_at'] < datetime.now():
            flash('Invalid or expired password reset token.', 'error')
            return redirect(url_for('forgot_password'))
            
        user_id = reset_request['user_id']
        
        if request.method == 'POST':
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            
            # Validate passwords
            if not password or not confirm_password:
                flash('Please enter and confirm your new password.', 'error')
                return render_template('reset_password.html', token=token)
                
            if password != confirm_password:
                flash('Passwords do not match.', 'error')
                return render_template('reset_password.html', token=token)
                
            if len(password) < 8:
                flash('Password must be at least 8 characters long.', 'error')
                return render_template('reset_password.html', token=token)
                
            # Hash the new password
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Update user's password
            cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (hashed_password, user_id))
            
            # Delete the used token
            cursor.execute("DELETE FROM password_resets WHERE token = %s", (token,))
            
            conn.commit()
            
            flash('Your password has been successfully reset. Please login.', 'success')
            return redirect(url_for('login'))
            
        # Handle GET request (show the form)
        return render_template('reset_password.html', token=token)
        
    except Error as db_error:
        print(f"Database error in reset_password: {str(db_error)}")
        flash('An error occurred processing your request.', 'error')
        return redirect(url_for('forgot_password'))
    except Exception as e:
        print(f"Error in reset_password: {str(e)}")
        flash('An unexpected error occurred.', 'error')
        return redirect(url_for('forgot_password'))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

if __name__ == '__main__':
    app.run(debug=True) 