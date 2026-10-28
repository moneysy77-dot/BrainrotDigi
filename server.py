import os, asyncio, json, hmac, hashlib, time, urllib.parse, secrets
from dotenv import load_dotenv
load_dotenv()
from pathlib import Path
from aiohttp import web
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

TOKEN = os.environ['BOT_TOKEN']
ADMIN_ID = int(os.environ['ADMIN_ID'])
WEBAPP_URL = os.getenv('WEBAPP_URL', 'https://moneysy77-dot.github.io/BrainrotDigi/')
CHANNEL = os.getenv('CHANNEL_USERNAME', '@brainrotdigi')
DB = os.getenv('DB_PATH', 'brainrotdigi.sqlite3')
PORT = int(os.getenv('PORT', '8080'))
bot = Bot(TOKEN)
dp = Dispatcher()
PRICES = {'Garama':45,'Cerberus':100,'Capitano Moby':70,'Dragon':800}
ITEMS = [('Garama', 60),('Cerberus', 25),('Capitano Moby', 12),('Dragon', 3)]

async def setup_db():
    async with aiosqlite.connect(DB) as db:
        await db.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, coins INTEGER NOT NULL DEFAULT 0, free_claimed INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS inventory(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT NOT NULL, reward INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending');
        ''')
        await db.commit()

async def ensure_user(db, uid):
    await db.execute('INSERT OR IGNORE INTO users(id) VALUES (?)', (uid,))

async def auth(request):
    raw = request.headers.get('X-Telegram-Init-Data', '')
    if not raw:
        raise web.HTTPUnauthorized(text='Open through Telegram Mini App')
    params = dict(urllib.parse.parse_qsl(raw, keep_blank_values=True))
    received = params.pop('hash', '')
    if not received:
        raise web.HTTPUnauthorized()
    check = '\n'.join(f'{k}={v}' for k,v in sorted(params.items()))
    secret = hmac.new(b'WebAppData', TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(received, expected):
        raise web.HTTPUnauthorized(text='Invalid signature')
    try:
        if abs(time.time() - int(params['auth_date'])) > 86400:
            raise ValueError('expired')
        uid = int(json.loads(params['user'])['id'])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise web.HTTPUnauthorized(text='Invalid Telegram user')
    return uid

def cors_headers():
    return {'Access-Control-Allow-Origin': WEBAPP_URL.rstrip('/'), 'Access-Control-Allow-Headers': 'Content-Type, X-Telegram-Init-Data', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS'}

@web.middleware
async def middleware(request, handler):
    if request.method == 'OPTIONS':
        return web.Response(headers=cors_headers())
    try:
        response = await handler(request)
    except web.HTTPException as exc:
        response = web.json_response({'error':exc.text or 'Request failed'}, status=exc.status)
    response.headers.update(cors_headers())
    return response

async def state(request):
    uid = await auth(request)
    async with aiosqlite.connect(DB) as db:
        await ensure_user(db, uid)
        await db.commit()
        async with db.execute('SELECT coins, free_claimed FROM users WHERE id=?',(uid,)) as cur:
            coins, claimed = await cur.fetchone()
        async with db.execute('SELECT id,name FROM inventory WHERE user_id=? ORDER BY id DESC',(uid,)) as cur:
            inventory = [{'id':r[0], 'name':r[1]} for r in await cur.fetchall()]
        async with db.execute('SELECT id,name,reward,status FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 20',(uid,)) as cur:
            requests = [{'id':r[0], 'name':r[1], 'reward':r[2], 'status':r[3]} for r in await cur.fetchall()]
    return web.json_response({'coins':coins,'free_claimed':bool(claimed),'inventory':inventory,'requests':requests,'prices':PRICES})

async def trade(request):
    uid = await auth(request)
    body = await request.json()
    name = body.get('name')
    if name not in PRICES:
        raise web.HTTPBadRequest(text='Unknown brainrot')
    async with aiosqlite.connect(DB) as db:
        await ensure_user(db,uid)
        async with db.execute("SELECT count(*) FROM requests WHERE user_id=? AND status='pending'",(uid,)) as cur:
            if (await cur.fetchone())[0] >= 3:
                raise web.HTTPConflict(text='Maximum 3 pending requests')
        cur = await db.execute('INSERT INTO requests(user_id,name,reward) VALUES (?,?,?)',(uid,name,PRICES[name]))
        rid = cur.lastrowid
        await db.commit()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Подтвердить', callback_data=f'approve:{rid}'),InlineKeyboardButton(text='❌ Отклонить',callback_data=f'reject:{rid}')]])
    try:
        await bot.send_message(ADMIN_ID, f'📩 Заявка #{rid}\nИгрок: {uid}\nБрейнрот: {name}\nНаграда: {PRICES[name]} 🪙\nПодтверждай только после проверки обмена в Roblox.', reply_markup=kb)
    except Exception:
        # Pending request stays recorded even if admin notification fails.
        pass
    return web.json_response({'ok':True,'request_id':rid})

@dp.callback_query(F.data.startswith(('approve:', 'reject:')))
async def review(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer('Нет доступа', show_alert=True)
        return
    action, raw_id = callback.data.split(':',1)
    rid = int(raw_id)
    async with aiosqlite.connect(DB) as db:
        await db.execute('BEGIN IMMEDIATE')
        async with db.execute('SELECT user_id,reward,status FROM requests WHERE id=?',(rid,)) as cur:
            row = await cur.fetchone()
        if not row or row[2] != 'pending':
            await db.rollback()
            await callback.answer('Заявка уже обработана',show_alert=True)
            return
        uid, reward, _ = row
        status = 'approved' if action == 'approve' else 'rejected'
        await db.execute('UPDATE requests SET status=? WHERE id=?',(status,rid))
        if action == 'approve':
            await db.execute('UPDATE users SET coins=coins+? WHERE id=?',(reward,uid))
        await db.commit()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer('Готово')
    try:
        await bot.send_message(uid, f'Заявка #{rid}: {"подтверждена, монеты начислены" if action == "approve" else "отклонена"}.')
    except Exception:
        pass

async def case(request):
    uid = await auth(request)
    body = await request.json()
    free = body.get('free') is True
    if free:
        try:
            member = await bot.get_chat_member(CHANNEL, uid)
            if member.status in ('left','kicked'):
                raise web.HTTPForbidden(text='Подпишись на канал')
        except web.HTTPException:
            raise
        except Exception:
            raise web.HTTPServiceUnavailable(text='Не удалось проверить подписку. Добавь бота администратором канала.')
    async with aiosqlite.connect(DB) as db:
        await db.execute('BEGIN IMMEDIATE')
        await ensure_user(db,uid)
        async with db.execute('SELECT coins,free_claimed FROM users WHERE id=?',(uid,)) as cur:
            coins, claimed = await cur.fetchone()
        if free and claimed:
            await db.rollback()
            raise web.HTTPConflict(text='Бесплатный кейс уже получен')
        if not free and coins < 100:
            await db.rollback()
            raise web.HTTPConflict(text='Недостаточно монет')
        if free:
            await db.execute('UPDATE users SET free_claimed=1 WHERE id=?',(uid,))
        else:
            await db.execute('UPDATE users SET coins=coins-100 WHERE id=?',(uid,))
        roll = secrets.randbelow(100)
        total=0
        name=ITEMS[-1][0]
        for item,weight in ITEMS:
            total+=weight
            if roll<total:
                name=item
                break
        await db.execute('INSERT INTO inventory(user_id,name) VALUES (?,?)',(uid,name))
        await db.commit()
    return web.json_response({'won':name})

async def fuse(request):
    uid=await auth(request)
    body=await request.json()
    ids=body.get('ids',[])
    if not isinstance(ids,list) or len(ids)!=3 or any(type(i)!=int for i in ids) or len(set(ids))!=3:
        raise web.HTTPBadRequest(text='Выбери 3 разных предмета')
    async with aiosqlite.connect(DB) as db:
        await db.execute('BEGIN IMMEDIATE')
        async with db.execute('SELECT id FROM inventory WHERE user_id=? AND id IN (?,?,?)',(uid,*ids)) as cur:
            found=await cur.fetchall()
        if len(found)!=3:
            await db.rollback()
            raise web.HTTPBadRequest(text='Предметы не найдены')
        await db.executemany('DELETE FROM inventory WHERE id=? AND user_id=?',[(i,uid) for i in ids])
        result=ITEMS[secrets.randbelow(len(ITEMS))][0]
        await db.execute('INSERT INTO inventory(user_id,name) VALUES (?,?)',(uid,result))
        await db.commit()
    return web.json_response({'won':result})

async def upgrade(request):
    uid=await auth(request)
    body=await request.json()
    iid=body.get('id')
    if type(iid)!=int:
        raise web.HTTPBadRequest(text='Выбери предмет')
    names=[x[0] for x in ITEMS]
    async with aiosqlite.connect(DB) as db:
        await db.execute('BEGIN IMMEDIATE')
        async with db.execute('SELECT name FROM inventory WHERE id=? AND user_id=?',(iid,uid)) as cur:
            row=await cur.fetchone()
        if not row:
            await db.rollback()
            raise web.HTTPBadRequest(text='Предмет не найден')
        idx=names.index(row[0])
        if idx==len(names)-1:
            await db.rollback()
            raise web.HTTPConflict(text='Максимальный уровень')
        success=secrets.randbelow(100)<40
        if success:
            await db.execute('UPDATE inventory SET name=? WHERE id=?',(names[idx+1],iid))
        else:
            await db.execute('DELETE FROM inventory WHERE id=?',(iid,))
        await db.commit()
    return web.json_response({'success':success,'result':names[idx+1] if success else None})

@dp.message(Command('start'))
async def start(message: Message):
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🎮 Открыть BrainrotDigi',web_app=WebAppInfo(url=WEBAPP_URL))]])
    await message.answer('🧠 Добро пожаловать в BrainrotDigi!\nОткрой Mini App:',reply_markup=kb)

async def main():
    await setup_db()
    app=web.Application(middlewares=[middleware])
    app.router.add_get('/',lambda request: web.Response(text='BrainrotDigi API running'))
    app.router.add_get('/api/state',state)
    app.router.add_post('/api/trade',trade)
    app.router.add_post('/api/case',case)
    app.router.add_post('/api/fuse',fuse)
    app.router.add_post('/api/upgrade',upgrade)
    runner=web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner,'0.0.0.0',PORT).start()
    print(f'BrainrotDigi API running on port {PORT}')
    await dp.start_polling(bot)

if __name__=='__main__':
    asyncio.run(main())
