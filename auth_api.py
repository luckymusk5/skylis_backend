from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import psycopg2.extras
import bcrypt
import jwt
import os
import re
from datetime import datetime, timedelta, timezone
from functools import wraps

app = Flask(__name__)
CORS(app, origins="*")

# ── Config ──────────────────────────────────────
DB_HOST     = os.getenv('AUTH_DB_HOST', 'auth-db')
DB_PORT     = os.getenv('AUTH_DB_PORT', '5432')
DB_NAME     = os.getenv('AUTH_DB_NAME', 'auth_db')
DB_USER     = os.getenv('AUTH_DB_USER', 'auth_user')
DB_PASSWORD = os.getenv('AUTH_DB_PASSWORD', 'auth_pass_skylis')
JWT_SECRET  = os.getenv('JWT_SECRET', 'skylis_jwt_secret_change_in_prod')
JWT_ALGO    = 'HS256'
ACCESS_EXP  = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '60'))
REFRESH_EXP = int(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS', '7'))

# ── DB ──────────────────────────────────────────
def get_db():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor
    )

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            prenom VARCHAR(100) NOT NULL,
            nom VARCHAR(100) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            telephone VARCHAR(30),
            password_hash VARCHAR(255) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            is_verified BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            token VARCHAR(500) NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS search_history (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            query VARCHAR(500) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS login_attempts (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255),
            ip_address VARCHAR(50),
            success BOOLEAN,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("✅ DB initialisée")

# ── JWT ─────────────────────────────────────────
def make_access_token(user_id, email):
    payload = {
        'sub': user_id,
        'email': email,
        'type': 'access',
        'exp': datetime.now(timezone.utc) + timedelta(minutes=ACCESS_EXP),
        'iat': datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def make_refresh_token(user_id):
    payload = {
        'sub': user_id,
        'type': 'refresh',
        'exp': datetime.now(timezone.utc) + timedelta(days=REFRESH_EXP),
        'iat': datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def jwt_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'error': 'Token manquant'}), 401
        token = auth.split(' ', 1)[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
            if payload.get('type') != 'access':
                return jsonify({'error': 'Token invalide'}), 401
            request.user_id = payload['sub']
            request.user_email = payload['email']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expiré'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token invalide'}), 401
        return f(*args, **kwargs)
    return decorated

# ── Helpers ─────────────────────────────────────
def valid_email(email):
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email))

def get_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()

def log_attempt(email, success):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO login_attempts (email, ip_address, success) VALUES (%s, %s, %s)",
                    (email, get_ip(), success))
        conn.commit()
        cur.close()
        conn.close()
    except: pass

def check_brute_force(email):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) as cnt FROM login_attempts
            WHERE email=%s AND success=FALSE
            AND created_at > NOW() - INTERVAL '15 minutes'
        """, (email,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row['cnt'] >= 5
    except:
        return False

# ══════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════

@app.route('/health', methods=['GET'])
def health():
    try:
        conn = get_db()
        conn.close()
        return jsonify({'status': 'ok', 'db': 'connected'})
    except Exception as e:
        return jsonify({'status': 'error', 'db': str(e)}), 500

# ── REGISTER ────────────────────────────────────
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    prenom   = (data.get('prenom') or '').strip()
    nom      = (data.get('nom') or '').strip()
    email    = (data.get('email') or '').strip().lower()
    tel      = (data.get('telephone') or '').strip()
    password = (data.get('password') or '')

    # Validation
    if not prenom or not nom:
        return jsonify({'error': 'Prénom et nom requis'}), 400
    if not valid_email(email):
        return jsonify({'error': 'Email invalide'}), 400
    if len(password) < 8:
        return jsonify({'error': 'Mot de passe trop court (min 8 caractères)'}), 400

    # Hash password
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()

    try:
        conn = get_db()
        cur = conn.cursor()

        # Check email existant
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            cur.close(); conn.close()
            return jsonify({'error': 'Cet email est déjà utilisé'}), 409

        # Créer utilisateur
        cur.execute("""
            INSERT INTO users (prenom, nom, email, telephone, password_hash)
            VALUES (%s, %s, %s, %s, %s) RETURNING id, prenom, nom, email, telephone, created_at
        """, (prenom, nom, email, tel or None, pw_hash))
        user = dict(cur.fetchone())
        conn.commit()

        # Tokens
        access  = make_access_token(user['id'], user['email'])
        refresh = make_refresh_token(user['id'])

        # Stocker refresh token
        cur.execute("""
            INSERT INTO refresh_tokens (user_id, token, expires_at)
            VALUES (%s, %s, %s)
        """, (user['id'], refresh, datetime.now(timezone.utc) + timedelta(days=REFRESH_EXP)))
        conn.commit()
        cur.close(); conn.close()

        user.pop('password_hash', None)
        if user.get('created_at'):
            user['created_at'] = user['created_at'].isoformat()

        return jsonify({
            'access_token': access,
            'refresh_token': refresh,
            'token_type': 'Bearer',
            'expires_in': ACCESS_EXP * 60,
            'user': user
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── LOGIN ───────────────────────────────────────
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email    = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '')

    if not email or not password:
        return jsonify({'error': 'Email et mot de passe requis'}), 400

    # Anti brute-force
    if check_brute_force(email):
        return jsonify({'error': 'Trop de tentatives. Attendez 15 minutes.'}), 429

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email=%s AND is_active=TRUE", (email,))
        user = cur.fetchone()

        if not user or not bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
            log_attempt(email, False)
            cur.close(); conn.close()
            return jsonify({'error': 'Email ou mot de passe incorrect'}), 401

        log_attempt(email, True)

        access  = make_access_token(user['id'], user['email'])
        refresh = make_refresh_token(user['id'])

        # Stocker refresh token
        cur.execute("""
            INSERT INTO refresh_tokens (user_id, token, expires_at)
            VALUES (%s, %s, %s)
        """, (user['id'], refresh, datetime.now(timezone.utc) + timedelta(days=REFRESH_EXP)))
        conn.commit()
        cur.close(); conn.close()

        return jsonify({
            'access_token': access,
            'refresh_token': refresh,
            'token_type': 'Bearer',
            'expires_in': ACCESS_EXP * 60,
            'user': {
                'id': user['id'],
                'prenom': user['prenom'],
                'nom': user['nom'],
                'email': user['email'],
                'telephone': user['telephone']
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── REFRESH TOKEN ───────────────────────────────
@app.route('/refresh', methods=['POST'])
def refresh():
    data = request.get_json() or {}
    refresh_token = data.get('refresh_token', '')
    try:
        payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=[JWT_ALGO])
        if payload.get('type') != 'refresh':
            return jsonify({'error': 'Token invalide'}), 401

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT rt.*, u.email FROM refresh_tokens rt
            JOIN users u ON u.id = rt.user_id
            WHERE rt.token=%s AND rt.expires_at > NOW()
        """, (refresh_token,))
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            return jsonify({'error': 'Token expiré ou révoqué'}), 401

        access = make_access_token(row['user_id'], row['email'])
        cur.close(); conn.close()
        return jsonify({'access_token': access, 'token_type': 'Bearer', 'expires_in': ACCESS_EXP * 60})

    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token expiré'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── LOGOUT ──────────────────────────────────────
@app.route('/logout', methods=['POST'])
@jwt_required
def logout():
    data = request.get_json() or {}
    refresh_token = data.get('refresh_token', '')
    try:
        conn = get_db()
        cur = conn.cursor()
        if refresh_token:
            cur.execute("DELETE FROM refresh_tokens WHERE token=%s AND user_id=%s",
                        (refresh_token, request.user_id))
        else:
            cur.execute("DELETE FROM refresh_tokens WHERE user_id=%s", (request.user_id,))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({'message': 'Déconnexion réussie'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── ME ──────────────────────────────────────────
@app.route('/me', methods=['GET'])
@jwt_required
def me():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, prenom, nom, email, telephone, created_at FROM users WHERE id=%s",
                    (request.user_id,))
        user = dict(cur.fetchone())
        cur.close(); conn.close()
        if user.get('created_at'):
            user['created_at'] = user['created_at'].isoformat()
        return jsonify({'user': user})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── SEARCH HISTORY ──────────────────────────────
@app.route('/user/history', methods=['GET'])
@jwt_required
def get_history():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT query, created_at FROM search_history
            WHERE user_id=%s ORDER BY created_at DESC LIMIT 20
        """, (request.user_id,))
        rows = [{'query': r['query'], 'date': r['created_at'].isoformat()} for r in cur.fetchall()]
        cur.close(); conn.close()
        return jsonify({'history': rows})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/user/history', methods=['POST'])
@jwt_required
def save_history():
    data = request.get_json() or {}
    query = (data.get('query') or '').strip()
    if not query:
        return jsonify({'error': 'Query vide'}), 400
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO search_history (user_id, query) VALUES (%s, %s)",
                    (request.user_id, query[:500]))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({'message': 'Historique sauvegardé'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── PASSWORD RESET ──────────────────────────────
@app.route('/password/reset', methods=['POST'])
def password_reset_request():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    # TODO: envoyer email via SendGrid
    return jsonify({'message': 'Si cet email existe, un lien de réinitialisation a été envoyé.'})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=int(os.getenv('FLASK_PORT', 5001)), debug=False)
