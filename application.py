from cs50 import SQL, eprint
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp
from werkzeug.security import generate_password_hash, check_password_hash

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    testing = db.execute("SELECT portfolio.symbol, portfolio.price, SUM(portfolio.shares) AS sum FROM portfolio WHERE id = :i GROUP BY portfolio.symbol", i = session["user_id"])
    cash = db.execute("SELECT cash FROM users WHERE id = :i", i =  session["user_id"])
    return render_template("index.html", testing = testing, cash = cash)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method == "POST":
        if not request.form.get("stock"):
            return apology("Enter a symbol for a stock")

        if not request.form.get("amount"):
            return apology("Enter a number of shares")

        stock = lookup(request.form.get("stock"))
        if stock == None:
            return apology("Not valid stock")
        else:
            cash = db.execute("SELECT cash FROM users WHERE id = :i", i =  session["user_id"])

            if int(request.form.get('amount')) <= 0:
                return apology("Enter a positive number to buy")

            if int(request.form.get('amount'))*stock['price'] > cash[0]['cash']:
                return apology("You don't have enough money to purchas this much")

            db.execute("UPDATE users SET cash = cash - :c WHERE id = :i", c = int(request.form.get('amount')) * stock['price'], i = session["user_id"])
            purchase = db.execute("INSERT INTO portfolio (symbol, shares, price, id) VALUES (:sy, :sh, :p, :i)",
            sy = stock['symbol'], sh = int(request.form.get('amount')), p = stock['price'], i = session["user_id"])

            if not purchase:
                return apology("didn't purchase succesfully")

            return redirect(url_for("index"))
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    portfolio = db.execute("SELECT portfolio.symbol, portfolio.price, portfolio.shares, portfolio.transacted FROM portfolio WHERE id = :i", i = session["user_id"])
    return render_template("history.html", portfolio = portfolio)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        passHash = generate_password_hash(request.form.get("password"), method = 'pbkdf2:sha256', salt_length = 8)
        # ensure username exists and password is correct

        # if len(rows) != 1 or not check_password_hash(passHash, rows[0]["hash"]):
        #     return apology(str(passHash))

        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology(str(passHash))

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        if not request.form.get("stock"):
            return apology("Enter a symbol for a stock")
        stock = lookup(request.form.get("stock"))
        if stock == None:
            return apology("Not valid stock")
        else:
            return render_template("quoteInfo.html", stock = stock)
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():

    """Register user."""
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("Missing")

        elif not request.form.get("password"):
            return apology("Missing password")

        if request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords do not match")

        #generate_password_hash
        passHash = generate_password_hash(request.form.get("password"), method = 'pbkdf2:sha256', salt_length = 8)
        result = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username = request.form.get("username"), hash = passHash)
        #ensre that the username doesn't exist
        if not result:
            return apology("username already exists")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    # stocks = db.execute("SELECT portfolio.symbol FROM portfolio GROUP BY portfolio.symbol")
    portfolio = db.execute("SELECT portfolio.symbol, SUM(portfolio.shares) AS sum FROM portfolio WHERE id = :i GROUP BY portfolio.symbol", i = session["user_id"])
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("Select Stock to Sell")
        if not request.form.get("shares"):
            return apology("Select Number of Shares to Sell")
        if int(request.form.get("shares")) <= 0:
            return apology("Select valid number of Shares to Sell")

        stockLookUp = lookup(request.form.get("symbol"))
        if stockLookUp == None:
            return apology("Not valid stock")
        numberOfShares = 0
        for i in range(0, len(portfolio)):
            if(request.form.get("symbol") == portfolio[i]["symbol"]):
                numberOfShares = portfolio[i]["sum"]
                break

        if(int(request.form.get("shares")) > numberOfShares):
            return apology("You can't sell that many shares")
        sell = db.execute("INSERT INTO portfolio (symbol, shares, price, id) VALUES (:sy, :sh, :p, :i)",
            sy = stockLookUp["symbol"], sh = -int(request.form.get("shares")), p = stockLookUp["price"], i = session["user_id"])

        db.execute("UPDATE users SET cash = cash + :c WHERE id = :i", c = int(request.form.get("shares")) * stockLookUp['price'], i = session["user_id"])

        return redirect(url_for("index"))
    else:
        return render_template("sell.html", stocks = portfolio)

@app.route("/addCash", methods=["GET", "POST"])
@login_required
def addCash():
    """Add more cash """
    if request.method == "POST":
        if not request.form.get("cash"):
            return apology("Enter Amount of Cash")
        cash = int(request.form.get("cash"))
        if cash <= 0:
            return apology("Enter valid amount of cash")
        db.execute("UPDATE users SET cash = cash + :c WHERE id = :i", c = cash, i = session["user_id"])

        return redirect(url_for("index"))
    else:
        return render_template("addCash.html")