import sqlite3
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import os

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Получаем токен из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN', '8304708243:AAHu5pL628e45y3MmiltjE5ebsxMooAJz6E')
ADMIN_USERNAME = "no_validxxx"
ADMIN_CHAT_ID = 8467569113

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('tournaments.db', check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # Таблица турниров
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tournaments (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                date TEXT,
                entry_fee TEXT,
                prize TEXT,
                max_participants INTEGER,
                participants INTEGER DEFAULT 0,
                photo_id TEXT,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        # Таблица регистраций
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id TEXT,
                user_tg_id INTEGER,
                user_tg_username TEXT,
                nickname TEXT,
                game_id TEXT,
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tournament_id) REFERENCES tournaments (id)
            )
        ''')
        
        # Таблица ссылок пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_links (
                user_id INTEGER PRIMARY KEY,
                match_link TEXT
            )
        ''')
        
        self.conn.commit()
    
    def add_tournament(self, tournament_id, name, description, date, entry_fee, prize, max_participants, photo_id=None):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO tournaments (id, name, description, date, entry_fee, prize, max_participants, photo_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
        ''', (tournament_id, name, description, date, entry_fee, prize, max_participants, photo_id))
        self.conn.commit()
    
    def get_tournaments(self, active_only=True):
        cursor = self.conn.cursor()
        if active_only:
            cursor.execute('SELECT * FROM tournaments WHERE status = "active" ORDER BY id')
        else:
            cursor.execute('SELECT * FROM tournaments ORDER BY id')
        tournaments = cursor.fetchall()
        # Конвертируем в словарь для совместимости
        result = {}
        for t in tournaments:
            result[t[0]] = {
                'name': t[1],
                'description': t[2],
                'date': t[3],
                'entry_fee': t[4],
                'prize': t[5],
                'max_participants': t[6],
                'participants': t[7],
                'photo_id': t[8],
                'status': t[9]
            }
        return result
    
    def get_tournament(self, tournament_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM tournaments WHERE id = ?', (tournament_id,))
        result = cursor.fetchone()
        if result:
            return {
                'id': result[0],
                'name': result[1],
                'description': result[2],
                'date': result[3],
                'entry_fee': result[4],
                'prize': result[5],
                'max_participants': result[6],
                'participants': result[7],
                'photo_id': result[8],
                'status': result[9]
            }
        return None
    
    def add_registration(self, tournament_id, user_tg_id, user_tg_username, nickname, game_id):
        cursor = self.conn.cursor()
        
        # Проверяем, активен ли турнир
        tournament = self.get_tournament(tournament_id)
        if tournament and tournament['status'] != 'active':
            return False, "Турнир завершен, запись невозможна"
        
        # Проверяем, не зарегистрирован ли уже
        cursor.execute('''
            SELECT * FROM registrations 
            WHERE tournament_id = ? AND user_tg_id = ?
        ''', (tournament_id, user_tg_id))
        
        if cursor.fetchone():
            return False, "Ты уже зарегистрирован на этот турнир"
        
        # Добавляем регистрацию
        cursor.execute('''
            INSERT INTO registrations (tournament_id, user_tg_id, user_tg_username, nickname, game_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (tournament_id, user_tg_id, user_tg_username, nickname, game_id))
        
        # Увеличиваем счетчик участников
        cursor.execute('''
            UPDATE tournaments 
            SET participants = participants + 1 
            WHERE id = ?
        ''', (tournament_id,))
        
        self.conn.commit()
        return True, "Успешная регистрация"
    
    def get_registrations(self, tournament_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM registrations 
            WHERE tournament_id = ?
            ORDER BY registration_date
        ''', (tournament_id,))
        return cursor.fetchall()
    
    def set_user_link(self, user_id, link):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO user_links (user_id, match_link)
            VALUES (?, ?)
        ''', (user_id, link))
        self.conn.commit()
    
    def get_user_link(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT match_link FROM user_links WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else "https://example.com/default-match"
    
    def delete_tournament(self, tournament_id):
        cursor = self.conn.cursor()
        # Сначала удаляем регистрации
        cursor.execute('DELETE FROM registrations WHERE tournament_id = ?', (tournament_id,))
        # Затем турнир
        cursor.execute('DELETE FROM tournaments WHERE id = ?', (tournament_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def complete_tournament(self, tournament_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE tournaments 
            SET status = 'completed' 
            WHERE id = ?
        ''', (tournament_id,))
        self.conn.commit()
        return cursor.rowcount > 0

# Инициализация БД
db = Database()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    is_admin = user.username and user.username.lower() == ADMIN_USERNAME.lower()
    
    keyboard = [
        [InlineKeyboardButton("Меню", callback_data="menu")],
        [InlineKeyboardButton("Связь с менеджером", url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton("Наш телеграм канал", url="https://t.me/RingingTournament")],
        [InlineKeyboardButton("Уведомления", callback_data="notifications")]
    ]
    
    if is_admin:
        keyboard.insert(1, [InlineKeyboardButton("Админ панель", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "Привет, ты попал в Ringing Tournament 📡\n"
        "Воспользуйся кнопками ниже чтобы ознакомиться с интерфейсом бота."
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на инлайн кнопки"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    is_admin = user.username and user.username.lower() == ADMIN_USERNAME.lower()
    
    data = query.data
    
    if data == "menu":
        await query.delete_message()
        await show_menu(query, context)
    
    elif data == "admin_panel" and is_admin:
        await show_admin_panel(query, context)
    
    elif data == "notifications":
        await query.edit_message_text("🔔 Настройки уведомлений будут здесь")
    
    elif data == "back_to_menu":
        await show_menu(query, context)
    
    elif data == "tournaments":
        await show_tournaments(query, context)
    
    elif data == "my_games":
        await show_my_games(query, context)
    
    elif data == "back_to_games":
        await show_my_games(query, context)
    
    elif data == "tournament_info":
        tournaments = db.get_tournaments()
        if tournaments:
            first_tournament_id = list(tournaments.keys())[0]
            await show_tournament_details(query, context, first_tournament_id, from_my_games=True)
        else:
            keyboard = [[InlineKeyboardButton("Назад", callback_data="my_games")]]
            await query.edit_message_text(
                "ℹ️ Нет активных турниров", 
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    elif data.startswith("tournament_"):
        tournament_id = data
        await show_tournament_details(query, context, tournament_id)
    
    elif data.startswith("admin_tournament_"):
        tournament_id = data.replace("admin_tournament_", "")
        await show_admin_tournament_details(query, context, tournament_id)
    
    elif data.startswith("register_"):
        tournament_id = data.replace("register_", "")
        await start_registration(query, context, tournament_id)
    
    elif data == "add_tournament":
        await query.edit_message_text("Введите название турнира:")
        context.user_data['waiting_for_tournament_name'] = True
    
    elif data == "view_tournaments":
        await show_admin_tournaments(query, context)
    
    elif data == "send_message":
        await query.edit_message_text("Введите ID пользователя и сообщение в формате: user_id текст сообщения")
        context.user_data['waiting_for_user_message'] = True
    
    elif data.startswith("delete_"):
        tournament_id = data.replace("delete_", "")
        if db.delete_tournament(tournament_id):
            await query.edit_message_text("✅ Турнир удален!")
        else:
            await query.edit_message_text("❌ Турнир не найден")
        await show_admin_tournaments(query, context)
    
    elif data.startswith("complete_"):
        tournament_id = data.replace("complete_", "")
        if db.complete_tournament(tournament_id):
            await query.edit_message_text("✅ Турнир завершен!")
        else:
            await query.edit_message_text("❌ Турнир не найден")
        await show_admin_tournaments(query, context)
    
    elif data.startswith("participants_"):
        tournament_id = data.replace("participants_", "")
        await show_participants_list(query, context, tournament_id)
    
    elif data == "back_to_start":
        user = query.from_user
        is_admin = user.username and user.username.lower() == ADMIN_USERNAME.lower()
        
        keyboard = [
            [InlineKeyboardButton("Меню", callback_data="menu")],
            [InlineKeyboardButton("Связь с менеджером", url=f"https://t.me/{ADMIN_USERNAME}")],
            [InlineKeyboardButton("Наш телеграм канал", url="https://t.me/RingingTournament")],
            [InlineKeyboardButton("Уведомления", callback_data="notifications")]
        ]
        
        if is_admin:
            keyboard.insert(1, [InlineKeyboardButton("Админ панель", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = (
            "Привет, ты попал в Ringing Tournament 📡\n"
            "Воспользуйся кнопками ниже чтобы ознакомиться с интерфейсом бота."
        )
        
        await query.edit_message_text(welcome_text, reply_markup=reply_markup)

async def show_participants_list(query, context, tournament_id):
    """Показывает список участников турнира"""
    tournament = db.get_tournament(tournament_id)
    if not tournament:
        await query.edit_message_text("❌ Турнир не найден")
        return
    
    registrations = db.get_registrations(tournament_id)
    
    if not registrations:
        text = f"📋 Список участников турнира: {tournament['name']}\n\n❌ Нет зарегистрированных участников"
    else:
        text = f"📋 Список участников турнира: {tournament['name']}\n\n"
        
        for i, reg in enumerate(registrations, 1):
            text += f"{i}. 🎮 Ник: {reg[4]}\n"
            text += f"   🆔 ID в игре: {reg[5]}\n"
            text += f"   👤 TG: @{reg[3] if reg[3] else 'скрыт'} (ID: {reg[2]})\n"
            text += f"   📅 Зарегистрирован: {reg[6][:10]}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Назад к турниру", callback_data=f"admin_tournament_{tournament_id}")],
        [InlineKeyboardButton("📊 Все турниры", callback_data="view_tournaments")]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def start_registration(query, context, tournament_id):
    """Начинает процесс регистрации на турнир"""
    if not db.get_tournament(tournament_id):
        await query.edit_message_text("❌ Турнир не найден")
        return
    
    context.user_data['registering_for_tournament'] = tournament_id
    context.user_data['waiting_for_nickname_id'] = True
    
    instruction_text = (
        "# Ringing Tournament\n\n"
        "📌 Запись на турнир\n\n"
        "Введи твой ник и айди, например:\n"
        "#CinShlyuhi и no valid\n\n"
        "📅 ОБЯЗАТЕЛЬНО: Если ты введёшь неправильный ID, то это дисквалификация!"
    )
    
    await query.message.reply_text(instruction_text)

async def show_tournament_details(query, context, tournament_id, from_my_games=False):
    """Показывает детальную информацию о турнире"""
    tournament = db.get_tournament(tournament_id)
    
    if tournament:
        status_emoji = "✅" if tournament['status'] == 'active' else "🏁"
        info_text = (
            f"🏆 {tournament['name']} {status_emoji}\n\n"
            f"📝 {tournament['description']}\n"
            f"📅 Дата: {tournament['date']}\n"
            f"💰 Призовой фонд: {tournament['prize']}\n"
            f"💵 Стоимость участия: {tournament['entry_fee']}\n"
            f"👥 Участников: {tournament['participants']}/{tournament['max_participants']}\n"
            f"📊 Статус: {'Активный' if tournament['status'] == 'active' else 'Завершен'}"
        )
        
        if from_my_games or query.data == "tournament_info":
            back_callback = "my_games"
        else:
            back_callback = "tournaments"
        
        keyboard = []
        
        if not from_my_games and query.data != "tournament_info" and tournament['status'] == 'active':
            keyboard.append([InlineKeyboardButton("📝 Записаться", callback_data=f"register_{tournament_id}")])
        
        keyboard.append([InlineKeyboardButton("Назад", callback_data=back_callback)])
        
        await query.edit_message_text(
            info_text, 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        keyboard = [[InlineKeyboardButton("Назад", callback_data="my_games")]]
        await query.edit_message_text(
            "❌ Турнир не найден", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def show_admin_tournament_details(query, context, tournament_id):
    """Показывает детальную информацию о турнире для админа"""
    tournament = db.get_tournament(tournament_id)
    
    if tournament:
        status_emoji = "✅" if tournament['status'] == 'active' else "🏁"
        info_text = (
            f"🏆 {tournament['name']} {status_emoji}\n\n"
            f"📝 {tournament['description']}\n"
            f"📅 Дата: {tournament['date']}\n"
            f"💰 Призовой фонд: {tournament['prize']}\n"
            f"💵 Стоимость участия: {tournament['entry_fee']}\n"
            f"👥 Участников: {tournament['participants']}/{tournament['max_participants']}\n"
            f"📊 Статус: {'Активный' if tournament['status'] == 'active' else 'Завершен'}"
        )
        
        keyboard = []
        
        if tournament['status'] == 'active':
            keyboard.append([InlineKeyboardButton("🏁 Завершить турнир", callback_data=f"complete_{tournament_id}")])
        
        keyboard.append([InlineKeyboardButton("❌ Удалить турнир", callback_data=f"delete_{tournament_id}")])
        keyboard.append([InlineKeyboardButton("📋 Список участников", callback_data=f"participants_{tournament_id}")])
        keyboard.append([InlineKeyboardButton("Назад", callback_data="view_tournaments")])
        
        await query.edit_message_text(
            info_text, 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        keyboard = [[InlineKeyboardButton("Назад", callback_data="view_tournaments")]]
        await query.edit_message_text(
            "❌ Турнир не найден", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def show_menu(query, context):
    """Показывает главное меню"""
    keyboard = [
        [InlineKeyboardButton("Турниры", callback_data="tournaments")],
        [InlineKeyboardButton("Мои игры", callback_data="my_games")],
        [InlineKeyboardButton("Назад", callback_data="back_to_start")]
    ]
    
    await query.message.reply_text(
        "Ringing Tournament",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_tournaments(query, context):
    """Показывает список турниров"""
    tournaments = db.get_tournaments()
    
    if not tournaments:
        keyboard = [[InlineKeyboardButton("Назад", callback_data="menu")]]
        await query.edit_message_text(
            "🏆 На данный момент нет активных турниров",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    keyboard = []
    for tournament_id, tournament in tournaments.items():
        status_emoji = "✅" if tournament['status'] == 'active' else "🏁"
        keyboard.append([InlineKeyboardButton(f"{tournament['name']} {status_emoji}", callback_data=tournament_id)])
    
    keyboard.append([InlineKeyboardButton("Назад", callback_data="menu")])
    
    await query.edit_message_text(
        "🏆 Выберите турнир:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_my_games(query, context):
    """Показывает меню 'Мои игры'"""
    keyboard = [
        [InlineKeyboardButton("О турнире", callback_data="tournament_info")],
        [InlineKeyboardButton("Назад", callback_data="menu")]
    ]
    
    await query.edit_message_text(
        "🎮 Мои игры",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_admin_panel(query, context):
    """Показывает админ панель"""
    keyboard = [
        [InlineKeyboardButton("Добавить турнир", callback_data="add_tournament")],
        [InlineKeyboardButton("Просмотреть турниры", callback_data="view_tournaments")],
        [InlineKeyboardButton("📨 Отправить сообщение", callback_data="send_message")],
        [InlineKeyboardButton("Назад", callback_data="menu")]
    ]
    
    await query.edit_message_text(
        "⚙️ Админ панель",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_admin_tournaments(query, context):
    """Показывает турниры в админ панели"""
    tournaments = db.get_tournaments(active_only=False)
    
    if not tournaments:
        text = "❌ Нет созданных турниров"
        keyboard = [[InlineKeyboardButton("Назад", callback_data="admin_panel")]]
    else:
        text = "🏆 Все турниры:\n\n"
        keyboard = []
        for tournament_id, tournament in tournaments.items():
            status_text = "✅ Активный" if tournament['status'] == 'active' else "🏁 Завершен"
            text += f"• {tournament['name']} ({status_text})\n"
            keyboard.append([InlineKeyboardButton(f"📋 {tournament['name']}", callback_data=f"admin_tournament_{tournament_id}")])
        
        keyboard.append([InlineKeyboardButton("Назад", callback_data="admin_panel")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений и фото"""
    user = update.effective_user
    
    # Обработка отправки сообщения пользователю
    if context.user_data.get('waiting_for_user_message'):
        try:
            user_id_str, message_text = update.message.text.split(' ', 1)
            user_id = int(user_id_str)
            
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text
            )
            
            await update.message.reply_text(f"✅ Сообщение отправлено пользователю {user_id}")
            context.user_data.pop('waiting_for_user_message')
            
        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Используйте: user_id текст сообщения")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка отправки: {e}")
            context.user_data.pop('waiting_for_user_message')
        return
    
    # Обработка регистрации на турнир
    if context.user_data.get('waiting_for_nickname_id'):
        tournament_id = context.user_data.get('registering_for_tournament')
        
        tournament = db.get_tournament(tournament_id)
        if tournament:
            message_text = update.message.text
            parts = message_text.split(' и ')
            
            if len(parts) >= 2:
                nickname = parts[0].strip()
                user_id = parts[1].strip()
                
                # Пытаемся зарегистрировать
                success, message = db.add_registration(
                    tournament_id, 
                    user.id, 
                    user.username, 
                    nickname, 
                    user_id
                )
                
                if success:
                    await update.message.reply_text(
                        f"✅ Ты успешно записался на турнир!\n"
                        f"🏆 Турнир: {tournament['name']}\n"
                        f"🎮 Твой ник: {nickname}\n"
                        f"🆔 Твой ID: {user_id}"
                    )
                    
                    # УВЕДОМЛЕНИЕ АДМИНУ
                    try:
                        admin_text = (
                            f"НОВАЯ ЗАПИСЬ НА ТУРНИР!\n"
                            f"Турнир: {tournament['name']}\n"
                            f"ID TG: {user.id}\n"
                            f"Username: @{user.username if user.username else 'нет'}\n"
                            f"Ник: {nickname}\n"
                            f"ID в игре: {user_id}"
                        )
                        
                        await context.bot.send_message(
                            chat_id=ADMIN_CHAT_ID,
                            text=admin_text
                        )
                        print("✅ УВЕДОМЛЕНИЕ ОТПРАВЛЕНО АДМИНУ!")
                        
                    except Exception as e:
                        print(f"❌ ОШИБКА ОТПРАВКИ АДМИНУ: {e}")
                else:
                    await update.message.reply_text(f"❌ {message}")
                
            else:
                await update.message.reply_text(
                    "❌ Неверный формат. Используйте: ник и айди\n"
                    "Например: #CinShlyuhi и no valid"
                )
                return
        
        context.user_data.pop('waiting_for_nickname_id', None)
        context.user_data.pop('registering_for_tournament', None)
        return
    
    # Обработка фото
    if update.message.photo:
        if context.user_data.get('waiting_for_tournament_photo'):
            photo_file_id = update.message.photo[-1].file_id
            context.user_data['new_tournament']['photo'] = photo_file_id
            context.user_data['waiting_for_tournament_photo'] = False
            await update.message.reply_text("💰 Введите призовой фонд (например: 10,000 руб):")
            context.user_data['waiting_for_tournament_prize'] = True
        return
    
    message_text = update.message.text
    
    if context.user_data.get('waiting_for_tournament_name'):
        context.user_data['new_tournament'] = {'name': message_text}
        context.user_data['waiting_for_tournament_name'] = False
        context.user_data['waiting_for_tournament_description'] = True
        await update.message.reply_text("Введите описание турнира:")
    
    elif context.user_data.get('waiting_for_tournament_description'):
        context.user_data['new_tournament']['description'] = message_text
        context.user_data['waiting_for_tournament_description'] = False
        context.user_data['waiting_for_tournament_date'] = True
        await update.message.reply_text("📅 Введите дату турнира (например: 15.04.2024):")
    
    elif context.user_data.get('waiting_for_tournament_date'):
        context.user_data['new_tournament']['date'] = message_text
        context.user_data['waiting_for_tournament_date'] = False
        context.user_data['waiting_for_tournament_entry_fee'] = True
        await update.message.reply_text("💵 Введите стоимость участия (например: 500 руб или Бесплатно):")
    
    elif context.user_data.get('waiting_for_tournament_entry_fee'):
        context.user_data['new_tournament']['entry_fee'] = message_text
        context.user_data['waiting_for_tournament_entry_fee'] = False
        context.user_data['waiting_for_tournament_max_participants'] = True
        await update.message.reply_text("👥 Введите максимальное количество участников:")
    
    elif context.user_data.get('waiting_for_tournament_max_participants'):
        try:
            max_participants = int(message_text)
            context.user_data['new_tournament']['max_participants'] = max_participants
            context.user_data['waiting_for_tournament_max_participants'] = False
            context.user_data['waiting_for_tournament_photo'] = True
            await update.message.reply_text("🖼 Отправьте фото для обложки турнира (или отправьте любой текст чтобы пропустить):")
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите число:")
    
    elif context.user_data.get('waiting_for_tournament_prize'):
        context.user_data['new_tournament']['prize'] = message_text
        tournament = context.user_data['new_tournament']
        
        tournament_id = f"tournament_{len(db.get_tournaments(active_only=False)) + 1}"
        db.add_tournament(
            tournament_id,
            tournament['name'],
            tournament['description'],
            tournament['date'],
            tournament['entry_fee'],
            tournament['prize'],
            tournament['max_participants'],
            tournament.get('photo')
        )
        
        context.user_data.pop('new_tournament')
        context.user_data.pop('waiting_for_tournament_prize')
        
        await update.message.reply_text(f"✅ Турнир '{tournament['name']}' успешно создан!")

def main():
    """Запуск бота"""
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_message))
        
        print("🤖 Бот запускается...")
        print("🗄️ База данных SQLite подключена")
        application.run_polling()
        
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
        import time
        time.sleep(10)
        main()

if __name__ == "__main__":
    main()