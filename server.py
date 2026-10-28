import os, asyncio, json, hmac, hashlib, time, urllib.parse, secrets
from datetime import datetime, timezone
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
# Цены здесь — только условные баллы коллекции, не реальные деньги.
NAMES = [
('Los Trios',5),('67',6),('Spinny H',7),('Arcadopus',8),('Candy Slap',8),('Los Noobini',8),('Tang Tang',9),('La Grande',10),('Divine Slap',10),
('Tictac Sahur',13),('Bacuru',13),('Los 67',13),('Cursed Slap',13),('Ying Yang',13),('Los Combinas',15),('Money Pug',15),('Lava Slap',15),('Nuclearo',16),
('Esok Sekolah',17),('Agarini',23),('Abbyssalo',23),('Los Mobilis',24),('Rainbow',24),('Los Burritos',25),('Los Puggies',29),('Orcaledon',30),('Ketupat',30),
('Waverider',37),('Witch Broom',40),('Blackhole',40),('Mi Gatito',41),('Camera R',41),('Ventolero',44),('Garama',44),('Yes My Exam',44),('Los Primos',45),
('Air Strike',45),('Cash or Crash',46),('Candy Secret',46),('Los Planitos',49),('La Summer',49),('Honey Honey',51),('Ketchuru',54),('Quassadilo',55),('Noodle',57),
('Phantom Slap',60),('La Jolly',69),('Sammyini',74),('Eviledon',75),('W or L',78),('Lava Blast',80),('Los Tictacs',82),('Los Sweet',84),('John Doe',84),
('Pizza and',84),('Los Jolly',91),('Popcura',92),('Los Mariachis',92),('Quackini',93),('Santas Slap',93),('La Secret',95),('Celestial',98),('Scorpino',98),
('Las Sis',99),('Burrum',109),('La Food',109),('Capitano',110),('Swag Soda',111),('Steakini',117),('Gold Gold',122),('Tralalero',122),('Los Cupids',126),
('Fragrama',128),('Los Hotspots',131),('La Taco',132),('Capitano Moby',134),('Los Spaghetti',135),('Pop Pop',136),('Cooki',137),('Tuff Toucan',138),('Jolly Jolly',139),
('Rosetti',140),('Money Money',140),('Swaggy Bros',150),('Spooky',153),('Boppin',160),('Money Machine',162),('Cerberus',163),('La Ginger',164),('Chipso',166),
('Festive 67',207),('Fragola',212),('La Fuse',220),('No My Exam',221),('Dug Dug',237),('Fortuna',242),('Cangurat',255),('Cloverat',258),('Caylusaur',267),
('Hoppilikali',281),('La Breakfast',287),('Los Tacor',290),('Duggy Bros',340),('Los Sekolah',342),('Guest 666',353),('Los Admins',389),('Examen Bros',393),('Smore',399),
('Rubiko',415),('Los Hackers',420),('Foxini',426),('Los Secret',440),('Rico Dinero',483),('Venuspino',512),('Ketupat Bros',513),('Bumbatron',529),('Rosey',552),
('Sammyini Ultra',572),('La Casa',579),('Rainbow Ultra',655),('Sammyini Gold',661),('Bunny',906),('Dragon Cannelloni',1022),('Pancake',1060),('Grabatron',1182),('Jelly Moby',1211),
('Hydra Dragon',1281),('Tirilikalika',1318),('Bloodmoon',1322),('Moby Bros',1685),('Hydra Bunny',1809),('Ginger Gee',2064),('Fishino',2104),('Kraken',2132),('Digi Narwhal',2246),
('La Supreme',2420),('Kalika Bros',3644),('Dragon A',3887),('Dragon G',5161),('Antonio',5827),('Griffin',6623),('Love Love',7074),('Arcadragon',11403),('Elefanto',12400),
('Skibidi Tin',13812),('John Pork',15257),('Orchidorx',15884),('Meowl',17681),('Signore Carapace',34676),('Strawberry',44635),('Headless',243600)
]
CATALOG = [{'name':n,'value':v,'tier':('Обычный' if v<50 else 'Редкий' if v<200 else 'Эпический' if v<1000 else 'Легендарный' if v<10000 else 'Мифический')} for n,v in NAMES]
BY_NAME = {x['name']:x for x in CATALOG}
CASES = [
 {'id':'starter','name':'Стартовый','emoji':'🎒','cooldown':43200,'min':0,'max':49,'desc':'Каждые 12 часов'},
 {'id':'rare','name':'Редкий','emoji':'💎','cooldown':86400,'min':50,'max':199,'desc':'Каждые 24 часа'},
 {'id':'epic','name':'Эпический','emoji':'🔮','cooldown':172800,'min':200,'max':999,'desc':'Каждые 48 часов'},
 {'id':'legend','name':'Легендарный','emoji':'👑','cooldown':604800,'min':1000,'max':999999,'desc':'Раз в 7 дней'}
]
WITHDRAWABLE = {'Garama', 'Capitano Moby', 'Cerberus', 'Dragon Cannelloni'}
TRADE_PRICES = {'Garama':45,'Cerberus':100,'Capitano Moby':70,'Dragon Cannelloni':800}

async def setup_db():
 async with aiosqlite.connect(DB) as db:
  await db.executescript('''
  CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, coins INTEGER NOT NULL DEFAULT 0, free_claimed INTEGER NOT NULL DEFAULT 0);
  CREATE TABLE IF NOT EXISTS inventory(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT NOT NULL, reward INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending');
  CREATE TABLE IF NOT EXISTS withdrawals(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT NOT NULL, roblox_username TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending');
  CREATE TABLE IF NOT EXISTS case_claims(user_id INTEGER NOT NULL, case_id TEXT NOT NULL, claimed_at INTEGER NOT NULL, claim_count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(user_id,case_id));
  ''')
  await db.commit()
async def ensure_user(db,uid):
 await db.execute('INSERT OR IGNORE INTO users(id) VALUES (?)',(uid,))
async def auth(request):
 raw=request.headers.get('X-Telegram-Init-Data','')
 if not raw: raise web.HTTPUnauthorized(text='Открой игру через Telegram')
 params=dict(urllib.parse.parse_qsl(raw,keep_blank_values=True))
 received=params.pop('hash','')
 check='\n'.join(f'{k}={v}' for k,v in sorted(params.items()))
 secret=hmac.new(b'WebAppData',TOKEN.encode(),hashlib.sha256).digest()
 expected=hmac.new(secret,check.encode(),hashlib.sha256).hexdigest()
 if not received or not hmac.compare_digest(received,expected): raise web.HTTPUnauthorized(text='Неверная подпись Telegram')
 try:
  if abs(time.time()-int(params['auth_date']))>86400: raise ValueError()
  return int(json.loads(params['user'])['id'])
 except (ValueError,KeyError,TypeError,json.JSONDecodeError): raise web.HTTPUnauthorized(text='Сессия устарела')
def cors_headers():
 p=urllib.parse.urlsplit(WEBAPP_URL)
 return {'Access-Control-Allow-Origin':f'{p.scheme}://{p.netloc}','Access-Control-Allow-Headers':'Content-Type, X-Telegram-Init-Data','Access-Control-Allow-Methods':'GET, POST, OPTIONS'}
@web.middleware
async def middleware(request,handler):
 if request.method=='OPTIONS':return web.Response(headers=cors_headers())
 try: response=await handler(request)
 except web.HTTPException as e: response=web.json_response({'error':e.text or 'Ошибка'},status=e.status)
 response.headers.update(cors_headers())
 return response
async def state(request):
 uid=await auth(request)
 async with aiosqlite.connect(DB) as db:
  await ensure_user(db,uid);await db.commit()
  async with db.execute('SELECT coins,free_claimed FROM users WHERE id=?',(uid,)) as c: coins,claimed=await c.fetchone()
  async with db.execute('SELECT id,name FROM inventory WHERE user_id=? ORDER BY id DESC',(uid,)) as c: inv=[{'id':r[0],'name':r[1]} for r in await c.fetchall()]
  async with db.execute('SELECT id,name,reward,status FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 30',(uid,)) as c: req=[{'id':r[0],'name':r[1],'reward':r[2],'status':r[3]} for r in await c.fetchall()]
  async with db.execute('SELECT id,name,roblox_username,status FROM withdrawals WHERE user_id=? ORDER BY id DESC LIMIT 30',(uid,)) as c: withdrawals=[{'id':r[0],'name':r[1],'roblox_username':r[2],'status':r[3]} for r in await c.fetchall()]
  async with db.execute('SELECT case_id,claimed_at FROM case_claims WHERE user_id=?',(uid,)) as c: claims={r[0]:r[1] for r in await c.fetchall()}
 return web.json_response({'coins':coins,'inventory':inv,'requests':req,'free_claimed':bool(claimed),'catalog':CATALOG,'cases':CASES,'claims':claims,'now':int(time.time()),'prices':TRADE_PRICES,'withdrawals':withdrawals,'withdrawable':sorted(WITHDRAWABLE)})
async def case(request):
 uid=await auth(request);body=await request.json();cid=body.get('case_id','starter')
 case=next((x for x in CASES if x['id']==cid),None)
 if not case:raise web.HTTPBadRequest(text='Неизвестный кейс')
 now=int(time.time())
 async with aiosqlite.connect(DB) as db:
  await db.execute('BEGIN IMMEDIATE');await ensure_user(db,uid)
  async with db.execute('SELECT claimed_at,claim_count FROM case_claims WHERE user_id=? AND case_id=?',(uid,cid)) as c: prev=await c.fetchone()
  if prev and now-prev[0]<case['cooldown']:
   await db.rollback();raise web.HTTPConflict(text='Кейс пока недоступен. Дождись таймера.')
  pool=[x for x in CATALOG if case['min']<=x['value']<=case['max']]
  # Предсказуемый цикл без ставок и платных случайных наград.
  count=prev[1] if prev else 0
  item=pool[(uid+count)%len(pool)]
  inserted=await db.execute('INSERT INTO inventory(user_id,name) VALUES (?,?)',(uid,item['name']))
  await db.execute('INSERT INTO case_claims(user_id,case_id,claimed_at,claim_count) VALUES (?,?,?,?) ON CONFLICT(user_id,case_id) DO UPDATE SET claimed_at=excluded.claimed_at,claim_count=excluded.claim_count',(uid,cid,now,count+1))
  await db.commit()
 return web.json_response({'won':item['name'],'inventory_id':inserted.lastrowid})
async def fuse(request):
 uid=await auth(request);body=await request.json();ids=body.get('ids',[])
 if not isinstance(ids,list) or len(ids)!=4 or any(type(i)!=int for i in ids) or len(set(ids))!=4:raise web.HTTPBadRequest(text='Выбери 4 разных персонажа')
 async with aiosqlite.connect(DB) as db:
  await db.execute('BEGIN IMMEDIATE')
  async with db.execute('SELECT id,name FROM inventory WHERE user_id=? AND id IN (?,?,?,?)',(uid,*ids)) as c: found=await c.fetchall()
  if len(found)!=4:await db.rollback();raise web.HTTPBadRequest(text='Персонажи не найдены')
  maxval=max(BY_NAME.get(n,{'value':0})['value'] for _,n in found)
  candidates=[x for x in CATALOG if x['value']>maxval]
  if not candidates:await db.rollback();raise web.HTTPConflict(text='Достигнут максимальный уровень')
  result=min(candidates,key=lambda x:x['value'])['name']
  await db.executemany('DELETE FROM inventory WHERE id=? AND user_id=?',[(i,uid) for i in ids])
  await db.execute('INSERT INTO inventory(user_id,name) VALUES (?,?)',(uid,result));await db.commit()
 return web.json_response({'won':result})
async def upgrade(request):
 """Гарантированный обмен одного персонажа + доплата игровыми монетами."""
 uid = await auth(request)
 body = await request.json()
 iid, target = body.get('id'), body.get('target')
 if type(iid) is not int or not isinstance(target, str) or target not in BY_NAME:
  raise web.HTTPBadRequest(text='Выбери своего персонажа и цель улучшения')
 async with aiosqlite.connect(DB) as db:
  await db.execute('BEGIN IMMEDIATE')
  await ensure_user(db, uid)
  async with db.execute('SELECT name FROM inventory WHERE id=? AND user_id=?', (iid, uid)) as c:
   row = await c.fetchone()
  if not row or row[0] not in BY_NAME:
   await db.rollback()
   raise web.HTTPBadRequest(text='Персонаж не найден в твоей коллекции')
  current = BY_NAME[row[0]]
  desired = BY_NAME[target]
  if desired['value'] <= current['value']:
   await db.rollback()
   raise web.HTTPBadRequest(text='Выбери более дорогого персонажа')
  cost = desired['value'] - current['value']
  async with db.execute('SELECT coins FROM users WHERE id=?', (uid,)) as c:
   coins = (await c.fetchone())[0]
  if coins < cost:
   await db.rollback()
   raise web.HTTPConflict(text=f'Недостаточно монет. Нужно {cost} 🪙')
  await db.execute('UPDATE users SET coins=coins-? WHERE id=?', (cost, uid))
  await db.execute('UPDATE inventory SET name=? WHERE id=? AND user_id=?', (target, iid, uid))
  await db.commit()
 return web.json_response({'success': True, 'result': target, 'cost': cost, 'inventory_id': iid})
async def sell(request):
 uid=await auth(request)
 body=await request.json()
 iid=body.get('id')
 if type(iid)!=int:raise web.HTTPBadRequest(text='Выбери персонажа')
 async with aiosqlite.connect(DB) as db:
  await db.execute('BEGIN IMMEDIATE')
  await ensure_user(db,uid)
  async with db.execute('SELECT name FROM inventory WHERE id=? AND user_id=?',(iid,uid)) as c:
   row=await c.fetchone()
  if not row:
   await db.rollback();raise web.HTTPConflict(text='Персонаж уже продан или отсутствует')
  name=row[0]
  entry=BY_NAME.get(name)
  if not entry:
   await db.rollback();raise web.HTTPBadRequest(text='Нет цены для этого персонажа')
  reward=int(entry['value'])
  await db.execute('DELETE FROM inventory WHERE id=? AND user_id=?',(iid,uid))
  await db.execute('UPDATE users SET coins=coins+? WHERE id=?',(reward,uid))
  await db.commit()
 return web.json_response({'ok':True,'name':name,'earned':reward})

async def trade(request):
 uid=await auth(request);body=await request.json();name=body.get('name')
 if name not in TRADE_PRICES:raise web.HTTPBadRequest(text='Неизвестный персонаж')
 async with aiosqlite.connect(DB) as db:
  await ensure_user(db,uid)
  async with db.execute("SELECT count(*) FROM requests WHERE user_id=? AND status='pending'",(uid,)) as c:
   if (await c.fetchone())[0]>=3:raise web.HTTPConflict(text='Не более 3 активных заявок')
  cur=await db.execute('INSERT INTO requests(user_id,name,reward) VALUES (?,?,?)',(uid,name,TRADE_PRICES[name]));rid=cur.lastrowid;await db.commit()
 kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Подтвердить',callback_data=f'approve:{rid}'),InlineKeyboardButton(text='❌ Отклонить',callback_data=f'reject:{rid}')]])
 try:await bot.send_message(ADMIN_ID,f'📩 Заявка #{rid}\nИгрок: {uid}\nПерсонаж: {name}\nБаллы: {TRADE_PRICES[name]}\nПроверяй обмен самостоятельно.',reply_markup=kb)
 except Exception:pass
 return web.json_response({'ok':True,'request_id':rid})
@dp.callback_query(F.data.startswith(('approve:','reject:')))
async def review(callback:CallbackQuery):
 if callback.from_user.id!=ADMIN_ID:await callback.answer('Нет доступа',show_alert=True);return
 action,raw=callback.data.split(':',1);rid=int(raw)
 async with aiosqlite.connect(DB) as db:
  await db.execute('BEGIN IMMEDIATE')
  async with db.execute('SELECT user_id,reward,status FROM requests WHERE id=?',(rid,)) as c:row=await c.fetchone()
  if not row or row[2]!='pending':await db.rollback();await callback.answer('Уже обработано');return
  uid,reward,_=row;status='approved' if action=='approve' else 'rejected'
  await db.execute('UPDATE requests SET status=? WHERE id=?',(status,rid))
  if action=='approve':await db.execute('UPDATE users SET coins=coins+? WHERE id=?',(reward,uid))
  await db.commit()
 await callback.message.edit_reply_markup(reply_markup=None);await callback.answer('Готово')
 try:await bot.send_message(uid,f'Заявка #{rid}: {"подтверждена" if action=="approve" else "отклонена"}.')
 except Exception:pass
async def withdraw(request):
    uid = await auth(request)
    body = await request.json()
    iid = body.get('id')
    username = body.get('roblox_username', '')
    if type(iid) is not int:
        raise web.HTTPBadRequest(text='Выбери персонажа из коллекции')
    if not isinstance(username, str) or not 3 <= len(username) <= 20 or not username.replace('_', '').isalnum() or not username.isascii():
        raise web.HTTPBadRequest(text='Укажи корректный Roblox-ник')
    async with aiosqlite.connect(DB) as db:
        await db.execute('BEGIN IMMEDIATE')
        async with db.execute('SELECT name FROM inventory WHERE id=? AND user_id=?',(iid,uid)) as cur:
            row = await cur.fetchone()
        if not row or row[0] not in WITHDRAWABLE:
            await db.rollback()
            raise web.HTTPBadRequest(text='Этот персонаж недоступен для вывода')
        async with db.execute("SELECT count(*) FROM withdrawals WHERE user_id=? AND status='pending'",(uid,)) as cur:
            if (await cur.fetchone())[0] >= 3:
                await db.rollback()
                raise web.HTTPConflict(text='Максимум 3 заявки на вывод')
        name = row[0]
        await db.execute('DELETE FROM inventory WHERE id=? AND user_id=?',(iid,uid))
        cur = await db.execute('INSERT INTO withdrawals(user_id,name,roblox_username) VALUES (?,?,?)',(uid,name,username))
        rid = cur.lastrowid
        await db.commit()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Передан',callback_data=f'wapprove:{rid}'),InlineKeyboardButton(text='❌ Отказать',callback_data=f'wreject:{rid}')]])
    try:
        await bot.send_message(ADMIN_ID, f'📤 Вывод #{rid}\nИгрок Telegram: {uid}\nRoblox: {username}\nПерсонаж: {name}\nПодтверждай только после передачи персонажа.', reply_markup=kb)
    except Exception:
        pass
    return web.json_response({'ok':True,'withdrawal_id':rid})

@dp.callback_query(F.data.startswith(('wapprove:', 'wreject:')))
async def review_withdrawal(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer('Нет доступа',show_alert=True)
        return
    action, raw_id = callback.data.split(':',1)
    rid = int(raw_id)
    async with aiosqlite.connect(DB) as db:
        await db.execute('BEGIN IMMEDIATE')
        async with db.execute('SELECT user_id,name,status FROM withdrawals WHERE id=?',(rid,)) as cur:
            row = await cur.fetchone()
        if not row or row[2] != 'pending':
            await db.rollback()
            await callback.answer('Заявка уже обработана',show_alert=True)
            return
        uid, name, _ = row
        approved = action == 'wapprove'
        await db.execute('UPDATE withdrawals SET status=? WHERE id=?',('approved' if approved else 'rejected',rid))
        if not approved:
            await db.execute('INSERT INTO inventory(user_id,name) VALUES (?,?)',(uid,name))
        await db.commit()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer('Готово')
    try:
        await bot.send_message(uid, f'📤 Заявка на вывод #{rid}: ' + ('подтверждена, персонаж передан.' if approved else 'отклонена, персонаж возвращён в коллекцию.'))
    except Exception:
        pass

@dp.message(Command('start'))
async def start(message:Message):
 kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🧠 Открыть BrainrotDigi',web_app=WebAppInfo(url=WEBAPP_URL))]])
 await message.answer('🧠 Добро пожаловать в BrainrotDigi!',reply_markup=kb)
async def main():
 await setup_db();app=web.Application(middlewares=[middleware])
 app.router.add_get('/',lambda request:web.Response(text='BrainrotDigi API running'))
 for path,fn,method in [('state',state,'get'),('case',case,'post'),('fuse',fuse,'post'),('upgrade',upgrade,'post'),('trade',trade,'post'),('withdraw',withdraw,'post'),('sell',sell,'post')]:getattr(app.router,'add_'+method)('/api/'+path,fn)
 runner=web.AppRunner(app);await runner.setup();await web.TCPSite(runner,'0.0.0.0',PORT).start()
 print('BrainrotDigi API running',flush=True);await dp.start_polling(bot)
if __name__=='__main__':asyncio.run(main())

