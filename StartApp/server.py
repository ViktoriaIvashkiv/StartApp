from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
from flask_mysqldb import MySQL
import yaml
import hashlib
import secrets
import os
from datetime import datetime
from functools import wraps
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont

import io
import shutil

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Налаштування бази даних MySQL
db_config = {
    'mysql_host': 'localhost',
    'mysql_user': 'root',
    'mysql_password': 'root2003',
    'mysql_db': 'startup_platform1'
}

app.config['MYSQL_HOST'] = db_config['mysql_host']
app.config['MYSQL_USER'] = db_config['mysql_user']
app.config['MYSQL_PASSWORD'] = db_config['mysql_password']
app.config['MYSQL_DB'] = db_config['mysql_db']
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# Налаштування для завантаження файлів
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/uploads')
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'avi', 'mov', 'mkv'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 МБ максимальний розмір файлу

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

mysql = MySQL(app)

# Функція для створення бази даних, якщо вона не існує
def create_database():
    try:
        # Підключаємось до MySQL сервера без вказування бази даних
        import MySQLdb
        conn = MySQLdb.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            passwd=app.config['MYSQL_PASSWORD']
        )
        cursor = conn.cursor()
        
        # Створюємо базу даних, якщо вона не існує
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {app.config['MYSQL_DB']}")
        
        print(f"База даних '{app.config['MYSQL_DB']}' успішно створена або вже існує.")
        
        # Закриваємо з'єднання
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Помилка при створенні бази даних: {str(e)}")
        return False

# Декоратор для перевірки авторизації
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Будь ласка, увійдіть в систему', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Декоратор для перевірки прав адміністратора
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'admin':
            flash('Доступ заборонено. Необхідні права адміністратора', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Функція для хешування паролів
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Функція для перевірки допустимих розширень файлів
def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

# Створення директорії для завантажень, якщо вона не існує
def ensure_upload_folder_exists():
    folders = [
        app.config['UPLOAD_FOLDER'],
        os.path.join(app.config['UPLOAD_FOLDER'], 'images'),
        os.path.join(app.config['UPLOAD_FOLDER'], 'videos')
    ]
    
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
    
    # Також створити заглушки для відсутніх файлів
    placeholder_dir = os.path.join('static', 'img')
    os.makedirs(placeholder_dir, exist_ok=True)
    
    # Створити зображення-заглушки, якщо вони ще не існують
    image_placeholder = os.path.join(placeholder_dir, 'image-placeholder.jpg')
    video_placeholder = os.path.join(placeholder_dir, 'video-placeholder.jpg')
    
    if not os.path.exists(image_placeholder):
        img = Image.new('RGB', (400, 300), color=(200, 200, 200))
        draw = ImageDraw.Draw(img)
        try:
            # Try to use a system font that supports Cyrillic (this may vary by system)
            # On Windows, you might use "Arial" or "Segoe UI"
            # On Linux, you might use "DejaVu Sans" or "Ubuntu"
            font = ImageFont.truetype("Arial", 20)  # Try a common font that supports Cyrillic
            draw.text((150, 150), "Зображення недоступне", font=font, fill=(0, 0, 0))
        except Exception:
            # Fallback to English if the font doesn't work
            draw.text((150, 150), "Image not available", fill=(0, 0, 0))
        img.save(image_placeholder, 'JPEG')
    
    if not os.path.exists(video_placeholder):
        img = Image.new('RGB', (640, 360), color=(50, 50, 50))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("Arial", 20)  # Try a common font that supports Cyrillic
            draw.text((280, 180), "Відео недоступне", font=font, fill=(255, 255, 255))
        except Exception:
            # Fallback to English
            draw.text((280, 180), "Video not available", fill=(255, 255, 255))
        img.save(video_placeholder, 'JPEG')

# Функція для збереження файлу
def save_file(file, file_type):
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    unique_filename = f"{timestamp}_{filename}"
    
    subfolder = 'images' if file_type == 'image' else 'videos'
    # Використовуємо os.path.join для коректного формування шляху
    file_path = os.path.join(subfolder, unique_filename).replace('\\', '/')
    
    ensure_upload_folder_exists()
    # Зберігаємо файл з правильним шляхом
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], subfolder, unique_filename)
    file.save(save_path)
    
    return unique_filename, file_path

def create_placeholder_for_media(file_type, file_path):
    """Створює заглушку для медіа файлу"""
    full_path = os.path.join(app.config['UPLOAD_FOLDER'], file_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    if file_type == 'image':
        img = Image.new('RGB', (600, 400), color=(
            random.randint(100, 200),
            random.randint(100, 200),
            random.randint(100, 200)
        ))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("Arial", 20)  # Try a common font that supports Cyrillic
            draw.text((250, 200), "Зразок зображення", font=font, fill=(0, 0, 0))
        except Exception:
            draw.text((250, 200), "Sample Image", fill=(0, 0, 0))
        img.save(full_path, 'JPEG')
    else:  # video
        # Для відео створимо текстовий файл як заглушку
        with open(full_path, 'w') as f:
            f.write("Це заглушка для відео. У реальному додатку тут було б відео.")
        
        # Також створюємо мініатюру-заглушку для відео
        thumb_path = full_path.replace(os.path.splitext(full_path)[1], '.jpg')
        img = Image.new('RGB', (640, 360), color=(50, 50, 50))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("Arial", 20)  # Try a common font that supports Cyrillic
            draw.text((280, 180), "Заглушка відео", font=font, fill=(255, 255, 255))
        except Exception:
            draw.text((280, 180), "Video Placeholder", fill=(255, 255, 255))
        img.save(thumb_path, 'JPEG')

def initialize_database():
    cur = mysql.connection.cursor()
    
    # Створення таблиці користувачів
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            full_name VARCHAR(255),
            bio TEXT,
            city VARCHAR(100),
            country VARCHAR(100),
            latitude DECIMAL(10, 8) NULL,
            longitude DECIMAL(11, 8) NULL,
            role ENUM('user', 'admin') DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Створення таблиці ідей (проектів)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS ideas (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            user_id INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Створення таблиці коментарів
    cur.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            idea_id INT NOT NULL,
            user_id INT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (idea_id) REFERENCES ideas(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Створення таблиці для приватних повідомлень
    cur.execute('''
        CREATE TABLE IF NOT EXISTS private_messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            sender_id INT NOT NULL,
            receiver_id INT NOT NULL,
            content TEXT NOT NULL,
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Створення таблиці для медіа-файлів
    cur.execute('''
        CREATE TABLE IF NOT EXISTS media_files (
            id INT AUTO_INCREMENT PRIMARY KEY,
            idea_id INT NOT NULL,
            user_id INT NOT NULL,
            file_name VARCHAR(255) NOT NULL,
            file_path VARCHAR(255) NOT NULL,
            file_type ENUM('image', 'video') NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (idea_id) REFERENCES ideas(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Перевірка наявності адміністратора, якщо немає - створюємо
    cur.execute("SELECT * FROM users WHERE role = 'admin'")
    admin = cur.fetchone()
    
    if not admin:
        admin_password = hash_password('admin')
        cur.execute("INSERT INTO users (username, email, password, full_name, role) VALUES (%s, %s, %s, %s, %s)",
                    ('admin', 'admin@startupplatform.ua', admin_password, 'Адміністратор системи', 'admin'))
    
    mysql.connection.commit()
    cur.close()

# Маршрут для ініціалізації бази даних
@app.route('/init-db')
def init_db_route():
    try:
        initialize_database()
        return 'База даних успішно ініціалізована!'
    except Exception as e:
        return f'Помилка при ініціалізації бази даних: {str(e)}'

# Головна сторінка
@app.route('/')
def index():
    cur = mysql.connection.cursor()
    cur.execute('''
        SELECT ideas.id, ideas.title, ideas.description, ideas.created_at, 
               users.username, users.full_name, users.city, users.country,
               COUNT(comments.id) as comment_count,
               (SELECT COUNT(*) FROM media_files WHERE media_files.idea_id = ideas.id) as media_count
        FROM ideas 
        JOIN users ON ideas.user_id = users.id 
        LEFT JOIN comments ON ideas.id = comments.idea_id 
        GROUP BY ideas.id 
        ORDER BY ideas.created_at DESC
    ''')
    ideas = cur.fetchall()
    cur.close()
    return render_template('index.html', ideas=ideas)

# Реєстрація
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        full_name = request.form['full_name']
        city = request.form.get('city', '')
        country = request.form.get('country', '')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        role = 'user'  # За замовчуванням роль користувача
        
        # Перевірка паролю
        if password != confirm_password:
            flash('Паролі не співпадають', 'danger')
            return redirect(url_for('register'))
        
        # Хешування паролю
        hashed_password = hash_password(password)
        
        # Перевірка чи користувач вже існує
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, email))
        user = cur.fetchone()
        
        if user:
            flash('Користувач з таким іменем або email вже існує', 'danger')
            cur.close()
            return redirect(url_for('register'))
            
        # Створення нового користувача
        cur.execute("""
            INSERT INTO users 
            (username, email, password, full_name, city, country, latitude, longitude, role) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (username, email, hashed_password, full_name, city, country, latitude, longitude, role))
        mysql.connection.commit()
        cur.close()
        
        flash('Ви успішно зареєструвалися! Тепер ви можете увійти', 'success')
        return redirect(url_for('login'))
        
    return render_template('client.html', action='register')

# Логін
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        hashed_password = hash_password(password)
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", [username])
        user = cur.fetchone()
        cur.close()
        
        if user and user['password'] == hashed_password:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            flash(f'Вітаємо, {user["username"]}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Невірне ім\'я користувача або пароль', 'danger')
            return redirect(url_for('login'))
    
    return render_template('client.html', action='login')

# Вихід
@app.route('/logout')
def logout():
    session.clear()
    flash('Ви вийшли з системи', 'success')
    return redirect(url_for('index'))

# Профіль користувача
@app.route('/profile/<username>')
def profile(username):
    cur = mysql.connection.cursor()
    
    # Отримання даних користувача
    cur.execute("SELECT * FROM users WHERE username = %s", [username])
    user = cur.fetchone()
    
    if not user:
        flash('Користувач не знайдений', 'danger')
        return redirect(url_for('index'))
    
    # Отримання ідей користувача
    cur.execute('''
        SELECT ideas.*, 
               COUNT(DISTINCT comments.id) as comment_count,
               COUNT(DISTINCT media_files.id) as media_count
        FROM ideas 
        LEFT JOIN comments ON ideas.id = comments.idea_id 
        LEFT JOIN media_files ON ideas.id = media_files.idea_id
        WHERE ideas.user_id = %s 
        GROUP BY ideas.id 
        ORDER BY ideas.created_at DESC
    ''', [user['id']])
    ideas = cur.fetchall()
    
    cur.close()
    return render_template('client.html', action='profile', user=user, ideas=ideas)

# Редагування профілю
@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        bio = request.form['bio']
        city = request.form.get('city', '')
        country = request.form.get('country', '')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        
        cur = mysql.connection.cursor()
        
        # Перевірка email на унікальність
        cur.execute("SELECT * FROM users WHERE email = %s AND id != %s", (email, session['user_id']))
        existing_user = cur.fetchone()
        
        if existing_user:
            flash('Цей email вже використовується', 'danger')
            return redirect(url_for('edit_profile'))
        
        # Оновлення профілю
        cur.execute("""
            UPDATE users 
            SET full_name = %s, email = %s, bio = %s, city = %s, country = %s, latitude = %s, longitude = %s 
            WHERE id = %s
        """, (full_name, email, bio, city, country, latitude, longitude, session['user_id']))
        mysql.connection.commit()
        cur.close()
        
        flash('Профіль успішно оновлено', 'success')
        return redirect(url_for('profile', username=session['username']))
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", [session['user_id']])
    user = cur.fetchone()
    cur.close()
    
    return render_template('client.html', action='edit_profile', user=user)

# Зміна паролю
@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form['current_password']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']
    
    # Перевірка нового паролю
    if new_password != confirm_password:
        flash('Нові паролі не співпадають', 'danger')
        return redirect(url_for('edit_profile'))
    
    # Перевірка поточного паролю
    cur = mysql.connection.cursor()
    cur.execute("SELECT password FROM users WHERE id = %s", [session['user_id']])
    user = cur.fetchone()
    
    if hash_password(current_password) != user['password']:
        flash('Поточний пароль невірний', 'danger')
        cur.close()
        return redirect(url_for('edit_profile'))
    
    # Оновлення паролю
    cur.execute("UPDATE users SET password = %s WHERE id = %s",
               (hash_password(new_password), session['user_id']))
    mysql.connection.commit()
    cur.close()
    
    flash('Пароль успішно змінено', 'success')
    return redirect(url_for('profile', username=session['username']))

# Створення нової ідеї (проекту)
@app.route('/idea/create', methods=['GET', 'POST'])
@login_required
def create_idea():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        
        # Створення нової ідеї
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO ideas (title, description, user_id) VALUES (%s, %s, %s)",
                  (title, description, session['user_id']))
        mysql.connection.commit()
        idea_id = cur.lastrowid
        
        # Обробка завантажених файлів
        uploaded_files = request.files.getlist('media_files')
        
        for file in uploaded_files:
            if file and file.filename:
                if allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
                    file_type = 'image'
                elif allowed_file(file.filename, ALLOWED_VIDEO_EXTENSIONS):
                    file_type = 'video'
                else:
                    continue  # Пропускаємо файли з непідтримуваними розширеннями
                
                unique_filename, file_path = save_file(file, file_type)
                
                # Зберігаємо інформацію про файл у базу даних
                cur.execute("""
                    INSERT INTO media_files (idea_id, user_id, file_name, file_path, file_type) 
                    VALUES (%s, %s, %s, %s, %s)
                """, (idea_id, session['user_id'], unique_filename, file_path, file_type))
                mysql.connection.commit()
        
        cur.close()
        
        flash('Ідея успішно створена', 'success')
        return redirect(url_for('view_idea', idea_id=idea_id))
    
    return render_template('client.html', action='create_idea')

# Перегляд ідеї (проекту)
@app.route('/idea/<int:idea_id>')
def view_idea(idea_id):
    cur = mysql.connection.cursor()
    
    # Отримання ідеї
    cur.execute('''
        SELECT ideas.*, users.username, users.full_name, users.city, users.country 
        FROM ideas 
        JOIN users ON ideas.user_id = users.id 
        WHERE ideas.id = %s
    ''', [idea_id])
    idea = cur.fetchone()
    
    if not idea:
        flash('Ідея не знайдена', 'danger')
        return redirect(url_for('index'))
    
    # Отримання коментарів
    cur.execute('''
        SELECT comments.*, users.username, users.full_name, users.city, users.country 
        FROM comments 
        JOIN users ON comments.user_id = users.id 
        WHERE comments.idea_id = %s 
        ORDER BY comments.created_at
    ''', [idea_id])
    comments = cur.fetchall()
    
    # Отримання медіа-файлів
    cur.execute('''
        SELECT * FROM media_files
        WHERE idea_id = %s
        ORDER BY created_at, file_type
    ''', [idea_id])
    media_files = cur.fetchall()
    
    # Перевірка і створення заглушок для медіа-файлів, які не існують
    for media in media_files:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], media['file_path'])
        if not os.path.exists(file_path):
            create_placeholder_for_media(media['file_type'], media['file_path'])
    
    cur.close()
    return render_template('client.html', action='view_idea', idea=idea, comments=comments, media_files=media_files)

# Редагування ідеї (проекту)
@app.route('/idea/<int:idea_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_idea(idea_id):
    cur = mysql.connection.cursor()
    
    # Перевірка власника ідеї
    cur.execute("SELECT * FROM ideas WHERE id = %s", [idea_id])
    idea = cur.fetchone()
    
    if not idea:
        flash('Ідея не знайдена', 'danger')
        cur.close()
        return redirect(url_for('index'))
    
    # Перевірка прав на редагування
    if idea['user_id'] != session['user_id'] and session['role'] != 'admin':
        flash('У вас немає прав для редагування цієї ідеї', 'danger')
        cur.close()
        return redirect(url_for('view_idea', idea_id=idea_id))
    
    # Отримуємо поточні медіа-файли ідеї
    cur.execute("SELECT * FROM media_files WHERE idea_id = %s", [idea_id])
    media_files = cur.fetchall()
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        
        # Оновлення ідеї
        cur.execute("UPDATE ideas SET title = %s, description = %s WHERE id = %s",
                  (title, description, idea_id))
        mysql.connection.commit()
        
        # Обробка нових завантажених файлів
        uploaded_files = request.files.getlist('media_files')
        
        for file in uploaded_files:
            if file and file.filename:
                if allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
                    file_type = 'image'
                elif allowed_file(file.filename, ALLOWED_VIDEO_EXTENSIONS):
                    file_type = 'video'
                else:
                    continue  # Пропускаємо файли з непідтримуваними розширеннями
                
                unique_filename, file_path = save_file(file, file_type)
                
                # Зберігаємо інформацію про файл у базу даних
                cur.execute("""
                    INSERT INTO media_files (idea_id, user_id, file_name, file_path, file_type) 
                    VALUES (%s, %s, %s, %s, %s)
                """, (idea_id, session['user_id'], unique_filename, file_path, file_type))
                mysql.connection.commit()
        
        # Видалення файлів, відмічених для видалення
        files_to_delete = request.form.getlist('delete_file')
        for file_id in files_to_delete:
            # Отримання інформації про файл перед видаленням
            cur.execute("SELECT file_path FROM media_files WHERE id = %s", [file_id])
            file_info = cur.fetchone()
            
            if file_info:
                # Видалення файлу з файлової системи
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_info['file_path'])
                if os.path.exists(file_path):
                    os.remove(file_path)
                
                # Видалення запису з бази даних
                cur.execute("DELETE FROM media_files WHERE id = %s", [file_id])
                mysql.connection.commit()
        
        cur.close()
        
        flash('Ідея успішно оновлена', 'success')
        return redirect(url_for('view_idea', idea_id=idea_id))
    
    cur.close()
    return render_template('client.html', action='edit_idea', idea=idea, media_files=media_files)

# Видалення ідеї (проекту)
@app.route('/idea/<int:idea_id>/delete', methods=['POST'])
@login_required
def delete_idea(idea_id):
    cur = mysql.connection.cursor()
    
    # Перевірка власника ідеї
    cur.execute("SELECT * FROM ideas WHERE id = %s", [idea_id])
    idea = cur.fetchone()
    
    if not idea:
        flash('Ідея не знайдена', 'danger')
        cur.close()
        return redirect(url_for('index'))
    
    # Перевірка прав на видалення
    if idea['user_id'] != session['user_id'] and session['role'] != 'admin':
        flash('У вас немає прав для видалення цієї ідеї', 'danger')
        cur.close()
        return redirect(url_for('view_idea', idea_id=idea_id))
    
    # Отримуємо всі медіа-файли ідеї для видалення
    cur.execute("SELECT file_path FROM media_files WHERE idea_id = %s", [idea_id])
    media_files = cur.fetchall()
    
    # Видаляємо фізичні файли
    for file in media_files:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file['file_path'])
        if os.path.exists(file_path):
            os.remove(file_path)
    
    # Видалення ідеї (каскадно видалить коментарі та записи про медіа-файли)
    cur.execute("DELETE FROM ideas WHERE id = %s", [idea_id])
    mysql.connection.commit()
    cur.close()
    
    flash('Ідея успішно видалена', 'success')
    return redirect(url_for('index'))

# Додавання коментаря
@app.route('/idea/<int:idea_id>/comment', methods=['POST'])
@login_required
def add_comment(idea_id):
    content = request.form['content']
    
    cur = mysql.connection.cursor()
    
    # Перевірка існування ідеї
    cur.execute("SELECT * FROM ideas WHERE id = %s", [idea_id])
    idea = cur.fetchone()
    
    if not idea:
        flash('Ідея не знайдена', 'danger')
        cur.close()
        return redirect(url_for('index'))
    
    # Додавання коментаря
    cur.execute("INSERT INTO comments (idea_id, user_id, content) VALUES (%s, %s, %s)",
               (idea_id, session['user_id'], content))
    mysql.connection.commit()
    cur.close()
    
    flash('Коментар додано', 'success')
    return redirect(url_for('view_idea', idea_id=idea_id))

# Видалення коментаря
@app.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    cur = mysql.connection.cursor()
    
    # Отримання коментаря
    cur.execute('''
        SELECT comments.*, ideas.id as idea_id 
        FROM comments 
        JOIN ideas ON comments.idea_id = ideas.id 
        WHERE comments.id = %s
    ''', [comment_id])
    comment = cur.fetchone()
    
    if not comment:
        flash('Коментар не знайдений', 'danger')
        cur.close()
        return redirect(url_for('index'))
    
    # Перевірка прав на видалення
    if comment['user_id'] != session['user_id'] and session['role'] != 'admin':
        flash('У вас немає прав для видалення цього коментаря', 'danger')
        cur.close()
        return redirect(url_for('view_idea', idea_id=comment['idea_id']))
    
    # Видалення коментаря
    cur.execute("DELETE FROM comments WHERE id = %s", [comment_id])
    mysql.connection.commit()
    cur.close()
    
    flash('Коментар видалено', 'success')
    return redirect(url_for('view_idea', idea_id=comment['idea_id']))

# Маршрут для пошуку користувачів за геолокацією
@app.route('/find_nearby_users', methods=['GET', 'POST'])
@login_required
def find_nearby_users():
    if request.method == 'POST':
        city = request.form.get('city', '')
        country = request.form.get('country', '')
        
        cur = mysql.connection.cursor()
        
        # Пошук за містом і країною
        query = """
            SELECT id, username, full_name, city, country, bio, latitude, longitude 
            FROM users 
            WHERE id != %s AND role = 'user'
        """
        params = [session['user_id']]
        
        if city:
            query += " AND city LIKE %s"
            params.append(f"%{city}%")
        
        if country:
            query += " AND country LIKE %s"
            params.append(f"%{country}%")
        
        cur.execute(query, params)
        nearby_users = cur.fetchall()
        cur.close()
        
        return render_template('client.html', action='find_nearby_users', users=nearby_users, search_city=city, search_country=country)
    
    return render_template('client.html', action='find_nearby_users', users=[])

# Маршрут для відображення медіа-файлу
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    try:
        # Замінюємо зворотні слеші на прямі для забезпечення кросплатформної сумісності
        filename = filename.replace('\\', '/')
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except FileNotFoundError:
        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
            return send_from_directory('static/img', 'image-placeholder.jpg')
        elif filename.lower().endswith(('.mp4', '.webm', '.avi', '.mov', '.mkv')):
            return send_from_directory('static/img', 'video-placeholder.jpg')
        return 'Файл не знайдено', 404

# Маршрут для списку всіх чатів користувача
@app.route('/messages')
@login_required
def messages():
    cur = mysql.connection.cursor()
    
    # Отримання всіх контактів з останніми повідомленнями
    cur.execute("""
        SELECT u.id, u.username, u.full_name,
               (SELECT content FROM private_messages 
                WHERE (sender_id = %s AND receiver_id = u.id) OR (sender_id = u.id AND receiver_id = %s) 
                ORDER BY created_at DESC LIMIT 1) as last_message,
               (SELECT created_at FROM private_messages 
                WHERE (sender_id = %s AND receiver_id = u.id) OR (sender_id = u.id AND receiver_id = %s) 
                ORDER BY created_at DESC LIMIT 1) as last_message_time,
               (SELECT COUNT(*) FROM private_messages 
                WHERE sender_id = u.id AND receiver_id = %s AND is_read = 0) as unread_count
        FROM users u
        WHERE u.id IN (
            SELECT sender_id FROM private_messages WHERE receiver_id = %s
            UNION
            SELECT receiver_id FROM private_messages WHERE sender_id = %s
        )
        ORDER BY last_message_time DESC
    """, (session['user_id'], session['user_id'], session['user_id'], session['user_id'], session['user_id'], session['user_id'], session['user_id']))
    
    contacts = cur.fetchall()
    cur.close()
    
    return render_template('client.html', action='messages', contacts=contacts)

# Маршрут для чату з конкретним користувачем
@app.route('/messages/<int:user_id>', methods=['GET', 'POST'])
@login_required
def chat(user_id):
    cur = mysql.connection.cursor()
    
    # Отримуємо інформацію про співрозмовника
    cur.execute("SELECT id, username, full_name FROM users WHERE id = %s", [user_id])
    recipient = cur.fetchone()
    
    if not recipient:
        flash('Користувач не знайдений', 'danger')
        return redirect(url_for('messages'))
    
    # Відправка нового повідомлення
    if request.method == 'POST':
        message_content = request.form['message']
        
        cur.execute("""
            INSERT INTO private_messages (sender_id, receiver_id, content)
            VALUES (%s, %s, %s)
        """, (session['user_id'], user_id, message_content))
        
        mysql.connection.commit()
        
    # Позначка всіх непрочитаних повідомлень як прочитаних
    cur.execute("""
        UPDATE private_messages
        SET is_read = TRUE
        WHERE sender_id = %s AND receiver_id = %s AND is_read = FALSE
    """, (user_id, session['user_id']))
    
    mysql.connection.commit()
    
    # Отримання історії повідомлень
    cur.execute("""
        SELECT pm.*, 
               CASE WHEN pm.sender_id = %s THEN 'outgoing' ELSE 'incoming' END as message_type,
               u.username, u.full_name
        FROM private_messages pm
        JOIN users u ON pm.sender_id = u.id
        WHERE (pm.sender_id = %s AND pm.receiver_id = %s) OR (pm.sender_id = %s AND pm.receiver_id = %s)
        ORDER BY pm.created_at
    """, (session['user_id'], session['user_id'], user_id, user_id, session['user_id']))
    
    messages = cur.fetchall()
    cur.close()
    
    return render_template('client.html', action='chat', recipient=recipient, messages=messages)

# Маршрут для створення нового діалогу
@app.route('/messages/new/<int:user_id>')
@login_required
def new_chat(user_id):
    # Перевіряємо, чи існує користувач
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, username, full_name FROM users WHERE id = %s", [user_id])
    user = cur.fetchone()
    cur.close()
    
    if not user:
        flash('Користувач не знайдений', 'danger')
        return redirect(url_for('index'))
    
    # Перенаправляємо на діалог з цим користувачем
    return redirect(url_for('chat', user_id=user_id))

# API для отримання непрочитаних повідомлень (для сповіщень)
@app.route('/api/unread_message_count')
@login_required
def unread_message_count():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT COUNT(*) as count FROM private_messages
        WHERE receiver_id = %s AND is_read = FALSE
    """, [session['user_id']])
    
    result = cur.fetchone()
    cur.close()
    
    return jsonify({'unread_count': result['count']})

# Адмін панель - список користувачів
@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users ORDER BY created_at DESC")
    users = cur.fetchall()
    cur.close()
    
    return render_template('client.html', action='admin_users', users=users)

# Адмін панель - видалення користувача
@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    # Адмін не може видалити самого себе
    if user_id == session['user_id']:
        flash('Ви не можете видалити власний обліковий запис', 'danger')
        return redirect(url_for('admin_users'))
    
    cur = mysql.connection.cursor()
    
    # Перевірка існування користувача
    cur.execute("SELECT * FROM users WHERE id = %s", [user_id])
    user = cur.fetchone()
    
    if not user:
        flash('Користувач не знайдений', 'danger')
        cur.close()
        return redirect(url_for('admin_users'))
    
    # Видалення користувача
    cur.execute("DELETE FROM users WHERE id = %s", [user_id])
    mysql.connection.commit()
    cur.close()
    
    flash('Користувач видалений', 'success')
    return redirect(url_for('admin_users'))

# Адмін панель - список всіх ідей
@app.route('/admin/ideas')
@login_required
@admin_required
def admin_ideas():
    cur = mysql.connection.cursor()
    cur.execute('''
        SELECT ideas.*, users.username, users.full_name,
               (SELECT COUNT(*) FROM media_files WHERE media_files.idea_id = ideas.id) as media_count
        FROM ideas 
        JOIN users ON ideas.user_id = users.id 
        ORDER BY ideas.created_at DESC
    ''')
    ideas = cur.fetchall()
    cur.close()
    
    return render_template('client.html', action='admin_ideas', ideas=ideas)

# Створення заглушок для медіа-файлів
@app.route('/create-media-placeholders')
@login_required
@admin_required
def create_media_placeholders():
    import random
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, file_path, file_type FROM media_files")
    media_files = cur.fetchall()
    
    count = 0
    for media in media_files:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], media['file_path'])
        if not os.path.exists(file_path):
            create_placeholder_for_media(media['file_type'], media['file_path'])
            count += 1
    
    cur.close()
    
    flash(f'Створено {count} заглушок для медіа-файлів', 'success')
    return redirect(url_for('index'))

# Додамо автоматичну ініціалізацію бази даних при запуску сервера
if __name__ == '__main__':
    # Імпортувати модуль random для генерації випадкових кольорів
    import random
    
    # Спочатку створюємо базу даних, якщо вона не існує
    print("Перевірка бази даних...")
    if create_database():
        # Потім ініціалізуємо таблиці
        with app.app_context():
            try:
                print("Ініціалізація таблиць бази даних...")
                initialize_database()
                print("База даних успішно ініціалізована.")
                
                # Створюємо директорії для медіа-файлів
                ensure_upload_folder_exists()
                print("Директорії для медіа-файлів створені.")
            except Exception as e:
                print(f"Помилка при ініціалізації таблиць бази даних: {str(e)}")
    else:
        print("Не вдалося створити базу даних, перевірте налаштування MySQL.")
    
    app.run(debug=True)