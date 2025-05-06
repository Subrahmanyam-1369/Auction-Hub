# AuctionHub

AuctionHub is a web-based auction platform built with Flask and MySQL. It allows users to browse, bid, and manage auctions for both normal and mortgage products. Admins can manage products, view activity, and oversee the auction process.

## Features
- User registration and login
- Browse and search auctions
- Place bids on products
- Watchlist functionality
- Admin dashboard for managing products and users
- Support for multiple product images
- Unit tests with pytest

## Tech Stack
- Python 3
- Flask
- MySQL
- HTML/CSS (Tailwind)
- JavaScript (jQuery)

## Setup Instructions

### 1. Clone the repository
```bash
git clone <repo-url>
cd Auction-Hub
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables
Create a `.env` file in the root directory with the following:
```
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=yourpassword
MYSQL_DB=auctionhub
SECRET_KEY=your_secret_key
```

### 4. Initialize the database
The app will auto-create tables on first run if they do not exist.

### 5. Run the application
```bash
python app.py
```
Visit [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

## Running Tests
To run unit tests (including endpoint and database tests):
```bash
pytest app_test.py
pytest login_tests.py
```

## Directory Structure
```
Auction-Hub/
├── app.py
├── requirements.txt
├── .env
├── static/
├── templates/
├── app_test.py
├── login_tests.py
└── README.md
```

## License
This project is licensed under the MIT License. 