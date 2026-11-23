from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import sqlite3

buku_bp = Blueprint('buku', __name__)

KATEGORI_LIST = [
    'Pemrograman',
    'Algoritma & Struktur Data',
    'Basis Data & Jaringan',
    'Sistem Terdistribusi & IoT',
    'Umum'
]


def get_db_connection():
    conn = sqlite3.connect('perpustakaan.db')
    conn.row_factory = sqlite3.Row
    return conn


def init_tabel_buku():
    """Memastikan kolom kategori tersedia di tabel buku tanpa merusak data lama."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(buku)")
    kolom_ada = [row[1] for row in cursor.fetchall()]

    if 'kategori' not in kolom_ada:
        cursor.execute("ALTER TABLE buku ADD COLUMN kategori TEXT DEFAULT 'Umum'")
        cursor.execute("UPDATE buku SET kategori = 'Pemrograman' WHERE judul LIKE '%Python%'")
        cursor.execute("UPDATE buku SET kategori = 'Algoritma & Struktur Data' WHERE judul LIKE '%Algoritma%'")
        cursor.execute("UPDATE buku SET kategori = 'Basis Data & Jaringan' WHERE judul LIKE '%Basis Data%'")
        cursor.execute("UPDATE buku SET kategori = 'Sistem Terdistribusi & IoT' WHERE judul LIKE '%Terdistribusi%' OR judul LIKE '%IoT%'")

    conn.commit()
    conn.close()


init_tabel_buku()


# ==========================================
# MODUL DATA BUKU (CRUD + VALIDASI + KATEGORI)
# ==========================================

@buku_bp.route('/admin', endpoint='admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('peran') != 'admin':
        flash("Akses ditolak! Halaman ini khusus Admin Perpustakaan.", "danger")
        return redirect(url_for('beranda'))

    kata_kunci = request.args.get('cari', '').strip()
    filter_kategori = request.args.get('kategori', '').strip()
    conn = get_db_connection()

    query = "SELECT * FROM buku WHERE 1=1"
    params = []

    if kata_kunci:
        query += " AND (judul LIKE ? OR penulis LIKE ?)"
        params.extend([f'%{kata_kunci}%', f'%{kata_kunci}%'])

    if filter_kategori:
        query += " AND kategori = ?"
        params.append(filter_kategori)

    query += " ORDER BY judul ASC"
    daftar_buku = conn.execute(query, params).fetchall()
    conn.close()

    return render_template(
        'admin_dashboard.html',
        daftar_buku=daftar_buku,
        kata_kunci=kata_kunci,
        filter_kategori=filter_kategori,
        kategori_list=KATEGORI_LIST
    )


@buku_bp.route('/tambah', methods=['GET', 'POST'], endpoint='tambah_buku')
def tambah_buku():
    if session.get('peran') != 'admin':
        flash("Akses ditolak! Hanya Admin Perpustakaan yang dapat menambah buku.", "danger")
        return redirect(url_for('beranda'))

    if request.method == 'POST':
        judul = request.form.get('judul', '').strip()
        penulis = request.form.get('penulis', '').strip()
        kategori = request.form.get('kategori', 'Umum').strip()
        stok_raw = request.form.get('stok', '0').strip()

        if not judul or not penulis:
            flash("Judul dan penulis wajib diisi!", "danger")
            return render_template('tambah_buku.html', kategori_list=KATEGORI_LIST)

        try:
            stok = int(stok_raw)
            if stok <= 0:
                raise ValueError
        except ValueError:
            flash("Jumlah stok harus berupa angka lebih dari 0!", "danger")
            return render_template('tambah_buku.html', kategori_list=KATEGORI_LIST)

        conn = get_db_connection()
        duplikat = conn.execute(
            "SELECT id FROM buku WHERE LOWER(judul) = LOWER(?)", (judul,)
        ).fetchone()

        if duplikat:
            conn.close()
            flash(f"Gagal! Buku dengan judul '{judul}' sudah terdaftar di katalog.", "warning")
            return render_template('tambah_buku.html', kategori_list=KATEGORI_LIST)

        conn.execute("""
            INSERT INTO buku (judul, penulis, kategori, stok_total, stok_tersedia)
            VALUES (?, ?, ?, ?, ?)
        """, (judul, penulis, kategori, stok, stok))
        conn.commit()
        conn.close()

        flash(f"Buku '{judul}' ({kategori}) berhasil ditambahkan ke katalog!", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('tambah_buku.html', kategori_list=KATEGORI_LIST)


@buku_bp.route('/edit/<int:buku_id>', methods=['GET', 'POST'], endpoint='edit_buku')
def edit_buku(buku_id):
    if session.get('peran') != 'admin':
        flash("Akses ditolak! Hanya Admin Perpustakaan yang dapat mengedit buku.", "danger")
        return redirect(url_for('beranda'))

    conn = get_db_connection()
    buku = conn.execute("SELECT * FROM buku WHERE id = ?", (buku_id,)).fetchone()

    if buku is None:
        conn.close()
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        judul = request.form.get('judul', '').strip()
        penulis = request.form.get('penulis', '').strip()
        kategori = request.form.get('kategori', 'Umum').strip()
        stok_raw = request.form.get('stok', '0').strip()

        if not judul or not penulis:
            conn.close()
            flash("Judul dan penulis tidak boleh kosong!", "danger")
            return render_template('edit_buku.html', buku=buku, kategori_list=KATEGORI_LIST)

        try:
            stok_baru = int(stok_raw)
            if stok_baru <= 0:
                raise ValueError
        except ValueError:
            conn.close()
            flash("Stok total harus berupa angka lebih dari 0!", "danger")
            return render_template('edit_buku.html', buku=buku, kategori_list=KATEGORI_LIST)

        duplikat = conn.execute(
            "SELECT id FROM buku WHERE LOWER(judul) = LOWER(?) AND id != ?",
            (judul, buku_id)
        ).fetchone()

        if duplikat:
            conn.close()
            flash(f"Gagal update! Judul '{judul}' sudah dipakai oleh buku lain.", "warning")
            return render_template('edit_buku.html', buku=buku, kategori_list=KATEGORI_LIST)

        jumlah_dipinjam = buku['stok_total'] - buku['stok_tersedia']
        if stok_baru >= jumlah_dipinjam:
            stok_tersedia_baru = stok_baru - jumlah_dipinjam
            conn.execute("""
                UPDATE buku
                SET judul = ?, penulis = ?, kategori = ?, stok_total = ?, stok_tersedia = ?
                WHERE id = ?
            """, (judul, penulis, kategori, stok_baru, stok_tersedia_baru, buku_id))
            conn.commit()
            flash(f"Data buku '{judul}' berhasil diperbarui!", "success")
        else:
            flash("Gagal update! Stok total baru tidak boleh lebih kecil dari jumlah buku yang sedang dipinjam.", "danger")

        conn.close()
        return redirect(url_for('admin_dashboard'))

    conn.close()
    return render_template('edit_buku.html', buku=buku, kategori_list=KATEGORI_LIST)


@buku_bp.route('/hapus/<int:buku_id>', methods=['POST'], endpoint='hapus_buku')
def hapus_buku(buku_id):
    if session.get('peran') != 'admin':
        flash("Akses ditolak! Hanya Admin Perpustakaan yang dapat menghapus buku.", "danger")
        return redirect(url_for('beranda'))

    conn = get_db_connection()
    buku = conn.execute("SELECT * FROM buku WHERE id = ?", (buku_id,)).fetchone()
    if buku:
        jumlah_dipinjam = buku['stok_total'] - buku['stok_tersedia']
        if jumlah_dipinjam > 0:
            flash(f"Buku '{buku['judul']}' tidak bisa dihapus karena masih ada {jumlah_dipinjam} buku yang dipinjam!", "danger")
        else:
            conn.execute("DELETE FROM buku WHERE id = ?", (buku_id,))
            conn.commit()
            flash(f"Buku '{buku['judul']}' berhasil dihapus!", "info")

    conn.close()
    return redirect(url_for('admin_dashboard'))
