# app.py - Sistem Kasir Toko Plastik
from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)
DATABASE = 'toko_plastik.db'

# Inisialisasi database
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # Buat tabel produk
    c.execute('''CREATE TABLE IF NOT EXISTS produk (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kode TEXT UNIQUE,
                nama TEXT,
                kategori TEXT,
                harga INTEGER,
                stok INTEGER,
                satuan TEXT,
                supplier TEXT)''')
    
    # Buat tabel transaksi
    c.execute('''CREATE TABLE IF NOT EXISTS transaksi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tanggal TEXT,
                total_belanja INTEGER,
                dibayar INTEGER,
                kembalian INTEGER)''')
    
    # Buat tabel detail_transaksi
    c.execute('''CREATE TABLE IF NOT EXISTS detail_transaksi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_transaksi INTEGER,
                id_produk INTEGER,
                jumlah INTEGER,
                subtotal INTEGER,
                FOREIGN KEY(id_transaksi) REFERENCES transaksi(id),
                FOREIGN KEY(id_produk) REFERENCES produk(id))''')
    
    # Tambah data contoh
    c.execute("SELECT COUNT(*) FROM produk")
    if c.fetchone()[0] == 0:
        sample_products = [
            ('PL001', 'Plastik Klip 1kg', 'Kemasan', 15000, 100, 'pack', 'Plastik Jaya'),
            ('PL002', 'Plastik Roll 30cm', 'Kemasan', 25000, 50, 'roll', 'Sinar Plastik'),
            ('PL003', 'Kantong Sampah Hitam', 'Kebersihan', 40000, 75, 'pack', 'Clean Env'),
            ('PL004', 'Plastik Wrap 45cm', 'Pembungkus', 32000, 40, 'roll', 'Wrap Master'),
            ('PL005', 'Plastik Mika A4', 'Dokumen', 5000, 200, 'pack', 'Mika Corp')
        ]
        c.executemany('''INSERT INTO produk (kode, nama, kategori, harga, stok, satuan, supplier)
                      VALUES (?, ?, ?, ?, ?, ?, ?)''', sample_products)
    
    conn.commit()
    conn.close()

init_db()

# Fungsi bantuan database
def query_db(query, args=(), one=False):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.commit()
    conn.close()
    return (rv[0] if rv else None) if one else rv

# Rute Halaman Utama
@app.route('/')
def dashboard():
    # Hitung statistik
    total_produk = query_db("SELECT COUNT(*) FROM produk")[0][0]
    total_stok = query_db("SELECT SUM(stok) FROM produk")[0][0]
    total_transaksi = query_db("SELECT COUNT(*) FROM transaksi")[0][0]
    
    # Produk hampir habis
    produk_habis = query_db("SELECT * FROM produk WHERE stok < 10 ORDER BY stok ASC LIMIT 5")
    
    return render_template('dashboard.html', 
                           total_produk=total_produk,
                           total_stok=total_stok,
                           total_transaksi=total_transaksi,
                           produk_habis=produk_habis)

# Manajemen Produk
@app.route('/produk')
def produk():
    all_products = query_db("SELECT * FROM produk")
    return render_template('produk.html', produk=all_products)

@app.route('/tambah_produk', methods=['GET', 'POST'])
def tambah_produk():
    if request.method == 'POST':
        data = request.form
        query_db('''INSERT INTO produk (kode, nama, kategori, harga, stok, satuan, supplier)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
                 (data['kode'], data['nama'], data['kategori'], data['harga'], 
                  data['stok'], data['satuan'], data['supplier']))
        return redirect(url_for('produk'))
    return render_template('tambah_produk.html')

@app.route('/edit_produk/<int:id>', methods=['GET', 'POST'])
def edit_produk(id):
    if request.method == 'POST':
        data = request.form
        query_db('''UPDATE produk SET 
                 kode=?, nama=?, kategori=?, harga=?, stok=?, satuan=?, supplier=?
                 WHERE id=?''',
                 (data['kode'], data['nama'], data['kategori'], data['harga'], 
                  data['stok'], data['satuan'], data['supplier'], id))
        return redirect(url_for('produk'))
    
    produk = query_db("SELECT * FROM produk WHERE id = ?", [id], one=True)
    return render_template('edit_produk.html', produk=produk)

@app.route('/hapus_produk/<int:id>')
def hapus_produk(id):
    query_db("DELETE FROM produk WHERE id = ?", [id])
    return redirect(url_for('produk'))

# Sistem Kasir
@app.route('/kasir')
def kasir():
    produk = query_db("SELECT id, kode, nama, harga, stok, satuan FROM produk WHERE stok > 0")
    return render_template('kasir.html', produk=produk)

@app.route('/proses_transaksi', methods=['POST'])
def proses_transaksi():
    data = request.get_json()
    keranjang = data['keranjang']
    total = data['total']
    dibayar = data['dibayar']
    kembalian = dibayar - total
    
    # Simpan transaksi
    tanggal = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    transaksi_id = query_db(
        "INSERT INTO transaksi (tanggal, total_belanja, dibayar, kembalian) VALUES (?, ?, ?, ?) RETURNING id",
        (tanggal, total, dibayar, kembalian),
        one=True
    )[0]
    
    # Simpan detail transaksi dan update stok
    for item in keranjang:
        query_db(
            "INSERT INTO detail_transaksi (id_transaksi, id_produk, jumlah, subtotal) VALUES (?, ?, ?, ?)",
            (transaksi_id, item['id'], item['jumlah'], item['subtotal'])
        )
        # Kurangi stok
        query_db("UPDATE produk SET stok = stok - ? WHERE id = ?", (item['jumlah'], item['id']))
    
    return jsonify({
        'success': True,
        'transaksi_id': transaksi_id,
        'kembalian': kembalian
    })

# Riwayat Transaksi
@app.route('/transaksi')
def transaksi():
    transaksi = query_db("SELECT * FROM transaksi ORDER BY tanggal DESC")
    return render_template('transaksi.html', transaksi=transaksi)

@app.route('/detail_transaksi/<int:id>')
def detail_transaksi(id):
    transaksi = query_db("SELECT * FROM transaksi WHERE id = ?", [id], one=True)
    detail = query_db('''SELECT d.jumlah, d.subtotal, p.nama, p.harga, p.satuan 
                      FROM detail_transaksi d 
                      JOIN produk p ON d.id_produk = p.id 
                      WHERE d.id_transaksi = ?''', [id])
    return render_template('detail_transaksi.html', transaksi=transaksi, detail=detail)

if __name__ == '__main__':
    app.run(debug=True)