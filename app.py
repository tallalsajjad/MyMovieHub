import os
import re
from cs50 import SQL
from flask import Flask, redirect, render_template, request, session
from flask_session import Session
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash

# Configure application
app = Flask(__name__)
UPLOAD_FOLDER = 'static/profile_pics'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config["MOVIE_POSTERS_FOLDER"] = "static/movie_posters"
app.config["MOVIE_PREVIEW_FOLDER"] = "static/preview_img"

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///site.db")


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
def home():
    movies = db.execute(
        "SELECT title, release_date, preview_img, movie_id FROM movies ORDER BY id DESC")
    return render_template("index.html", movies=movies)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["password"], request.form.get("password")
        ):
            return apology("invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/signup", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == 'GET':
        return render_template("signup.html")
    if request.method == 'POST':
        if not request.form.get("username"):
            return apology("INVALID USERNAME")
        if not request.form.get("password"):
            return apology("INVALID PASSWORD")
        if not request.form.get("confirmation"):
            return apology("Required confirmation")
        if not request.form.get("password") == request.form.get("confirmation"):
            return apology("Check Password")
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if len(rows) > 0:
            return apology("Username already exists.")
        password = request.form.get("password")
        hash_password = generate_password_hash(password)
        result = db.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                            request.form.get("username"), hash_password)
        session["user_id"] = result
        return redirect("/")


@app.route("/profile")
def profile():
    user_id = session["user_id"]
    user = db.execute("""
                      SELECT username, username_timestamp, display_name, profile_pic
                      FROM users WHERE id = ?
                      """, user_id)[0]
    uploads = db.execute(
        "SELECT title, story, release_date, uploaded_at FROM movies WHERE user_id = ?", user_id)
    return render_template("profile.html",
                           name=user["username"],
                           joined_date=user["username_timestamp"],
                           display_name=user["display_name"],
                           profile_pic=user["profile_pic"],
                           uploads=uploads)


@app.route("/update_profile", methods=["POST"])
def update_profile():
    user_id = session["user_id"]
    display_name = request.form.get("display_name")
    username = request.form.get("username")
    old_password = request.form.get("old-password")
    password = request.form.get("password")
    confirm_password = request.form.get("confirm-password")
    if request.method == 'POST':
        if old_password:
            old_password_c = db.execute("SELECT password FROM users WHERE id = ?", user_id)
            old_password_check = check_password_hash(old_password_c)
            if old_password_check != old_password:
                return apology("Incorrect Old Password")
            if password != confirm_password:
                return apology("Check Password")

    if display_name:
        db.execute("UPDATE users SET display_name = ? WHERE id = ?", display_name, user_id)

    if username:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute("UPDATE users SET username = ?, username_timestamp = ? WHERE id = ?",
                   username, timestamp, user_id)

    if password:
        hash_pw = generate_password_hash(password)
        db.execute("UPDATE users SET password = ? WHERE id = ?", hash_pw, user_id)

    return redirect("/profile")


@app.route("/upload_photo", methods=["POST"])
def upload_photo():
    user_id = session["user_id"]
    if "photo" not in request.files:
        return apology("No file part")

    file = request.files["photo"]
    if file.filename == "":
        return apology("No selected file")

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Give it a unique name using user_id
        new_filename = f"user_{user_id}.{filename.rsplit('.', 1)[1].lower()}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], new_filename)
        file.save(filepath)

        # Save file path to DB
        db.execute("UPDATE users SET profile_pic = ? WHERE id = ?", new_filename, user_id)
        return redirect("/profile")

    return apology("Invalid file type")


@app.route("/upload_movie", methods=["GET", "POST"])
def upload_movie():
    if request.method == "GET":
        return render_template("upload.html")
    if request.method == "POST":
        title = request.form.get("title")
        release_date = request.form.get("release_date")
        description = request.form.get("description")
        story = request.form.get("story")
        drive_link = request.form.get("drive_link")
        image = request.files.get("poster")
        preview_image = request.files.get("preview_img")
        user_id = session["user_id"]

        if not (title and release_date and description and story and drive_link and image):
            return apology("All fields required")

        if not allowed_file(image.filename):
            return apology("Invalid image type")
        if not allowed_file(preview_image.filename):
            return apology("Invalid image type")
        if not is_valid_gdrive_link(drive_link):
            return apology("Invalid Google Drive link")

        filename = secure_filename(image.filename)
        poster_filename = f"{user_id}_{filename}"
        filepath = os.path.join(app.config["MOVIE_POSTERS_FOLDER"], poster_filename)
        image.save(filepath)
        file_2 = secure_filename(preview_image.filename)
        preview_img = f"{user_id}_{file_2}"
        filepath_2 = os.path.join(app.config["MOVIE_PREVIEW_FOLDER"], preview_img)
        preview_image.save(filepath_2)
        # Get the current highest movie_id
        if (title and release_date and description and story and drive_link and image):
            row = db.execute("SELECT MAX(movie_id) AS max_id FROM movies")
            last_id = row[0]["max_id"] or 109874
            new_movie_id = last_id + 1

            db.execute("""
                INSERT INTO movies (user_id, title, release_date, description, story, poster_filename, drive_link, preview_img, movie_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       user_id, title, release_date, description, story, poster_filename, drive_link, preview_img, new_movie_id
                       )
            return redirect("/profile")  # Or a page like /movies


@app.route("/movie/<int:movie_id>")
def movie_detail(movie_id):
    movie = db.execute("SELECT * FROM movies WHERE movie_id = ?", movie_id)
    if not movie:
        return apology("Movie not found")
    return render_template("download.html", movie=movie[0])


@app.route("/search")
def search():
    query = request.args.get("q")
    if not query:
        return redirect("/")

    # Search for titles containing the query, case-insensitive
    results = db.execute("SELECT * FROM movies WHERE title LIKE ?", f"%{query}%")
    return render_template("search_results.html", movies=results, query=query)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {"png", "jpg", "jpeg", "gif"}


def apology(message):
    return render_template("apology.html", message=message)


def is_valid_gdrive_link(link):
    return bool(re.match(r"https://drive\.google\.com/(file/d/|open\?id=|uc\?export=download&id=|drive/folders/)[\w-]+", link))


if __name__ == "__main__":
    app.run(debug=True)
