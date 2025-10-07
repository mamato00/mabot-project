

# Mabot: AI Gemini Finance Chatbot

![Mabot Logo](images/logo.png)

[![Streamlit App](https://img.shields.io/badge/Streamlit-App-red?style=for-the-badge&logo=streamlit)](https://share.streamlit.io/)
[![Python](https://img.shields.io/badge/Python-3.9+-blue?style=for-the-badge&logo=python)](https://www.python.org/)

Mabot adalah chatbot keuangan pribadi yang ditenagai oleh AI Gemini, dirancang untuk membantu Anda mencatat dan menganalisis transaksi keuangan dengan mudah. Dengan antarmuka yang intuitif dan kemampuan AI canggih, Mabot membuat pengelolaan keuangan menjadi lebih sederhana dan menyenangkan.

## 🚀 Coba Aplikasi ini!!
https://mabot-project-8grjzqplzeitzb8svw44ar.streamlit.app/

## 🌟 Fitur Utama

### 🔐 Sistem Autentikasi
- **Login & Registrasi Aman**: Sistem login dengan database Neon yang aman
- **Sesi Server-Side**: Manajemen sesi yang aman dengan opsi "Ingat Saya"
- **Proteksi Data**: Data keuangan Anda terlindungi dengan enkripsi password

### 📊 Manajemen Spreadsheet
- **Integrasi Google Sheets**: Hubungkan spreadsheet Anda sendiri untuk menyimpan data
- **Nama Kustom**: Beri nama spreadsheet sesuai keinginan untuk kemudahan identifikasi
- **Multi-Spreadsheet**: Kelola beberapa spreadsheet untuk berbagai kebutuhan keuangan
- **Template Siap Pakai**: Gunakan template yang telah disediakan untuk memulai dengan cepat

### 🤝 Asisten AI Cerdas
- **Pemahaman Bahasa Alami**: Cukup ketik transaksi dalam bahasa sehari-hari
- **Parsing Otomatis**: AI akan memahami dan mengkategorikan transaksi Anda
- **Analisis Data**: Tanyakan tentang pengeluaran, pemasukan, atau tren keuangan Anda
- **Respons Konversasional**: Dapatkan jawaban dalam gaya bahasa yang ramah

### 📈 Visualisasi & Analisis
- **Dashboard Interaktif**: Lihat ringkasan keuangan Anda dengan grafik yang menarik
- **Analisis Kategori**: Ketahui di mana saja uang Anda dialokasikan
- **Tren Waktu**: Pantau perkembangan keuangan Anda dari waktu ke waktu
- **Laporan Detail**: Dapatkan laporan mendalam tentang kondisi keuangan Anda

### ✏️ Manajemen Transaksi
- **Tambah & Edit**: Tambah transaksi baru atau edit yang sudah ada
- **Hapus dengan Konfirmasi**: Hapus transaksi dengan dialog konfirmasi untuk mencegah kesalahan
- **Pagination**: Navigasi mudah melalui ribuan transaksi
- **Pencarian**: Temukan transaksi tertentu dengan fitur pencarian

## 🛠️ Teknologi yang Digunakan

- **Frontend**: [Streamlit](https://streamlit.io/)
- **Backend**: [Python](https://www.python.org/)
- **AI**: [Google Gemini](https://ai.google.dev/)
- **Database**: [Neon](https://neon.tech/)
- **Spreadsheet**: [Google Sheets API](https://developers.google.com/sheets/api)
- **Authentication**: [Passlib](https://passlib.readthedocs.io/)

## 📸 Pratinjau

![Example](images/example_4.png)

## 📋 Prasyarat (Developer)

Sebelum memulai, pastikan Anda telah menyiapkan:

1. **Akun Google Cloud** dengan project yang telah mengaktifkan Google Sheets API dan Google Drive API
2. **Service Account** dengan file kunci JSON
3. **Akun Neon** untuk database
4. **API Key Google Gemini**
5. **Python 3.9+** terinstal di sistem Anda

## 🚀 Instalasi & Setup

### 1. Clone Repository

```bash
git clone https://github.com/username/mabot-finance-chatbot.git
cd mabot-finance-chatbot
```

### 2. Buat Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Untuk Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Konfigurasi Environment

Buat file `.env` berdasarkan template `.env.example`:

```bash
cp .env.example .env
```

Edit file `.env` dengan informasi Anda:

```env
# Database Configuration
DATABASE_URL=postgresql://username:password@host:port/database

# Google Sheets Configuration
GOOGLE_SHEETS_JSON=path/to/your/service-account.json

# Gemini API Configuration
GEMINI_API_KEY=your_gemini_api_key

# Session Management
SECRET_KEY=your_secret_key_here
```

### 5. Setup Google Service Account

1. Buat project di [Google Cloud Console](https://console.cloud.google.com/)
2. Aktifkan Google Sheets API dan Google Drive API
3. Buat service account dan download file kunci JSON
4. Simpan file JSON dan update path di file `.env`

### 6. Jalankan Aplikasi

```bash
streamlit run streamlit-mabot-app.py
```

## 📖 Cara Penggunaan

### 1. Registrasi & Login

Buka aplikasi di browser dan daftarkan akun baru Anda:

1. Klik "Register a new account"
2. Isi username, email, dan password
3. Setelah registrasi, login dengan kredensial Anda
4. Opsional: Centang "Remember me for 30 days" untuk tetap login

### 2. Setup Spreadsheet

1. Klik link template spreadsheet yang disediakan
2. Buat salinan template ke Google Drive Anda
3. Bagikan spreadsheet dengan email service account Anda
4. Kembali ke aplikasi dan masukkan URL spreadsheet
5. Beri nama spreadsheet untuk identifikasi mudah
6. Klik "Hubungkan Spreadsheet"

### 3. Menambah Transaksi

Ada dua cara untuk menambah transaksi:

#### Cara 1: Input Natural Language
1. Ketik transaksi dalam bahasa sehari-hari, misalnya:
   - "Hari ini beli makan siang 35k"
   - "Kemarin dapat gaji 5 juta"
   - "Bayar listrik 250rb bulan ini"
2. AI akan memahami dan mengekstrak informasi transaksi
3. Konfirmasi transaksi dan klik "Simpan Transaksi"

#### Cara 2: Form Manual
1. Buka tab "Tambah Transaksi Manual"
2. Isi semua field yang diperlukan
3. Klik "Tambah & Simpan"

### 4. Analisis Data

1. Buka tab "Riwayat & Ringkasan"
2. Lihat statistik umum di bagian atas
3. Jelajahi tab "Data Tabel", "Visualisasi", atau "Analisis"
4. Gunakan fitur pencarian untuk menemukan transaksi spesifik

### 5. Manajemen Spreadsheet

1. Di sidebar, klik "Change Spreadsheet" untuk beralih spreadsheet
2. Klik "Hapus" untuk menghapus spreadsheet dari akun Anda
3. Tambahkan spreadsheet baru kapan saja

## 📁 Struktur Proyek

```
mabot-finance-chatbot/
├── .env.example              # Template file konfigurasi
├── .gitignore                # File yang diabaikan oleh Git
├── README.md                 # File dokumentasi ini
├── requirements.txt          # Dependencies Python
├── streamlit_app.py          # Aplikasi utama Streamlit
├── config.py                 # Konfigurasi aplikasi
├── database.py               # Operasi database
├── auth.py                   # Autentikasi dan manajemen sesi
├── utils.py                  # Fungsi utilitas
├── sheets_client.py          # Klien Google Sheets
├── gemini_client.py          # Klien API Gemini
└── data_analyzer.py          # Alat analisis data
```

## 🤝 Kontribusi

Kontribusi sangat diterima! Jika Anda ingin berkontribusi pada proyek ini:

1. Fork repository ini
2. Buat branch fitur baru (`git checkout -b feature/AmazingFeature`)
3. Commit perubahan Anda (`git commit -m 'Add some AmazingFeature'`)
4. Push ke branch (`git push origin feature/AmazingFeature`)
5. Buka Pull Request

## 📝 Changelog

### v1.0.0 (Terbaru)
- ✨ Sistem autentikasi dengan database Neon
- ✨ Manajemen sesi server-side dengan "Remember me"
- ✨ Nama spreadsheet kustom
- ✨ Fitur hapus spreadsheet dan transaksi dengan konfirmasi
- ✨ Parsing transaksi dengan AI Gemini
- ✨ Visualisasi data interaktif
- ✨ Manajemen transaksi lengkap (CRUD)

## 📄 Lisensi

Proyek ini open source dan dapat digunakan oleh siapa saja selama tidak melanggar aturan dan etika.

## 🙏 Terima Kasih

- [Hacktiv8](https://www.hacktiv8.com/) untuk pelatihan dan sertifikasi AI tanpa biaya yang keren
- [kode.id](https://www.kode.id/) Maju Bareng AI Bersama Hacktiv8
- [Streamlit](https://streamlit.io/) untuk framework aplikasi web yang luar biasa
- [Google](https://ai.google.dev/) untuk Gemini API
- [LangChain](https://langchain.com/) untuk framework AI
- [Plotly](https://plotly.com/) untuk visualisasi data yang interaktif

## 📞 Kontak

Jika Anda memiliki pertanyaan atau masukan, jangan ragu untuk:

- Membuka [Issue](https://github.com/mamato00/mabot-project)
- Mengirim email ke [fawfawfaw994@gmail.com](fawfawfaw994@gmail.com)

---

<div align="center">
  <p>Dibuat dengan ❤️ vibe coding oleh Saya</p>
  <p>2025 Mabot: AI Gemini Finance Chatbot</p>
</div>
