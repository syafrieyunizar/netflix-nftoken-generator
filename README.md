# Netflix NFToken Generator

Generate Netflix **auto-login links** from session cookies.

Link format: `https://netflix.com/?nftoken=...`

Siapapun yang membuka link tersebut akan **langsung masuk** ke akun Netflix tanpa perlu email/password.

## Fitur

- Input: cookies Netflix (`NetflixId` wajib, `SecureNetflixId` + `nfvdid` opsional)
- Output: link `https://netflix.com/?nftoken=...`
- Deteksi expiry link (~65 menit TTL)
- Mode daemon: auto-refresh link sebelum expired
- Notifikasi Telegram opsional setiap refresh
- Simpan link ke file untuk di-share
- Single file Python, minimal dependency

## TTL (Berapa lama link bertahan?)

nftoken memiliki TTL **~65 menit (1 jam)** sejak di-generate.

Setelah expired, link tidak bisa dipakai untuk login.

Solusi: gunakan **mode daemon** untuk auto-refresh link sebelum expired.

## Cara Kerja

```
1. User login Netflix di browser
2. Ambil cookie NetflixId dari DevTools
3. Script call Netflix API (ios.prod.ftl.netflix.com)
4. API return nftoken + expiry timestamp
5. Script build link: https://netflix.com/?nftoken=...
6. Share link ke orang lain
7. Orang lain buka link → auto-login Netflix
```

## Install

```bash
git clone https://github.com/syafrieyunizar/netflix-nftoken-generator.git
cd netflix-nftoken-generator
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Agent Quick Start (untuk Hermes / AI Agent)

Jika Anda adalah AI agent yang baru di-deploy ke VPS baru dan user memberikan link repo ini, ikuti langkah berikut:

### 1. Setup sekali

```bash
cd /home/<user>
git clone https://github.com/syafrieyunizar/netflix-nftoken-generator.git
cd netflix-nftoken-generator
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 2. Minta cookie dari user (1x per akun)

User perlu kirim cookie `NetflixId` dari browser yang sedang login Netflix.
Simpan ke config per akun:

```bash
cp config.example.json config-friendshouse.json
# Edit config-friendshouse.json, isi netflix_id, secure_netflix_id, nfvdid
```

Multi-account: buat config terpisah per akun:

```
config-friendshouse.json   → Akun 1
config-family.json         → Akun 2
config-personal.json       → Akun 3
```

### 3. Saat user minta link (on-demand)

User: "Minta link Netflix Friendshouse"

Agent jalankan:

```bash
cd /home/<user>/netflix-nftoken-generator
.venv/bin/python3 nftoken_generator.py --config config-friendshouse.json
```

Parse output, kirim link ke user. Link fresh, TTL ~65 menit.

### 4. Kalau cookie expired

Script return: `No token in response` atau `value: {}`

Minta user kirim cookie `NetflixId` baru dari browser.
Update config, jalan lagi.

### 5. Simpan info akun ke memory/fact_store

Agar ingat across sessions:

```
Netflix account "Friendshouse" → config di /home/<user>/netflix-nftoken-generator/config-friendshouse.json
Netflix account "Family" → config di /home/<user>/netflix-nftoken-generator/config-family.json
```

### 6. Mode operasi

| Mode | Kapan dipakai | Command |
|------|--------------|---------|
| On-demand | User minta link → generate saat itu juga | `python3 nftoken_generator.py --config config-XXX.json` |
| Daemon 24 jam | Link selalu ready, auto-refresh | `python3 nftoken_generator.py --config config-XXX.json --daemon` |

**Rekomendasi**: On-demand. Link selalu fresh, tidak buang API call.

### 7. Jangan commit secret

- `config.json` dan `config-*.json` berisi cookie = **SECRET**
- Sudah di `.gitignore`
- Jangan pernah `git add config*.json`
- Jangan push cookie ke GitHub

## Cara Ambil Cookie Netflix

### A. Ambil `NetflixId` (wajib)

1. Buka `https://www.netflix.com` di browser
2. Login ke akun Netflix
3. Buka DevTools (tekan `F12`)
4. Tab **Application** → Sidebar **Cookies** → `https://www.netflix.com`
5. Cari cookie bernama `NetflixId`
6. Copy **value**-nya

### B. Ambil `SecureNetflixId` (opsional, tapi disarankan)

Dari tempat yang sama, cari cookie `SecureNetflixId`, copy valuenya.

### C. Ambil `nfvdid` (opsional)

Dari tempat yang sama, cari cookie `nfvdid`, copy valuenya.

### D. Alternatif: Export semua cookies

Pakai browser extension seperti **Cookie-Editor** atau **EditThisCookie**:
1. Buka `netflix.com` (sudah login)
2. Klik extension → Export cookies (JSON format)
3. Simpan ke file `cookies.json`

## Konfigurasi

```bash
cp config.example.json config.json
```

Edit `config.json`:

```json
{
  "netflix_id": "PASTE_NetflixId_VALUE_HERE",
  "secure_netflix_id": "PASTE_SecureNetflixId_VALUE_HERE",
  "nfvdid": "PASTE_nfvdid_VALUE_HERE",
  "refresh_interval_sec": 3000,
  "telegram": {
    "enabled": false,
    "bot_token": "",
    "chat_id": ""
  },
  "output_file": "link.txt"
}
```

## Pakai: Mode One-Shot

Generate satu link, print, exit:

```bash
python3 nftoken_generator.py --config config.json
```

Output:

```
============================================================
  Netflix NFToken Generated
============================================================

  Link:    https://netflix.com/?nftoken=<TOKEN>...

  Expires: 2026-08-18 12:55:53
  TTL:     3888 seconds (64 minutes)

  How to use:
    Send the link above to anyone.
    When they open it, they will be auto-logged into
    the Netflix account (no password needed).

  Note:
    - Link expires in ~65 minutes
    - Link may be one-time use
    - Old links stop working after generating a new one
============================================================
```

## Pakai: Mode Daemon (Auto-Refresh)

Refresh link otomatis sebelum expired:

```bash
python3 nftoken_generator.py --config config.json --daemon
```

Output:

```
[11:51:05] Daemon mode started
[11:51:05]   Refresh interval: 3000 seconds (50 minutes)
[11:51:05] NFToken generated | TTL: 64 min | Expires: 2026-08-18 12:55:53
[11:51:05] Link: https://netflix.com/?nftoken=<TOKEN>...
[11:51:05] Written to: link.txt
[11:51:05] Next refresh in 50 minutes...
```

Custom interval (contoh: refresh tiap 30 menit):

```bash
python3 nftoken_generator.py --config config.json --daemon --interval 1800
```

## Pakai: Dari Cookie File

Daripada edit config.json, bisa langsung pakai file cookie:

```bash
# JSON format (dari Cookie-Editor export)
python3 nftoken_generator.py --cookie-file cookies.json

# Raw cookie string
python3 nftoken_generator.py --cookie-file cookies.txt

# Dengan daemon mode
python3 nftoken_generator.py --cookie-file cookies.json --daemon --output link.txt
```

## Pakai: CLI Langsung

```bash
python3 nftoken_generator.py --netflix-id "PASTE_VALUE" --output link.txt
```

## Simpan Link ke File

Set `output_file` di config:

```json
{
  "output_file": "link.txt"
}
```

Atau pakai flag `--output`:

```bash
python3 nftoken_generator.py --config config.json --output link.txt
```

Setiap kali link di-generate/refresh, file `link.txt` akan di-update dengan link terbaru.

## Notifikasi Telegram

1. Bikin bot via `@BotFather` di Telegram, dapat bot_token
2. Dapatkan chat_id kamu (kirim pesan ke bot, lalu cek `https://api.telegram.org/bot<TOKEN>/getUpdates`)
3. Edit config.json:

```json
{
  "telegram": {
    "enabled": true,
    "bot_token": "123456:ABC-DEF...",
    "chat_id": "123456789"
  }
}
```

4. Jalankan daemon:

```bash
python3 nftoken_generator.py --config config.json --daemon
```

Setiap kali link di-refresh, bot akan kirim pesan:

```
Netflix NFToken Refreshed

Link: https://netflix.com/?nftoken=...
Expires: 2026-08-18 12:55:53
TTL: 64 minutes
```

## Jalankan 24 Jam dengan systemd

Buat service:

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/nftoken.service <<'EOF'
[Unit]
Description=Netflix NFToken Generator (auto-refresh)
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/netflix-nftoken-generator
ExecStart=%h/netflix-nftoken-generator/.venv/bin/python3 nftoken_generator.py --config config.json --daemon
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF
```

Aktifkan:

```bash
systemctl --user daemon-reload
systemctl --user enable --now nftoken.service
loginctl enable-linger "$USER"
```

Cek status:

```bash
systemctl --user status nftoken.service --no-pager
journalctl --user -u nftoken.service -f
```

## Endpoint API

```
GET https://ios.prod.ftl.netflix.com/iosui/user/15.48
```

Parameter penting:

| Parameter | Value |
|-----------|-------|
| `path` | `["account","token","default"]` |
| `pathFormat` | `graph` |
| `responseFormat` | `json` |
| `appVersion` | `15.48.1` |
| `device_type` | `NFAPPL-02-` |

Auth:

```
Cookie: NetflixId=<value>; SecureNetflixId=<value>; nfvdid=<value>
```

Response:

```json
{
  "value": {
    "account": {
      "token": {
        "default": {
          "token": "<TOKEN_VALUE>",
          "expires": 1787028953214,
          "$type": "leaf"
        }
      }
    }
  }
}
```

## FAQ

### Berapa lama link bertahan?
**~65 menit (1 jam)** sejak di-generate. Setelah itu link expired dan tidak bisa dipakai.

### Bisa dipakai berapa kali?
Kemungkinan **one-time use**. Setelah satu orang pakai link itu, link bisa jadi tidak bisa dipakai lagi. Generate ulang untuk link baru.

### Apakah generating link baru membatalkan link lama?
**Ya**, generating nftoken baru kemungkinan membatalkan link sebelumnya.

### Apakah cookie NetflixId bertahan lama?
Cookie `NetflixId` bisa bertahan **berbulan-bulan** selama tidak logout atau ganti password. Selama cookie valid, bisa terus generate nftoken baru.

### Apakah ini legal?
Ini menggunakan API resmi Netflix untuk device activation. Namun sharing akun ke orang lain **melanggar Terms of Service Netflix**. Gunakan untuk personal/research saja.

### Apakah Netflix bisa deteksi abuse?
Ya. Netflix punya sistem deteksi anomali. Generate nftoken terlalu sering atau share ke banyak orang bisa memicu flag/ban akun.

## Security

- Jangan commit `config.json` (sudah di `.gitignore`)
- Jangan share cookie `NetflixId` ke publik
- Jangan share link nftoken di tempat publik
- Ganti password Netflix kalau cookie bocor
- Cookie `NetflixId` = akses penuh ke akun Netflix

## Credits

Reverse-engineered dari Netflix iOS app API (`ios.prod.ftl.netflix.com`).
Inspired by `harshitkamboj/Netflix-NFToken-Generator`.
