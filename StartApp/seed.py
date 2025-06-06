import mysql.connector
import random
import hashlib
import datetime
from faker import Faker
import os
from pathlib import Path
import shutil

# Налаштування бази даних
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root2003',
    'database': 'startup_platform1'
}

# Ініціалізація Faker для генерації тестових даних
fake = Faker('uk_UA')  # Українська локалізація

# Функція для хешування паролів
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Підготовка директорій для медіа-файлів
def prepare_media_directories():
    base_dir = Path("static/uploads")
    images_dir = base_dir / "images"
    videos_dir = base_dir / "videos"
    
    # Створення директорій, якщо вони не існують
    for dir_path in [base_dir, images_dir, videos_dir]:
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
    
    return images_dir, videos_dir

def generate_test_data():
    try:
        # Підключення до бази даних
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        
        # Підготовка директорій для медіа
        images_dir, videos_dir = prepare_media_directories()
        
        print("Очищення існуючих даних...")
        # Видалення існуючих тестових даних з дотриманням обмежень зовнішніх ключів
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        tables = ["private_messages", "media_files", "comments", "ideas", "users"]
        for table in tables:
            cursor.execute(f"TRUNCATE TABLE {table}")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        
        print("Створення тестових користувачів...")
        # Координати центральної точки (Київ)
        base_latitude = 50.4501
        base_longitude = 30.5234
        
        # Список міст поблизу Києва
        nearby_cities = [
            {"city": "Київ", "country": "Україна"},
            {"city": "Бровари", "country": "Україна"},
            {"city": "Бориспіль", "country": "Україна"},
            {"city": "Ірпінь", "country": "Україна"},
            {"city": "Буча", "country": "Україна"},
            {"city": "Вишневе", "country": "Україна"},
            {"city": "Васильків", "country": "Україна"},
            {"city": "Обухів", "country": "Україна"},
            {"city": "Боярка", "country": "Україна"},
            {"city": "Вишгород", "country": "Україна"}
        ]
        
        # Створення адміністратора, якщо потрібно
        admin_password = hash_password('admin')
        cursor.execute("""
            INSERT INTO users 
            (username, email, password, full_name, city, country, latitude, longitude, role, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, ('admin', 'admin@startupplatform.ua', admin_password, 'Адміністратор системи', 
              'Київ', 'Україна', base_latitude, base_longitude, 'admin', 
              datetime.datetime.now()))
        
        # Генерація 20 звичайних користувачів
        users = []
        for i in range(1, 21):
            username = f"user{i}"
            email = f"user{i}@example.com"
            password = hash_password(f"password{i}")
            full_name = fake.name()
            
            # Вибір випадкового міста поблизу
            location = random.choice(nearby_cities)
            city = location["city"]
            country = location["country"]
            
            # Невелике відхилення від базових координат (в межах приблизно 30 км)
            latitude = base_latitude + random.uniform(-0.15, 0.15)
            longitude = base_longitude + random.uniform(-0.15, 0.15)
            
            bio = fake.text(max_nb_chars=200)
            role = 'user'
            created_at = fake.date_time_between(start_date='-1y', end_date='now')
            
            # Додавання користувача
            cursor.execute("""
                INSERT INTO users 
                (username, email, password, full_name, bio, city, country, latitude, longitude, role, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (username, email, password, full_name, bio, city, country, latitude, longitude, role, created_at))
            
            user_id = cursor.lastrowid
            users.append({
                'id': user_id,
                'username': username,
                'full_name': full_name
            })
        
        print(f"Створено {len(users)} користувачів")
        
        # Генерація 40 ідей (проектів)
        ideas = []
        for i in range(1, 41):
            user = random.choice(users)
            title = fake.sentence(nb_words=6)
            description = fake.text(max_nb_chars=500)
            created_at = fake.date_time_between(start_date='-1y', end_date='now')
            
            # Додавання ідеї
            cursor.execute("""
                INSERT INTO ideas 
                (title, description, user_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (title, description, user['id'], created_at, created_at))
            
            idea_id = cursor.lastrowid
            ideas.append({
                'id': idea_id,
                'title': title,
                'user_id': user['id']
            })
            
            # Додавання 1-5 медіа-файлів до кожної ідеї
            media_count = random.randint(1, 5)
            for j in range(media_count):
                # Визначення типу медіа (90% зображення, 10% відео)
                is_image = random.random() < 0.9
                file_type = 'image' if is_image else 'video'
                
                # Створення унікального імені файлу
                timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                filename = f"{timestamp}_{i}_{j}.{'jpg' if is_image else 'mp4'}"
                
                # Шлях до файлу
                subfolder = 'images' if is_image else 'videos'
                file_path = f"{subfolder}/{filename}"
                
                # Запис у базу даних
                cursor.execute("""
                    INSERT INTO media_files 
                    (idea_id, user_id, file_name, file_path, file_type, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (idea_id, user['id'], filename, file_path, file_type, created_at))
                
                # Примітка: насправді файли не створюються фізично, лише записи в БД
        
        print(f"Створено {len(ideas)} ідей з медіа-файлами")
        
        # Генерація коментарів для ідей
        comments_count = 0
        for idea in ideas:
            # 0-10 коментарів на ідею
            comment_count = random.randint(0, 10)
            for _ in range(comment_count):
                commenter = random.choice(users)
                content = fake.paragraph()
                created_at = fake.date_time_between(start_date='-1y', end_date='now')
                
                cursor.execute("""
                    INSERT INTO comments 
                    (idea_id, user_id, content, created_at)
                    VALUES (%s, %s, %s, %s)
                """, (idea['id'], commenter['id'], content, created_at))
                
                comments_count += 1
        
        print(f"Створено {comments_count} коментарів")
        
        # Генерація приватних повідомлень між користувачами
        messages_count = 0
        # Для кожного користувача створимо 2-5 діалогів
        for user in users:
            # Вибір випадкової кількості діалогів для користувача
            dialog_count = random.randint(2, 5)
            dialog_partners = random.sample(users, min(dialog_count, len(users) - 1))
            
            for partner in dialog_partners:
                if partner['id'] == user['id']:
                    continue  # Пропускаємо діалог з самим собою
                
                # 1-15 повідомлень в кожному діалозі
                message_count = random.randint(1, 15)
                for _ in range(message_count):
                    # Визначення відправника і отримувача
                    if random.random() < 0.5:
                        sender_id = user['id']
                        receiver_id = partner['id']
                    else:
                        sender_id = partner['id']
                        receiver_id = user['id']
                    
                    content = fake.paragraph()
                    created_at = fake.date_time_between(start_date='-3m', end_date='now')
                    is_read = random.random() < 0.8  # 80% повідомлень прочитані
                    
                    cursor.execute("""
                        INSERT INTO private_messages 
                        (sender_id, receiver_id, content, is_read, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (sender_id, receiver_id, content, is_read, created_at))
                    
                    messages_count += 1
        
        print(f"Створено {messages_count} приватних повідомлень")
        
        # Підтвердження змін
        connection.commit()
        print("Тестові дані успішно створено!")
        
    except mysql.connector.Error as error:
        print(f"Помилка: {error}")
        
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("З'єднання з MySQL закрито")

if __name__ == "__main__":
    generate_test_data()