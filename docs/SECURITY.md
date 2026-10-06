# 🛡️ Security Policy & AI Skill Hardening (NVIDIA SkillSpector)

Dokumen ini menjelaskan model keamanan dan implementasi pengujian keamanan statis untuk agen AI di `ytagent` menggunakan [NVIDIA SkillSpector](https://github.com/NVIDIA/SkillSpector).

---

## 1. Latar Belakang & Ancaman (Threat Model)

Sistem `ytagent` menggunakan instruksi AI terstruktur dan skills (seperti skill pembersih antislop, tools eksekusi Python, integrasi MCP, dan subagent workflow). 

Skill AI dapat menjadi celah keamanan jika disusupi atau ditulis dengan pola yang berbahaya:
- **Prompt Injection (`P1`, `P2`)**: Instruksi tersembunyi (misalnya dalam komentar HTML markdown) yang mencoba membajak perilaku LLM.
- **Data Exfiltration (`DE1`–`DE5`)**: Upaya pengiriman data sensitif, API key, atau environment variable ke endpoint eksternal yang tidak sah.
- **Privilege Escalation (`PE1`–`PE4`)**: Skill yang mencoba mengakses instruksi atau file milik skill lain tanpa otorisasi.
- **Excessive Agency (`EA1`–`EA3`)**: Eksekusi aksi destruktif atau mutasi data tanpa persetujuan / konfirmasi manusia.
- **Tool Misuse & AST Injection (`TM1`–`TM3`, `AST1`–`AST4`)**: Penggunaan `eval()`, `exec()`, subprocess shell berbahaya, atau manipulasi dynamic import pada script pendukung.

NVIDIA SkillSpector memindai instruksi Markdown (`SKILL.md`), script executable Python, skema tool, dan konfigurasi MCP secara statis untuk mendeteksi 17 kategori kerentanan tersebut.

---

## 2. Struktur Integrasi di YTAgent

Integrasi SkillSpector dalam repository ini terdiri dari komponen berikut:

| Komponen | Path | Fungsi |
|---|---|---|
| **CLI Runner** | [`scripts/security_scan_skills.py`](../scripts/security_scan_skills.py) | Script otomatisasi untuk memindai seluruh sub-skill di `.agents/skills` atau skill tunggal. |
| **Baseline File** | [`.skillspector-baseline.yaml`](../.skillspector-baseline.yaml) | Fingerprint cryptographic (SHA-256) untuk menandai temuan yang sudah diaudit dan disetujui (false-positive). |
| **CI/CD Workflow** | [`.github/workflows/skillspector.yml`](../.github/workflows/skillspector.yml) | GitHub Actions yang memvalidasi setiap push/PR pada folder `.agents/**` atau `scripts/**`. |
| **Audit Log** | [`docs/SECURITY_SKILLSPECTOR_REPORT.md`](SECURITY_SKILLSPECTOR_REPORT.md) | Catatan audit awal hasil pemindaian lengkap. |

---

## 3. Cara Menjalankan Scan Lokal

### A. Menjalankan via Script Runner (Rekomendasi)

Jalankan pemindaian seluruh skills yang terpasang di `.agents/skills`:

```bash
python scripts/security_scan_skills.py --fail-on-findings
```

Opsi yang didukung:
- `--target <path>`: Target direktori atau skill tertentu (default: `.agents/skills`).
- `--baseline <path>`: File baseline (default: `.skillspector-baseline.yaml`).
- `--format [terminal|json|markdown|sarif]`: Format output laporan.
- `--output <file>`: Menyimpan output laporan ke file tertentu.
- `--fail-on-findings`: Keluar dengan kode error `non-zero` jika ada kerentanan baru yang belum masuk baseline.

### B. Menjalankan Langsung via CLI SkillSpector

```bash
# Scan satu skill spesifik dengan baseline
./.venv/bin/skillspector scan .agents/skills/antislop --baseline .skillspector-baseline.yaml --no-llm --fail-on-findings

# Menampilkan temuan yang disupresi oleh baseline
./.venv/bin/skillspector scan .agents/skills/antislop --baseline .skillspector-baseline.yaml --no-llm --show-suppressed
```

---

## 4. Kebijakan Baseline & False-Positive

Pada pemindaian awal terhadap skill `antislop`, SkillSpector menandai 21 pola statis:
1. **P2 (Hidden Instructions)**: Komentar HTML (`<!-- antislop:start -->`) yang digunakan untuk penanda blok kode oleh package antislop.
2. **AS3 (Skill Enumeration)**: Referensi path file antar-skill dalam dokumentasi instalasi.
3. **AR2 (Anti-Refusal)**: Arahan untuk menghindari kalimat penolakan klise AI (moralizing disclaimers).
4. **EA2 (Autonomous Decision)**: Arahan otomasi tanpa prompt berulang.

Pola-pola ini telah diverifikasi bukan malicious code, melainkan bagian dari operasional tool antislop. Pola tersebut didaftarkan ke [`.skillspector-baseline.yaml`](../.skillspector-baseline.yaml) sehingga:
- Skill yang sudah diaudit tetap berstatus **0/100 (LOW - PASSED)**.
- Setiap perubahan baru atau penambahan skill jahat di masa mendatang akan langsung terdeteksi dan memblokir pipeline CI/CD.

### Memperbarui Baseline saat Menambah Skill Baru

Jika Anda menambahkan skill internal baru atau memodifikasi instruksi yang memicu peringatan yang valid dan aman:

```bash
# 1. Audit manual terlebih dahulu isi SKILL.md dan file executable
./.venv/bin/skillspector scan .agents/skills/<nama-skill> --no-llm

# 2. Jika temuan telah ditinjau dan aman, perbarui baseline:
./.venv/bin/skillspector baseline .agents/skills/<nama-skill> -o /tmp/new_baseline.yaml --no-llm

# 3. Gabungkan fingerprint ke .skillspector-baseline.yaml dan commit
```

---

## 5. Integrasi CI/CD (GitHub Actions)

Workflow [`.github/workflows/skillspector.yml`](../.github/workflows/skillspector.yml) berjalan otomatis pada event `push` dan `pull_request` untuk branch `main`.

Langkah pipeline:
1. Setup Python 3.12.
2. Install `skillspector` dari repository resmi NVIDIA (`git+https://github.com/NVIDIA/skillspector.git`).
3. Menjalankan `python scripts/security_scan_skills.py --fail-on-findings`.
4. Jika ada temuan berisiko yang belum terdaftar di `.skillspector-baseline.yaml`, proses build PR akan ditolak (failed status).
