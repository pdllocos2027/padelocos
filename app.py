import os, sqlite3, hmac
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import check_password_hash, generate_password_hash

app=Flask(__name__)
app.secret_key=os.environ.get('SECRET_KEY', 'development-only-change-before-publishing')
DB=os.environ.get('DATABASE_PATH',os.path.join(os.path.dirname(__file__),'padelocos.db'))

def db():
    c=sqlite3.connect(DB,timeout=15,isolation_level=None)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA busy_timeout=15000')
    return c

def init_db():
    with db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS matches (id INTEGER PRIMARY KEY, title TEXT NOT NULL, starts_at TEXT NOT NULL, category TEXT NOT NULL, venue TEXT NOT NULL DEFAULT "", price REAL NOT NULL DEFAULT 0 CHECK(price>=0), capacity INTEGER NOT NULL CHECK(capacity>0))')
        c.execute('CREATE TABLE IF NOT EXISTS registrations (id INTEGER PRIMARY KEY, match_id INTEGER NOT NULL REFERENCES matches(id), name TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(match_id,name COLLATE NOCASE))')
        if not any(col[1]=='prize' for col in c.execute('PRAGMA table_info(matches)').fetchall()):
            c.execute("ALTER TABLE matches ADD COLUMN prize TEXT NOT NULL DEFAULT ''")
        c.execute('CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY, password_hash TEXT NOT NULL)')
        c.execute('PRAGMA foreign_keys=ON')
        if not c.execute('SELECT 1 FROM admins').fetchone():
            pwd=os.environ.get('ADMIN_PASSWORD')
            if pwd:
                c.execute('INSERT INTO admins(password_hash) VALUES (?)',(generate_password_hash(pwd),))
init_db()

def admin_required(fn):
    @wraps(fn)
    def inner(*a,**kw):
        if not session.get('admin'): return redirect(url_for('login'))
        return fn(*a,**kw)
    return inner

def token():
    if 'csrf' not in session:
        session['csrf']=os.urandom(24).hex()
    return session['csrf']
app.jinja_env.globals['csrf_token']=token

@app.before_request
def protect():
    if request.method=='POST' and not hmac.compare_digest(request.form.get('csrf',''),token()):
        return 'Solicitud inválida. Actualiza la página.',400

@app.get('/')
def index():
    c=db()
    matches=c.execute('SELECT * FROM matches WHERE starts_at >= ? ORDER BY starts_at ASC,id ASC',(datetime.now().strftime('%Y-%m-%dT%H:%M'),)).fetchall()
    rows=[]
    for m in matches:
        names=c.execute('SELECT name FROM registrations WHERE match_id=? ORDER BY id',(m['id'],)).fetchall()
        rows.append({'match':m,'names':names,'remaining':m['capacity']-len(names)})
    c.close()
    return render_template('index.html',rows=rows)

@app.post('/inscribir/<int:match_id>')
def register(match_id):
    name=' '.join(request.form.get('name','').split())
    if not (2<=len(name)<=70): flash('Escribe un nombre de 2 a 70 caracteres.','error');return redirect(url_for('index'))
    c=db()
    try:
        c.execute('BEGIN IMMEDIATE')
        m=c.execute('SELECT capacity,starts_at FROM matches WHERE id=?',(match_id,)).fetchone()
        count=c.execute('SELECT COUNT(*) FROM registrations WHERE match_id=?',(match_id,)).fetchone()[0]
        if not m or m['starts_at']<datetime.now().strftime('%Y-%m-%dT%H:%M'): flash('Este partido ya no está disponible.','error')
        elif count>=m['capacity']: flash('Este partido ya está completo.','error')
        else:
            try: c.execute('INSERT INTO registrations(match_id,name) VALUES (?,?)',(match_id,name));flash('¡Inscripción realizada!','ok')
            except sqlite3.IntegrityError: flash('Ese nombre ya está inscrito en este partido.','error')
        c.execute('COMMIT')
    except Exception:
        c.execute('ROLLBACK');raise
    finally: c.close()
    return redirect(url_for('index')+'#partidos')

@app.post('/inscribir-pareja/<int:match_id>')
def register_pair(match_id):
    names=[' '.join(request.form.get(key,'').split()) for key in ('name1','name2')]
    if any(not 2<=len(n)<=70 for n in names) or names[0].casefold()==names[1].casefold():
        flash('Escribe dos nombres diferentes, de 2 a 70 caracteres.','error')
        return redirect(url_for('index')+'#partidos')
    c=db()
    try:
        c.execute('BEGIN IMMEDIATE')
        m=c.execute('SELECT capacity,starts_at FROM matches WHERE id=?',(match_id,)).fetchone()
        count=c.execute('SELECT COUNT(*) FROM registrations WHERE match_id=?',(match_id,)).fetchone()[0]
        if not m or m['starts_at']<datetime.now().strftime('%Y-%m-%dT%H:%M'):
            flash('Este partido ya no está disponible.','error')
        elif m['capacity']-count<2:
            flash('No hay dos cupos disponibles para la pareja.','error')
        elif c.execute('SELECT 1 FROM registrations WHERE match_id=? AND (name=? COLLATE NOCASE OR name=? COLLATE NOCASE)',(match_id,*names)).fetchone():
            flash('Uno de los jugadores ya está inscrito.','error')
        else:
            for name in names:
                c.execute('INSERT INTO registrations(match_id,name) VALUES (?,?)',(match_id,name))
            flash('¡Pareja inscrita correctamente!','ok')
        c.execute('COMMIT')
    except sqlite3.IntegrityError:
        c.execute('ROLLBACK')
        flash('Uno de los nombres ya está registrado.','error')
    except Exception:
        c.execute('ROLLBACK');raise
    finally:c.close()
    return redirect(url_for('index')+'#partidos')

@app.route('/administracion',methods=['GET','POST'])
def login():
    if session.get('admin'):return redirect(url_for('admin'))
    if request.method=='POST':
        pwd=request.form.get('password','')
        c=db(); row=c.execute('SELECT password_hash FROM admins LIMIT 1').fetchone();c.close()
        if row and check_password_hash(row['password_hash'],pwd):
            session.clear();session['admin']=True;flash('Sesión iniciada.','ok');return redirect(url_for('admin'))
        flash('Contraseña incorrecta o administrador no configurado.','error')
    return render_template('login.html')

@app.post('/salir')
@admin_required
def logout():session.clear();return redirect(url_for('index'))

@app.get('/panel')
@admin_required
def admin():
    c=db();matches=c.execute('SELECT * FROM matches ORDER BY starts_at DESC').fetchall()
    rows=[{'match':m,'players':c.execute('SELECT * FROM registrations WHERE match_id=? ORDER BY id',(m['id'],)).fetchall()} for m in matches];c.close()
    return render_template('admin.html',rows=rows)

def validate_match():
    title=request.form.get('title','').strip()[:100]
    starts=request.form.get('starts_at','')
    category=request.form.get('category','').strip()[:70]
    venue=request.form.get('venue','').strip()[:120]
    capacity=int(request.form.get('capacity','0'))
    price=float(request.form.get('price','-1'))
    datetime.strptime(starts,'%Y-%m-%dT%H:%M')
    if not title or not category or not (1<=capacity<=10000) or not (0<=price<=100000):raise ValueError('Datos inválidos')
    prize=request.form.get('prize','').strip()[:250]
    return title,starts,category,venue,price,capacity,prize

@app.post('/panel/crear')
@admin_required
def create():
    try:
        fields=validate_match()
        with db() as c:c.execute('INSERT INTO matches(title,starts_at,category,venue,price,capacity,prize) VALUES (?,?,?,?,?,?,?)',fields)
        flash('Partido creado.','ok')
    except (ValueError,OverflowError):flash('Revisa los datos del partido.','error')
    return redirect(url_for('admin'))

@app.post('/panel/editar/<int:mid>')
@admin_required
def edit(mid):
    try:
        fields=validate_match()
        with db() as c:
            count=c.execute('SELECT COUNT(*) FROM registrations WHERE match_id=?',(mid,)).fetchone()[0]
            if fields[5]<count:flash('No puedes poner menos cupos que jugadores inscritos.','error')
            else:c.execute('UPDATE matches SET title=?,starts_at=?,category=?,venue=?,price=?,capacity=?,prize=? WHERE id=?',(*fields,mid));flash('Partido actualizado.','ok')
    except (ValueError,OverflowError):flash('Revisa los datos del partido.','error')
    return redirect(url_for('admin'))

@app.post('/panel/eliminar-jugador/<int:rid>')
@admin_required
def delete_player(rid):
    with db() as c:c.execute('DELETE FROM registrations WHERE id=?',(rid,))
    flash('Jugador eliminado.','ok');return redirect(url_for('admin'))

@app.post('/panel/eliminar-partido/<int:mid>')
@admin_required
def delete_match(mid):
    with db() as c:
        c.execute('DELETE FROM registrations WHERE match_id=?',(mid,))
        c.execute('DELETE FROM matches WHERE id=?',(mid,))
    flash('Partido eliminado.','ok');return redirect(url_for('admin'))

if __name__=='__main__':
    app.run(debug=False,host='127.0.0.1',port=int(os.environ.get('PORT','5000')))
