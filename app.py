from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from modul_buku import buku_bp

app = Flask(__name__)
app.secret_key = 'kunci_rahasia_perpustakaan_kampus'
app.register_blueprint(buku_bp)


def get_db_connection():
    conn = sqlite3.connect('perpustakaan.db')
    conn.row_factory = sqlite3.Row
    return conn


def inisialisasi_database():
    conn = sqlite3.connect('perpustakaan.db')
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS buku (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            judul TEXT NOT NULL,
            penulis TEXT NOT NULL,
            kategori TEXT DEFAULT 'Umum',
            stok_total INTEGER NOT NULL,
            stok_tersedia INTEGER NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mahasiswa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nim VARCHAR(15) UNIQUE,
            username VARCHAR(50) UNIQUE,
            password TEXT,
            peran VARCHAR(20) DEFAULT 'mahasiswa'
        )
    """)

    cursor.execute("PRAGMA table_info(mahasiswa)")
    kolom_ada = [row[1] for row in cursor.fetchall()]
    if 'username' not in kolom_ada:
        cursor.execute("ALTER TABLE mahasiswa ADD COLUMN username VARCHAR(50)")
    if 'password' not in kolom_ada:
        cursor.execute("ALTER TABLE mahasiswa ADD COLUMN password TEXT")
    if 'peran' not in kolom_ada:
        cursor.execute("ALTER TABLE mahasiswa ADD COLUMN peran VARCHAR(20) DEFAULT 'mahasiswa'")

    cursor.execute('SELECT COUNT(*) FROM buku')
    if cursor.fetchone()[0] == 0:
        buku_sampel = [
            ('Pemrograman Python Dasar', 'Guido van Rossum', 'Pemrograman', 5, 5),
            ('Sistem Terdistribusi & Middleware', 'Andrew S. Tanenbaum', 'Sistem Terdistribusi & IoT', 3, 3),
            ('Algoritma dan Struktur Data', 'Donald Knuth', 'Algoritma & Struktur Data', 4, 4),
            ('Internet of Things (IoT) dengan ESP32', 'Ahmad Rizal', 'Sistem Terdistribusi & IoT', 2, 2),
            ('Pengantar Basis Data & SQL', 'Eko Kurniawan', 'Basis Data & Jaringan', 6, 6)
        ]
        cursor.executemany("""
            INSERT INTO buku (judul, penulis, kategori, stok_total, stok_tersedia)
            VALUES (?, ?, ?, ?, ?)
        """, buku_sampel)

    cursor.execute("SELECT COUNT(*) FROM mahasiswa WHERE username = 'admin'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO mahasiswa (nim, username, password, peran)
            VALUES (?, ?, ?, ?)
        """, ('ADM001', 'admin', generate_password_hash('admin123'), 'admin'))

    conn.commit()
    conn.close()


inisialisasi_database()


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        if session.get('peran') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('beranda'))

    if request.method == 'POST':
        nim = request.form.get('nim', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not nim or not username or not password:
            flash("Data tidak boleh kosong!", "danger")
            return render_template('register.html')

        conn = get_db_connection()

        if conn.execute("SELECT * FROM mahasiswa WHERE nim = ?", (nim,)).fetchone():
            conn.close()
            flash("NIM sudah terdaftar!", "warning")
            return render_template('register.html')

        if conn.execute("SELECT * FROM mahasiswa WHERE username = ?", (username,)).fetchone():
            conn.close()
            flash("Username sudah digunakan, pilih username lain!", "warning")
            return render_template('register.html')

        conn.execute("""
            INSERT INTO mahasiswa (nim, username, password, peran)
            VALUES (?, ?, ?, ?)
        """, (nim, username, generate_password_hash(password), 'mahasiswa'))
        conn.commit()
        conn.close()

        flash("Registrasi berhasil! Silakan login menggunakan akun mahasiswa Anda.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        if session.get('peran') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('beranda'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash("Username dan password wajib diisi!", "danger")
            return render_template('login.html')

        conn = get_db_connection()
        anggota = conn.execute("SELECT * FROM mahasiswa WHERE username = ?", (username,)).fetchone()
        conn.close()

        if anggota is None or not check_password_hash(anggota['password'], password):
            flash("Login gagal! Username atau password salah.", "danger")
            return render_template('login.html')

        session['user_id'] = anggota['id']
        session['nim'] = anggota['nim']
        session['username'] = anggota['username']
        session['peran'] = anggota['peran']

        if anggota['peran'] == 'admin':
            flash(f"Login Admin berhasil! Selamat datang, {anggota['username']}.", "success")
            return redirect(url_for('admin_dashboard'))
        else:
            flash(f"Selamat datang, {anggota['username']}! Silakan pilih buku untuk dipinjam.", "success")
            return redirect(url_for('beranda'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("Anda telah keluar dari sistem.", "info")
    return redirect(url_for('login'))


@app.route('/')
def beranda():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('peran') == 'admin':
        return redirect(url_for('admin_dashboard'))

    kata_kunci = request.args.get('cari', '').strip()
    kategori_filter = request.args.get('kategori', '').strip()

    daftar_kategori = [
        'Pemrograman',
        'Algoritma & Struktur Data',
        'Basis Data & Jaringan',
        'Sistem Terdistribusi & IoT',
        'Umum',
        'Lainnya'
    ]

    conn = get_db_connection()
    query = "SELECT * FROM buku WHERE 1=1"
    params = []

    if kata_kunci:
        query += " AND (judul LIKE ? OR penulis LIKE ?)"
        params.extend([f'%{kata_kunci}%', f'%{kata_kunci}%'])

    if kategori_filter:
        query += " AND kategori = ?"
        params.append(kategori_filter)

    query += " ORDER BY judul ASC"
    daftar_buku = conn.execute(query, params).fetchall()
    conn.close()

    return render_template(
        'index.html',
        daftar_buku=daftar_buku,
        kata_kunci=kata_kunci,
        kategori_filter=kategori_filter,
        daftar_kategori=daftar_kategori
    )


@app.route('/pinjam/<int:buku_id>', methods=['POST'])
def pinjam_buku(buku_id):
    if 'user_id' not in session or session.get('peran') != 'mahasiswa':
        flash("Hanya mahasiswa yang dapat meminjam buku!", "warning")
        return redirect(url_for('login'))

    conn = get_db_connection()
    buku = conn.execute("SELECT * FROM buku WHERE id = ?", (buku_id,)).fetchone()

    if buku and buku['stok_tersedia'] > 0:
        conn.execute("""
            UPDATE buku
            SET stok_tersedia = stok_tersedia - 1
            WHERE id = ?
        """, (buku_id,))
        conn.commit()
        flash(f"Buku '{buku['judul']}' berhasil dipinjam!", "success")

    conn.close()
    return redirect(url_for('beranda'))


@app.route('/kembalikan/<int:buku_id>', methods=['POST'])
def kembalikan_buku(buku_id):
    if 'user_id' not in session or session.get('peran') != 'mahasiswa':
        flash("Hanya mahasiswa yang dapat mengembalikan buku!", "warning")
        return redirect(url_for('login'))

    conn = get_db_connection()
    buku = conn.execute("SELECT * FROM buku WHERE id = ?", (buku_id,)).fetchone()

    if buku and buku['stok_tersedia'] < buku['stok_total']:
        conn.execute("""
            UPDATE buku
            SET stok_tersedia = stok_tersedia + 1
            WHERE id = ?
        """, (buku_id,))
        conn.commit()
        flash(f"Buku '{buku['judul']}' berhasil dikembalikan!", "info")

    conn.close()
    return redirect(url_for('beranda'))

@app.route('/mahasiswa')
def daftar_mahasiswa():
    if 'user_id' not in session or session.get('peran') != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    semua_mahasiswa = conn.execute("SELECT * FROM mahasiswa ORDER BY id ASC").fetchall()
    conn.close()
    return render_template('daftar_mahasiswa.html', daftar_mahasiswa=semua_mahasiswa)


app.add_url_rule('/admin', endpoint='admin_dashboard', view_func=app.view_functions['buku.admin_dashboard'])
app.add_url_rule('/tambah', endpoint='tambah_buku', view_func=app.view_functions['buku.tambah_buku'], methods=['GET', 'POST'])
app.add_url_rule('/edit/<int:buku_id>', endpoint='edit_buku', view_func=app.view_functions['buku.edit_buku'], methods=['GET', 'POST'])
app.add_url_rule('/hapus/<int:buku_id>', endpoint='hapus_buku', view_func=app.view_functions['buku.hapus_buku'], methods=['POST'])

if __name__ == '__main__':
    app.run(debug=True)
