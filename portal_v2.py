#!/usr/bin/env python3
import base64
import cgi
import csv
import hashlib
import hmac
import html
import io
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import time
import urllib.request
import uuid
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


APP_DIR = "/opt/firefox-portal"
DB = APP_DIR + "/portal.db"
SECRET_FILE = APP_DIR + "/secret.key"
ENV_FILE = APP_DIR + "/portal.env"
SAP_SUMMARY_FILE = "/opt/firefox-sap-sync/latest_summary.json"
UPLOAD_DIR = APP_DIR + "/uploads"
PORT = 8088
LOCK_LIMIT = 5
LOCK_SECONDS = 15 * 60


def U(s):
    return s.encode("ascii").decode("unicode_escape")


def load_env_file():
    if not os.path.exists(ENV_FILE):
        return
    for line in Path(ENV_FILE).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


load_env_file()

T = {
    "brand": U(r"\u706b\u72d0\u72f8 AI \u4f01\u4e1a\u7ecf\u8425\u7cfb\u7edf"),
    "subtitle": U(r"FireFox AI Operating System\uff1aAI + ERP + CRM + OA + \u77e5\u8bc6\u5e93 + BI + \u667a\u80fd\u4f53\u5e73\u53f0\u7684\u7edf\u4e00\u5165\u53e3\u3002"),
    "login": U(r"\u767b\u5f55"),
    "register": U(r"\u65b0\u5458\u5de5\u6ce8\u518c"),
    "logout": U(r"\u9000\u51fa"),
    "email": U(r"\u90ae\u7bb1"),
    "password": U(r"\u5bc6\u7801"),
    "new_password": U(r"\u65b0\u5bc6\u7801"),
    "name": U(r"\u59d3\u540d"),
    "phone": U(r"\u624b\u673a"),
    "store": U(r"\u95e8\u5e97/\u90e8\u95e8"),
    "role": U(r"\u89d2\u8272"),
    "status": U(r"\u72b6\u6001"),
    "action": U(r"\u64cd\u4f5c"),
    "pending": U(r"\u4f60\u7684\u8d26\u53f7\u5df2\u63d0\u4ea4\uff0c\u9700\u7ba1\u7406\u5458\u5ba1\u6838\u901a\u8fc7\u540e\u624d\u80fd\u767b\u5f55\u3002"),
    "bad": U(r"\u8d26\u53f7\u6216\u5bc6\u7801\u4e0d\u6b63\u786e\uff0c\u6216\u8d26\u53f7\u8fd8\u6ca1\u6709\u5ba1\u6838\u901a\u8fc7\u3002"),
    "locked": U(r"\u767b\u5f55\u5931\u8d25\u6b21\u6570\u8fc7\u591a\uff0c\u8d26\u53f7\u5df2\u9501\u5b9a 15 \u5206\u949f\u3002"),
    "duplicate": U(r"\u8fd9\u4e2a\u90ae\u7bb1\u5df2\u7ecf\u6ce8\u518c\u8fc7\u3002"),
    "admin": U(r"\u7cfb\u7edf\u7ba1\u7406"),
    "users": U(r"\u7528\u6237\u7ba1\u7406"),
    "change_password": U(r"\u4fee\u6539\u5bc6\u7801"),
    "save": U(r"\u4fdd\u5b58"),
    "approve": U(r"\u5ba1\u6838\u901a\u8fc7"),
    "disable": U(r"\u7981\u7528"),
    "enable": U(r"\u542f\u7528"),
    "reset": U(r"\u91cd\u7f6e\u5bc6\u7801"),
    "no_permission": U(r"\u6ca1\u6709\u6743\u9650"),
    "password_changed": U(r"\u5bc6\u7801\u5df2\u4fee\u6539\u3002"),
}

ROLES = {
    "boss": U(r"\u8001\u677f"),
    "store_manager": U(r"\u5e97\u957f"),
    "employee": U(r"\u5458\u5de5"),
    "purchasing": U(r"\u91c7\u8d2d"),
    "finance": U(r"\u8d22\u52a1"),
    "admin": U(r"\u7ba1\u7406\u5458"),
}

MODULES = {
    "/overview": (U(r"\u7ecf\u8425\u603b\u89c8"), U(r"\u67e5\u770b\u9500\u552e\u3001\u6bdb\u5229\u3001\u5e93\u5b58\u3001\u98ce\u9669\u548c AI \u7ecf\u8425\u5efa\u8bae\u3002"), ("boss", "admin", "finance", "purchasing")),
    "/stores": (U(r"\u95e8\u5e97\u4e2d\u5fc3"), U(r"\u95e8\u5e97\u6863\u6848\u3001\u7ecf\u8425\u6570\u636e\u3001\u95e8\u5e97\u65f6\u95f4\u8f74\u548c AI \u5206\u6790\u3002"), ("boss", "admin", "store_manager", "finance")),
    "/employees": (U(r"\u5458\u5de5\u4e2d\u5fc3"), U(r"\u5458\u5de5\u6863\u6848\u3001\u9500\u552e\u8868\u73b0\u3001\u57f9\u8bad\u8bb0\u5f55\u3001\u6210\u957f\u65f6\u95f4\u8f74\u3002"), ("boss", "admin", "store_manager", "finance")),
    "/brands": (U(r"\u54c1\u724c\u4e2d\u5fc3"), U(r"\u54c1\u724c\u6863\u6848\u3001\u5408\u4f5c\u6587\u4ef6\u3001\u54c1\u724c\u9500\u552e\u548c AI \u7ecf\u8425\u5efa\u8bae\u3002"), ("boss", "admin", "purchasing", "store_manager")),
    "/products": (U(r"\u4ea7\u54c1\u4e2d\u5fc3"), U(r"\u4ea7\u54c1\u6863\u6848\u3001\u56fe\u7247\u3001\u5e93\u5b58\u3001\u9500\u552e\u6570\u636e\u3001AI \u9500\u552e\u8bdd\u672f\u3002"), ("boss", "admin", "purchasing", "store_manager", "employee")),
    "/suppliers": (U(r"\u4f9b\u5e94\u5546\u4e2d\u5fc3"), U(r"\u4f9b\u5e94\u5546\u6863\u6848\u3001\u5408\u540c\u3001\u91c7\u8d2d\u8bb0\u5f55\u3001\u4ed8\u6b3e\u8bb0\u5f55\u548c AI \u8bc4\u4f30\u3002"), ("boss", "admin", "purchasing", "finance")),
    "/members": (U(r"\u987e\u5ba2/\u4f1a\u5458\u4e2d\u5fc3"), U(r"\u4f1a\u5458\u6863\u6848\u3001\u8d2d\u4e70\u5386\u53f2\u3001\u504f\u597d\u6807\u7b7e\u3001AI \u7ef4\u62a4\u5efa\u8bae\u3002"), ("boss", "admin", "store_manager", "employee")),
    "/finance": (U(r"\u8d22\u52a1\u4e2d\u5fc3"), U(r"\u5bf9\u516c\u5408\u89c4\u8d26\u52a1\u3001\u5bf9\u79c1\u73b0\u91d1\u8d26\u3001\u4ed8\u6b3e\u8bc4\u4f30\u548c\u8d44\u91d1\u8ba1\u5212\u3002"), ("boss", "admin", "finance")),
    "/content": (U(r"\u5185\u5bb9\u53d1\u5e03\u4e2d\u5fc3"), U(r"\u65b0\u5a92\u4f53\u63a8\u5e7f\u3001\u95e8\u5e97\u5185\u5bb9\u3001\u4ea7\u54c1\u7d20\u6750\u548c\u53d1\u5e03\u8ba1\u5212\u3002"), ("boss", "admin", "store_manager", "employee")),
    "/tasks": (U(r"\u4efb\u52a1\u4e2d\u5fc3"), U(r"\u4eca\u65e5\u5f85\u529e\u3001\u95e8\u5e97\u4efb\u52a1\u3001\u5458\u5de5\u8ddf\u8fdb\u548c\u81ea\u52a8\u5316\u4efb\u52a1\u3002"), ("boss", "admin", "store_manager", "employee", "purchasing", "finance")),
}

ARCHIVE_FIELDS = {
    "stores": [U(r"\u95e8\u5e97\u540d\u79f0"), U(r"\u5730\u5740"), U(r"\u9762\u79ef"), U(r"\u5f00\u4e1a\u65f6\u95f4"), U(r"\u79df\u8d41\u5408\u540c"), U(r"\u8425\u4e1a\u989d"), U(r"\u79df\u91d1"), U(r"\u5458\u5de5"), U(r"\u54c1\u724c"), U(r"AI \u5efa\u8bae")],
    "employees": [U(r"\u59d3\u540d"), U(r"\u7167\u7247"), U(r"\u5e74\u9f84"), U(r"\u7535\u8bdd"), U(r"\u5c97\u4f4d"), U(r"\u90e8\u95e8"), U(r"\u5165\u804c\u65e5\u671f"), U(r"\u5de5\u8d44"), U(r"\u7ee9\u6548"), U(r"AI \u8bc4\u4ef7")],
    "brands": [U(r"\u54c1\u724c\u540d\u79f0"), "Logo", U(r"\u54c1\u724c\u4ecb\u7ecd"), U(r"\u8d1f\u8d23\u4eba"), U(r"\u5408\u540c"), U(r"\u9500\u552e"), U(r"\u6bdb\u5229"), U(r"\u5e93\u5b58"), U(r"\u672a\u6765\u89c4\u5212"), U(r"AI \u5206\u6790")],
    "products": [U(r"\u4ea7\u54c1\u540d\u79f0"), "SKU", U(r"\u6761\u7801"), U(r"\u54c1\u724c"), U(r"\u5206\u7c7b"), U(r"\u56fe\u7247"), U(r"\u8bf4\u660e\u4e66"), U(r"\u9500\u552e"), U(r"\u5e93\u5b58"), U(r"AI \u63a8\u8350")],
    "suppliers": [U(r"\u4f9b\u5e94\u5546\u540d\u79f0"), U(r"\u8054\u7cfb\u4eba"), U(r"\u7535\u8bdd"), U(r"\u5fae\u4fe1"), U(r"\u5408\u540c"), U(r"\u4ed8\u6b3e\u65b9\u5f0f"), U(r"\u5386\u53f2\u91c7\u8d2d"), U(r"\u9644\u4ef6"), U(r"AI \u8bc4\u4ef7")],
    "members": [U(r"\u59d3\u540d"), U(r"\u7535\u8bdd"), U(r"\u5fae\u4fe1"), U(r"\u751f\u65e5"), U(r"\u6d88\u8d39\u8bb0\u5f55"), U(r"\u79ef\u5206"), U(r"\u4f1a\u5458\u7b49\u7ea7"), U(r"\u5174\u8da3"), U(r"\u5907\u6ce8"), U(r"AI \u63a8\u8350")],
}
OLD_ROLE_MAP = {
    "leader": "boss",
    "manager": "store_manager",
}
STATUS = {
    "pending": U(r"\u5f85\u5ba1\u6838"),
    "approved": U(r"\u6b63\u5e38"),
    "disabled": U(r"\u5df2\u7981\u7528"),
}


def esc(value):
    return html.escape(str(value or ""))


def money(value):
    try:
        return f"{float(value):,.0f}"
    except Exception:
        return "0"


def pct(value):
    try:
        return f"{float(value):.1f}%"
    except Exception:
        return "0.0%"


def ts():
    return int(time.time())


def dt(value):
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(value or 0)))
    except Exception:
        return ""


def safe_json(value, fallback=None):
    try:
        return json.loads(value or "")
    except Exception:
        return fallback if fallback is not None else {}


def csv_values(value):
    return [v.strip() for v in str(value or "").split(",") if v.strip()]


def chunk_text(text, size=1600):
    clean = re.sub(r"\s+", " ", text or "").strip()
    if not clean:
        return []
    return [clean[i : i + size] for i in range(0, len(clean), size)]


def row_dict(row):
    return dict(row) if row else None


def module_key(path_or_key):
    return str(path_or_key or "").strip().lstrip("/")


def module_title(key):
    data = MODULES.get("/" + module_key(key))
    return data[0] if data else module_key(key)


def classify_text(text, fallback="01_公司制度"):
    text = (text or "").lower()
    rules = [
        ("02_产品资料", ["产品", "货号", "尺码", "面料", "价格", "gtx", "gore", "kailas"]),
        ("03_品牌资料", ["品牌", "logo", "合同", "mammut", "osprey", "salomon"]),
        ("04_销售话术", ["话术", "顾客", "推荐", "成交", "异议"]),
        ("06_门店经营", ["门店", "店长", "销售", "日报", "任务"]),
        ("07_库存采购", ["库存", "采购", "供应商", "订货", "补货"]),
        ("09_财务经营", ["财务", "付款", "现金", "社保", "工资", "公积金"]),
        ("14_AI经营日报", ["ai", "晨报", "经营分析", "建议"]),
    ]
    for category, words in rules:
        if any(w.lower() in text for w in words):
            return category
    return fallback


def summarize_text(text, limit=220):
    clean = re.sub(r"\s+", " ", text or "").strip()
    if not clean:
        return U(r"\u6682\u65e0\u53ef\u63d0\u53d6\u6587\u672c\uff0c\u5df2\u5148\u4fdd\u5b58\u539f\u6587\u4ef6\u3002")
    return clean[:limit] + ("..." if len(clean) > limit else "")


def extract_tags(text):
    category = classify_text(text)
    tags = [category.split("_", 1)[-1]]
    for word in [U(r"\u9500\u552e"), U(r"\u5e93\u5b58"), U(r"\u91c7\u8d2d"), U(r"\u4f1a\u5458"), U(r"\u95e8\u5e97"), "SAP B1", "AI"]:
        if word.lower() in (text or "").lower():
            tags.append(word)
    return ",".join(dict.fromkeys(tags))


def extract_file_text(path, filename):
    ext = Path(filename).suffix.lower()
    try:
        if ext in (".txt", ".md", ".csv", ".json"):
            return Path(path).read_text(encoding="utf-8", errors="ignore")[:200000]
        if ext == ".pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(path)
                return "\n".join((p.extract_text() or "") for p in reader.pages)[:200000]
            except Exception:
                return ""
        if ext == ".docx":
            try:
                import docx
                doc = docx.Document(path)
                return "\n".join(p.text for p in doc.paragraphs)[:200000]
            except Exception:
                return ""
        if ext in (".xlsx", ".xls"):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                lines = []
                for ws in wb.worksheets[:3]:
                    for row in ws.iter_rows(max_row=200, values_only=True):
                        lines.append("\t".join("" if v is None else str(v) for v in row))
                return "\n".join(lines)[:200000]
            except Exception:
                return ""
    except Exception:
        return ""
    return ""


def fetch_url_text(url):
    if not url.lower().startswith(("http://", "https://")):
        return ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 FoxBrain"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read(500000)
        text = raw.decode("utf-8", errors="ignore")
        text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", html.unescape(text)).strip()[:200000]
    except Exception:
        return ""


def load_summary():
    fallback = {
        "data_date": U(r"\u6d4b\u8bd5\u6570\u636e"),
        "yesterday_sales": 80539.66,
        "yesterday_gross_profit": 23848.03,
        "yesterday_gross_margin": 29.6,
        "month_sales": 118059.57,
        "month_gross_profit": 35385.52,
        "month_target": 900000,
        "completion_rate": 13.1,
        "inventory_amount": 0,
        "risk_count": 0,
        "top_stores": [
            {"store": "8001", "sales": 43866.40, "gross_profit": 12642.40},
            {"store": "8002", "sales": 36844.00, "gross_profit": 9200.43},
            {"store": "8003", "sales": 27678.17, "gross_profit": 9195.06},
        ],
        "ai_suggestions": [
            U(r"\u4eca\u65e5\u5148\u68c0\u67e5 8001\u30018002\u30018003 \u4e09\u4e2a\u4e3b\u529b\u4ed3\u5e93\u7684\u9500\u552e\u548c\u6bdb\u5229\u5dee\u5f02\u3002"),
            U(r"\u628a 7 \u6708\u76ee\u6807\u62c6\u5230\u6bcf\u5e97\u6bcf\u65e5\uff0c\u6bcf\u5929\u8ffd\u8e2a\u5dee\u989d\u3002"),
            U(r"\u5e93\u5b58\u5206\u6790\u4e0b\u4e00\u6b65\u8981\u52a0\u5165\u6ede\u9500\u5929\u6570\u548c\u5c3a\u7801\u7ed3\u6784\u3002"),
        ],
        "todos": [
            U(r"\u786e\u8ba4\u4ed3\u5e93\u4ee3\u7801 8001\u30018002\u30018003\u30018014 \u5bf9\u5e94\u7684\u95e8\u5e97\u540d\u79f0\u3002"),
            U(r"\u68c0\u67e5 SAP B1 \u51cc\u6668 2:00 \u81ea\u52a8\u540c\u6b65\u7ed3\u679c\u3002"),
            U(r"\u4e3a AI \u603b\u7ecf\u7406\u63a5\u5165\u6570\u636e\u67e5\u8be2\u5de5\u5177\u3002"),
        ],
    }
    try:
        if os.path.exists(SAP_SUMMARY_FILE):
            with open(SAP_SUMMARY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {**fallback, **data}
    except Exception:
        pass
    return fallback


def get_secret():
    os.makedirs(APP_DIR, exist_ok=True)
    if not os.path.exists(SECRET_FILE):
        Path(SECRET_FILE).write_text(secrets.token_urlsafe(48), encoding="utf-8")
        os.chmod(SECRET_FILE, 0o600)
    return Path(SECRET_FILE).read_text(encoding="utf-8").strip().encode()


SECRET = get_secret()


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def hp(password, salt=None, iterations=200000):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
    return salt + "$" + base64.b64encode(digest).decode()


def cp(password, stored):
    try:
        salt = stored.split("$", 1)[0]
        return hmac.compare_digest(hp(password, salt, 200000), stored) or hmac.compare_digest(hp(password, salt, 160000), stored)
    except Exception:
        return False


def needs_password_upgrade(password, stored):
    try:
        salt = stored.split("$", 1)[0]
        return hmac.compare_digest(hp(password, salt, 160000), stored) and not hmac.compare_digest(hp(password, salt, 200000), stored)
    except Exception:
        return False


def sign(value):
    digest = hmac.new(SECRET, value.encode(), hashlib.sha256).hexdigest()
    return value + "|" + digest


def unsign(value):
    if not value or "|" not in value:
        return None
    raw, digest = value.rsplit("|", 1)
    good = hmac.new(SECRET, raw.encode(), hashlib.sha256).hexdigest()
    return raw if hmac.compare_digest(digest, good) else None


def ensure_column(conn, table, column, ddl):
    cols = {r["name"] for r in conn.execute(f"pragma table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"alter table {table} add column {ddl}")


def init():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with db() as conn:
        conn.execute(
            """
create table if not exists users(
 id integer primary key autoincrement,
 email text unique not null,
 name text not null,
 phone text,
 store text,
 role text not null default 'employee',
 status text not null default 'pending',
 password_hash text not null,
 created_at integer not null,
 last_login integer
)
"""
        )
        ensure_column(conn, "users", "failed_attempts", "failed_attempts integer not null default 0")
        ensure_column(conn, "users", "locked_until", "locked_until integer not null default 0")
        ensure_column(conn, "users", "updated_at", "updated_at integer")
        ensure_column(conn, "users", "reset_required", "reset_required integer not null default 0")
        for old, new in OLD_ROLE_MAP.items():
            conn.execute("update users set role=? where role=?", (new, old))
        conn.execute(
            """
create table if not exists records(
 id integer primary key autoincrement,
 module text not null,
 title text not null,
 status text not null default 'active',
 tags text,
 summary text,
 data_json text,
 created_by integer,
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_records_module on records(module)")
        conn.execute(
            """
create table if not exists knowledge_items(
 id integer primary key autoincrement,
 title text not null,
 category text,
 tags text,
 body text,
 ai_summary text,
 source_type text,
 source_ref text,
 approved integer not null default 1,
 created_by integer,
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_knowledge_category on knowledge_items(category)")
        ensure_column(conn, "knowledge_items", "knowledge_id", "knowledge_id text")
        ensure_column(conn, "knowledge_items", "source_id", "source_id text")
        ensure_column(conn, "knowledge_items", "source_file_id", "source_file_id integer")
        ensure_column(conn, "knowledge_items", "object_type", "object_type text")
        ensure_column(conn, "knowledge_items", "object_id", "object_id integer")
        ensure_column(conn, "knowledge_items", "summary", "summary text")
        ensure_column(conn, "knowledge_items", "keywords", "keywords text")
        ensure_column(conn, "knowledge_items", "status", "status text not null default 'draft'")
        ensure_column(conn, "knowledge_items", "visibility", "visibility text not null default 'public_internal'")
        ensure_column(conn, "knowledge_items", "human_summary", "human_summary text")
        ensure_column(conn, "knowledge_items", "auto_tags", "auto_tags text")
        ensure_column(conn, "knowledge_items", "manual_tags", "manual_tags text")
        ensure_column(conn, "knowledge_items", "embedding_status", "embedding_status text not null default 'pending'")
        conn.execute("create index if not exists idx_knowledge_status on knowledge_items(status)")
        conn.execute("create index if not exists idx_knowledge_object on knowledge_items(object_type, object_id)")
        conn.execute("create index if not exists idx_knowledge_visibility on knowledge_items(visibility)")
        conn.execute(
            """
create table if not exists uploaded_files(
 id integer primary key autoincrement,
 original_name text not null,
 saved_name text not null,
 path text not null,
 mime text,
 size integer,
 category text,
 description text,
 public integer not null default 1,
 need_summary integer not null default 1,
 need_sales_script integer not null default 0,
 extracted_text text,
 knowledge_id integer,
 created_by integer,
 created_at integer not null
)
"""
        )
        conn.execute(
            """
create table if not exists knowledge_chunks(
 id integer primary key autoincrement,
 chunk_id text unique,
 knowledge_id integer not null,
 document_id integer,
 chunk_index integer not null,
 chunk_text text,
 token_count integer not null default 0,
 page_number integer,
 section_title text,
 embedding_status text not null default 'pending',
 created_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_chunks_knowledge on knowledge_chunks(knowledge_id)")
        conn.execute(
            """
create table if not exists knowledge_query_history(
 id integer primary key autoincrement,
 user_id integer,
 question text not null,
 scope text,
 related_object_type text,
 related_object_id integer,
 answer_json text,
 created_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_query_history_user on knowledge_query_history(user_id, created_at)")
        conn.execute(
            """
create table if not exists activity_log(
 id integer primary key autoincrement,
 user_id integer,
 action text not null,
 target_type text,
 target_id integer,
 detail text,
 created_at integer not null
)
"""
        )
        conn.execute(
            """
create table if not exists timeline_events(
 id integer primary key autoincrement,
 target_type text not null,
 target_id integer not null,
 title text not null,
 body text,
 created_by integer,
 created_at integer not null
)
"""
        )
        conn.execute(
            """
create table if not exists relations(
 id integer primary key autoincrement,
 from_type text not null,
 from_id integer not null,
 to_type text not null,
 to_id integer not null,
 relation_type text,
 created_by integer,
 created_at integer not null
)
"""
        )
        conn.execute(
            """
create table if not exists tasks(
 id integer primary key autoincrement,
 task_id text unique,
 title text not null,
 description text,
 owner text,
 related_object_type text,
 related_object_id integer,
 priority text not null default 'normal',
 status text not null default 'todo',
 due_date text,
 source_type text,
 source_id text,
 created_by integer,
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_tasks_status on tasks(status)")
        conn.execute("create index if not exists idx_tasks_owner on tasks(owner)")
        conn.execute("create index if not exists idx_tasks_related on tasks(related_object_type, related_object_id)")
        conn.execute(
            """
create table if not exists workflow_templates(
 id integer primary key autoincrement,
 template_id text unique,
 name text not null,
 description text,
 trigger_type text,
 steps_json text,
 owner text,
 status text not null default 'draft',
 related_object_type text,
 ai_recommendation text,
 created_by integer,
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_workflow_templates_status on workflow_templates(status)")
        conn.execute(
            """
create table if not exists automations(
 id integer primary key autoincrement,
 automation_id text unique,
 name text not null,
 description text,
 trigger_type text not null default 'manual',
 schedule_rule text,
 action_type text,
 template_id integer,
 status text not null default 'draft',
 owner text,
 last_run_at integer,
 next_run_at integer,
 related_object_type text,
 related_object_id integer,
 ai_recommendation text,
 created_by integer,
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_automations_status on automations(status)")
        conn.execute("create index if not exists idx_automations_trigger on automations(trigger_type)")
        conn.execute(
            """
create table if not exists automation_runs(
 id integer primary key autoincrement,
 run_id text unique,
 automation_id integer,
 status text not null default 'pending',
 started_at integer,
 finished_at integer,
 message text,
 result_json text,
 created_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_automation_runs_status on automation_runs(status)")
        conn.execute(
            """
create table if not exists notifications(
 id integer primary key autoincrement,
 notification_id text unique,
 channel text not null default 'in_app',
 title text not null,
 body text,
 recipient_user_id integer,
 status text not null default 'pending',
 related_object_type text,
 related_object_id integer,
 created_by integer,
 created_at integer not null,
 read_at integer
)
"""
        )
        conn.execute("create index if not exists idx_notifications_status on notifications(status)")
        conn.execute(
            """
create table if not exists memories(
 id integer primary key autoincrement,
 memory_id text unique,
 title text not null,
 content text,
 memory_type text not null default 'company_principle',
 object_type text,
 object_id integer,
 source_type text,
 source_id text,
 importance text not null default 'normal',
 confidence text not null default 'medium',
 visibility text not null default 'manager_only',
 status text not null default 'pending_review',
 created_by integer,
 created_at integer not null,
 updated_at integer not null,
 expires_at integer
)
"""
        )
        conn.execute("create index if not exists idx_memories_type on memories(memory_type)")
        conn.execute("create index if not exists idx_memories_status on memories(status)")
        conn.execute("create index if not exists idx_memories_visibility on memories(visibility)")
        conn.execute(
            """
create table if not exists user_preferences(
 id integer primary key autoincrement,
 preference_id text unique,
 user_id integer not null,
 key text not null,
 value text,
 scope text not null default 'user',
 created_at integer not null,
 updated_at integer not null,
 unique(user_id,key,scope)
)
"""
        )
        conn.execute("create index if not exists idx_preferences_user on user_preferences(user_id)")
        conn.execute(
            """
create table if not exists decision_memories(
 id integer primary key autoincrement,
 decision_id text unique,
 decision_title text not null,
 decision_context text,
 options_considered text,
 selected_option text,
 reason text,
 risks text,
 owner text,
 decision_date text,
 related_objects text,
 follow_up_task text,
 memory_id integer,
 created_by integer,
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_decision_memories_date on decision_memories(decision_date)")
        ensure_column(conn, "relations", "relationship_id", "relationship_id text")
        ensure_column(conn, "relations", "source_entity_type", "source_entity_type text")
        ensure_column(conn, "relations", "source_entity_id", "source_entity_id integer")
        ensure_column(conn, "relations", "target_entity_type", "target_entity_type text")
        ensure_column(conn, "relations", "target_entity_id", "target_entity_id integer")
        ensure_column(conn, "relations", "strength", "strength text not null default 'normal'")
        ensure_column(conn, "relations", "confidence", "confidence text not null default 'medium'")
        ensure_column(conn, "relations", "direction", "direction text not null default 'directed'")
        ensure_column(conn, "relations", "description", "description text")
        ensure_column(conn, "relations", "evidence_type", "evidence_type text")
        ensure_column(conn, "relations", "evidence_id", "evidence_id integer")
        ensure_column(conn, "relations", "updated_at", "updated_at integer")
        conn.execute(
            """
create table if not exists graph_entities(
 id integer primary key autoincrement,
 entity_id text unique,
 entity_type text not null,
 entity_key text,
 entity_name text not null,
 description text,
 source_type text,
 source_id text,
 status text not null default 'active',
 created_by integer,
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_graph_entities_type on graph_entities(entity_type)")
        conn.execute("create index if not exists idx_graph_entities_name on graph_entities(entity_name)")
        conn.execute(
            """
create table if not exists graph_risks(
 id integer primary key autoincrement,
 risk_id text unique,
 title text not null,
 risk_type text not null,
 level text not null default 'unknown',
 object_type text,
 object_id integer,
 related_entities text,
 evidence text,
 recommendation text,
 status text not null default 'open',
 created_by integer,
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_graph_risks_type on graph_risks(risk_type)")
        conn.execute("create index if not exists idx_graph_risks_level on graph_risks(level)")
        admin_email = os.environ.get("PORTAL_ADMIN_EMAIL", "vafox@126.com").strip().lower()
        existing_admin = conn.execute("select id from users where role='admin' limit 1").fetchone()
        if not existing_admin:
            initial_password = os.environ.get("PORTAL_INITIAL_ADMIN_PASSWORD")
            if initial_password:
                conn.execute(
                    "insert into users(email,name,phone,store,role,status,password_hash,created_at) values(?,?,?,?,?,?,?,?)",
                    (admin_email, U(r"\u7ba1\u7406\u5458"), "", U(r"\u603b\u90e8"), "admin", "approved", hp(initial_password), int(time.time())),
                )
        conn.commit()


init()


def layout(title, body, user=None, msg="", wide=False):
    nav = ""
    if user:
        nav = (
            '<div class="topbar"><div><strong>{}</strong><small>{} · {}</small></div>'
            '<div><a href="/change-password">{}</a><a href="/logout">{}</a></div></div>'
        ).format(esc(user["name"]), esc(ROLES.get(user["role"], user["role"])), esc(user["store"]), T["change_password"], T["logout"])
    alert = f'<div class="alert">{esc(msg)}</div>' if msg else ""
    max_width = "1180px" if wide else "980px"
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Arial,sans-serif;background:#f6f3ed;color:#171717}}
main{{width:min({max_width},calc(100% - 24px));margin:0 auto;padding:18px 0 44px}}
h1{{font-size:30px;margin:8px 0 6px}}h2{{font-size:20px;margin:0 0 12px}}p,.lead{{line-height:1.65}}.lead{{font-size:16px;color:#555;margin:0 0 16px}}
.topbar{{display:flex;justify-content:space-between;gap:12px;align-items:center;background:#fff;border:1px solid #ddd7cc;border-radius:8px;padding:12px 14px;margin-bottom:18px}}
.topbar small{{display:block;color:#666;margin-top:3px}}.topbar a{{margin-left:12px;color:#1849a9;text-decoration:none;font-weight:700}}
.panel,.card{{background:#fff;border:1px solid #ddd7cc;border-radius:8px;box-shadow:0 8px 22px rgba(0,0,0,.05)}}.panel{{padding:18px;margin:14px 0}}.form{{max-width:520px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}.card{{padding:18px;min-height:154px;display:flex;flex-direction:column;justify-content:space-between}}
.metrics{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:12px 0}}.metric{{background:#fff;border:1px solid #ddd7cc;border-radius:8px;padding:14px;min-height:92px}}.metric strong{{display:block;font-size:22px;margin-top:7px}}.metric span{{font-size:13px;color:#666}}
.split{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}.list{{margin:0;padding-left:20px;line-height:1.85}}.pill{{display:inline-block;border:1px solid #ddd7cc;border-radius:999px;padding:7px 10px;margin:3px 5px 3px 0;background:#fff;font-weight:700;color:#333;text-decoration:none}}
.store-row{{display:grid;grid-template-columns:1.1fr 1fr 1fr;gap:8px;border-top:1px solid #eee;padding:10px 0}}.store-row:first-child{{border-top:0}}
.card h2{{margin-bottom:4px}}.card p{{color:#555;margin:0 0 18px}}.disabled{{opacity:.55}}
label{{display:block;font-weight:800;margin:12px 0 7px}}input,select,textarea{{width:100%;padding:14px;border:1px solid #cfc8bb;border-radius:8px;font-size:16px;background:#fff}}textarea{{min-height:120px;font-family:inherit}}
button,.btn{{display:inline-block;border:0;border-radius:8px;background:#1849a9;color:#fff;text-decoration:none;font-weight:800;padding:13px 16px;cursor:pointer;font-size:16px;text-align:center}}
.btn.full{{width:100%}}.red{{background:#ad1f15}}.green{{background:#18704c}}.dark{{background:#222}}.gray{{background:#777}}.orange{{background:#b45f06}}
.alert{{padding:12px;background:#fff7d6;border:1px solid #ecd27a;border-radius:8px;margin:12px 0}}table{{width:100%;border-collapse:collapse}}th,td{{border-bottom:1px solid #eee;padding:10px;text-align:left;vertical-align:top}}th{{white-space:nowrap}}.inline{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}.inline form{{display:inline}}.small{{font-size:13px;color:#666}}
@media(max-width:820px){{main{{width:calc(100% - 18px);padding-top:10px}}h1{{font-size:26px}}.grid,.metrics,.split{{grid-template-columns:1fr;gap:12px}}.store-row{{grid-template-columns:1fr}}.card{{min-height:132px}}.btn,button{{width:100%;padding:15px}}.topbar{{align-items:flex-start;flex-direction:column}}.topbar a{{margin:0 12px 0 0}}table,tbody,tr,td,th{{display:block}}thead{{display:none}}tr{{border:1px solid #eee;border-radius:8px;margin:10px 0;padding:8px;background:#fff}}td{{border:0;padding:7px}}.inline{{display:block}}.inline form{{display:block;margin-top:8px}}}}
</style></head><body><main>{nav}<section><h1>{esc(title)}</h1><p class="lead">{T['subtitle']}</p></section>{alert}{body}</main></body></html>"""


class App(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(fmt % args)

    def out(self, html_text, code=200):
        body = html_text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.end_headers()
        self.wfile.write(body)

    def json_out(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def file_out(self, name, content, content_type="text/csv; charset=utf-8"):
        body = content.encode("utf-8-sig")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def redir(self, path, cookie=None):
        self.send_response(302)
        self.send_header("Location", path)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def form(self):
        size = int(self.headers.get("Content-Length", "0") or 0)
        return {k: v[0] for k, v in parse_qs(self.rfile.read(size).decode("utf-8")).items()}

    def multipart(self):
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD": "POST"})
        return form

    def current_user(self):
        jar = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        token = jar.get("fp_session")
        uid = unsign(token.value) if token else None
        if not uid:
            return None
        with db() as conn:
            return conn.execute("select * from users where id=? and status='approved'", (uid,)).fetchone()

    def require_admin(self):
        user = self.current_user()
        if not user or user["role"] != "admin":
            self.redir("/login")
            return None
        return user

    def do_GET(self):
        path = urlparse(self.path).path
        user = self.current_user()
        if path in ("/health", "/api/health"):
            return self.api_health()
        if path == "/logout":
            return self.redir("/login", "fp_session=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax")
        if path == "/login":
            return self.login()
        if path == "/register":
            return self.register()
        if path == "/change-password":
            return self.change_password(user)
        if path == "/admin":
            return self.admin()
        if path == "/ai-ceo":
            return self.ai_ceo(user)
        if path == "/ai-store-manager":
            return self.ai_store_manager(user)
        if path in ("/ai-query", "/knowledge/query"):
            return self.ai_assistant(user)
        if path == "/agents":
            return self.agents(user)
        if path == "/sap-sync":
            return self.sap_sync(user)
        if path == "/documents":
            return self.document_center(user)
        if path == "/workflow":
            return self.workflow_center(user)
        if path == "/business-overview":
            return self.business_overview(user)
        if path == "/overview":
            return self.business_overview(user)
        if path == "/stores/operations":
            return self.store_operations(user)
        if path == "/brands/operations":
            return self.brand_operations(user)
        if path == "/inventory/risk":
            return self.inventory_risk(user)
        if path == "/brands/osprey-risk":
            return self.osprey_risk(user)
        if path == "/tasks":
            return self.task_center(user)
        if path == "/automation":
            return self.automation_center(user)
        if path == "/memory":
            return self.memory_center(user)
        if path == "/memory/view":
            return self.memory_view(user)
        if path == "/decisions":
            return self.decision_memory(user)
        if path == "/graph":
            return self.graph_center(user)
        if path == "/system/health":
            return self.system_health(user)
        if path == "/content-center":
            return self.module_page(user, "/content")
        if path == "/knowledge":
            return self.knowledge(user)
        if path == "/knowledge/dashboard":
            return self.knowledge(user)
        if path == "/inventory":
            return self.inventory(user)
        if path == "/records/new":
            return self.record_form(user)
        if path == "/records/view":
            return self.record_view(user)
        if path == "/records/edit":
            return self.record_form(user, edit=True)
        if path == "/records/export":
            return self.records_export(user)
        if path in MODULES:
            return self.module_page(user, path)
        if path == "/upload":
            return self.upload(user)
        if path == "/web-search":
            return self.web_search(user)
        if path == "/ai-assistant":
            return self.ai_assistant(user)
        if path == "/knowledge/view":
            return self.knowledge_view(user)
        if path == "/knowledge/new":
            return self.knowledge_form(user)
        if path == "/api/dashboard/summary":
            return self.json_out(load_summary())
        if path.startswith("/api/ai-ceo") or path.startswith("/api/business") or path.startswith("/api/stores") or path.startswith("/api/brands") or path.startswith("/api/inventory") or path.startswith("/api/tasks"):
            return self.api_task005_get(user, path)
        if path.startswith("/api/automation") or path.startswith("/api/workflows") or path.startswith("/api/notifications"):
            return self.api_automation_get(user, path)
        if path.startswith("/api/memory") or path.startswith("/api/preferences") or path.startswith("/api/decisions"):
            return self.api_memory_get(user, path)
        if path.startswith("/api/graph"):
            return self.api_graph_get(user, path)
        if path.startswith("/api/knowledge"):
            return self.api_knowledge_get(user, path)
        if path.startswith("/api/sap/"):
            return self.sap_api_placeholder(user, path)
        if path == "/":
            return self.dashboard(user) if user else self.login()
        if path == "/daily":
            return self.redir("/wiki/firefox-hq/daily")
        return self.redir("/")

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/tasks/save":
            return self.task_save()
        if path == "/tasks/complete":
            return self.task_complete()
        if path == "/automation/save":
            return self.automation_save()
        if path == "/workflows/save":
            return self.workflow_template_save()
        if path == "/memory/save":
            return self.memory_save()
        if path == "/memory/action":
            return self.memory_action()
        if path == "/preferences/save":
            return self.preference_save()
        if path == "/decisions/save":
            return self.decision_save()
        if path.startswith("/api/ai-ceo") or path.startswith("/api/business") or path.startswith("/api/stores") or path.startswith("/api/brands") or path.startswith("/api/inventory") or path.startswith("/api/tasks"):
            return self.api_task005_post(self.current_user(), path)
        if path.startswith("/api/automation") or path.startswith("/api/workflows") or path.startswith("/api/notifications"):
            return self.api_automation_post(self.current_user(), path)
        if path.startswith("/api/memory") or path.startswith("/api/preferences") or path.startswith("/api/decisions"):
            return self.api_memory_post(self.current_user(), path)
        if path.startswith("/api/graph"):
            return self.api_graph_post(self.current_user(), path)
        if path.startswith("/api/knowledge"):
            return self.api_knowledge_post(self.current_user(), path)
        if path.startswith("/api/"):
            return self.json_out({"ok": False, "message": U(r"\u63a5\u53e3\u5df2\u9884\u7559\uff0c\u4e0b\u4e00\u6b65\u63a5\u5165 AI \u548c\u77e5\u8bc6\u5e93\u6570\u636e\u3002")}, code=501)
        if path == "/login":
            return self.login_post()
        if path == "/register":
            return self.register_post()
        if path == "/change-password":
            return self.change_password_post()
        if path == "/records/save":
            return self.record_save()
        if path == "/records/delete":
            return self.record_delete()
        if path == "/records/import":
            return self.records_import()
        if path == "/upload":
            return self.upload_post()
        if path == "/web-search":
            return self.web_search_post()
        if path in ("/ai-assistant", "/ai-query"):
            return self.ai_assistant_post()
        if path == "/knowledge/save":
            return self.knowledge_save()
        if path == "/admin/update":
            return self.admin_update()
        if path == "/admin/reset-password":
            return self.admin_reset_password()
        return self.redir("/")

    def do_PUT(self):
        path = urlparse(self.path).path
        if path.startswith("/api/tasks"):
            return self.api_task005_post(self.current_user(), path)
        if path.startswith("/api/memory") or path.startswith("/api/preferences"):
            return self.api_memory_post(self.current_user(), path)
        if path.startswith("/api/graph"):
            return self.api_graph_post(self.current_user(), path)
        return self.json_out({"ok": False, "message": "unsupported"}, code=404)

    def seed_workflow_templates(self, conn, user_id=None):
        templates = [
            (U(r"\u91c7\u8d2d\u5ba1\u6279"), U(r"\u4ece\u9700\u6c42\u3001\u8be2\u4ef7\u3001\u5ba1\u6279\u5230\u4e0b\u5355\u7684\u91c7\u8d2d\u6d41\u7a0b\u3002"), "manual", [U(r"\u63d0\u4ea4\u9700\u6c42"), U(r"\u91c7\u8d2d\u590d\u6838"), U(r"\u8001\u677f\u5ba1\u6279"), U(r"\u751f\u6210\u4efb\u52a1")]),
            (U(r"\u4ed8\u6b3e\u5ba1\u6279"), U(r"\u4ed8\u6b3e\u7533\u8bf7\u3001\u8d22\u52a1\u590d\u6838\u3001\u8001\u677f\u5ba1\u6279\u548c\u8bb0\u5f55\u3002"), "manual", [U(r"\u63d0\u4ea4\u4ed8\u6b3e"), U(r"\u8d22\u52a1\u68c0\u67e5"), U(r"\u5ba1\u6279"), U(r"\u901a\u77e5")]),
            (U(r"\u62db\u8058"), U(r"\u9700\u6c42\u786e\u8ba4\u3001\u9762\u8bd5\u3001\u5f55\u7528\u548c\u5165\u804c\u3002"), "manual", [U(r"\u63d0\u4ea4\u5c97\u4f4d"), U(r"\u7b5b\u9009\u7b80\u5386"), U(r"\u9762\u8bd5"), U(r"\u5f55\u7528")]),
            (U(r"\u5458\u5de5\u5165\u804c"), U(r"\u5165\u804c\u8d44\u6599\u3001\u57f9\u8bad\u3001\u6743\u9650\u548c\u95e8\u5e97\u4ea4\u63a5\u3002"), "manual", [U(r"\u6536\u96c6\u8d44\u6599"), U(r"\u5efa\u7acb\u8d26\u53f7"), U(r"\u57f9\u8bad"), U(r"\u8bd5\u7528\u671f\u8ddf\u8fdb")]),
            (U(r"\u5458\u5de5\u79bb\u804c"), U(r"\u79bb\u804c\u7533\u8bf7\u3001\u4ea4\u63a5\u3001\u7ed3\u7b97\u548c\u6743\u9650\u56de\u6536\u3002"), "manual", [U(r"\u63d0\u4ea4\u7533\u8bf7"), U(r"\u4ea4\u63a5"), U(r"\u7ed3\u7b97"), U(r"\u56de\u6536\u6743\u9650")]),
            (U(r"\u5408\u540c\u5ba1\u6838"), U(r"\u5408\u540c\u4e0a\u4f20\u3001AI \u6458\u8981\u3001\u98ce\u9669\u63d0\u9192\u548c\u5ba1\u6279\u3002"), "document_uploaded", [U(r"\u4e0a\u4f20\u5408\u540c"), U(r"AI \u6458\u8981"), U(r"\u4eba\u5de5\u5ba1\u6838"), U(r"\u5f52\u6863")]),
            (U(r"\u95e8\u5e97\u5de1\u68c0"), U(r"\u95e8\u5e97\u536b\u751f\u3001\u9648\u5217\u3001\u4eba\u5458\u548c\u5e93\u5b58\u5de1\u68c0\u3002"), "scheduled", [U(r"\u751f\u6210\u5de1\u68c0\u4efb\u52a1"), U(r"\u95e8\u5e97\u586b\u62a5"), U(r"\u5ba1\u6838\u5f02\u5e38"), U(r"\u8ddf\u8fdb")]),
            (U(r"\u5e93\u5b58\u76d8\u70b9"), U(r"\u76d8\u70b9\u4efb\u52a1\u3001\u5dee\u5f02\u8bb0\u5f55\u548c AI \u5206\u6790\u3002"), "inventory_threshold", [U(r"\u751f\u6210\u76d8\u70b9"), U(r"\u95e8\u5e97\u6267\u884c"), U(r"\u5dee\u5f02\u590d\u6838"), U(r"\u8c03\u6574\u5efa\u8bae")]),
            (U(r"\u8425\u9500\u6d3b\u52a8"), U(r"\u4ece\u9009\u9898\u3001\u7d20\u6750\u3001\u5ba1\u6838\u5230\u53d1\u5e03\u8ddf\u8e2a\u3002"), "manual", [U(r"\u63d0\u4ea4\u65b9\u6848"), U(r"AI \u751f\u6210\u6587\u6848"), U(r"\u5ba1\u6838"), U(r"\u53d1\u5e03")]),
            (U(r"\u54c1\u724c\u4e0a\u65b0"), U(r"\u65b0\u54c1\u8d44\u6599\u3001\u57f9\u8bad\u3001\u5e93\u5b58\u548c\u8425\u9500\u4e0a\u67b6\u3002"), "manual", [U(r"\u54c1\u724c\u8d44\u6599"), U(r"\u57f9\u8bad"), U(r"\u4e0a\u67b6"), U(r"\u590d\u76d8")]),
        ]
        now = ts()
        for name, desc, trigger, steps in templates:
            exists = conn.execute("select id from workflow_templates where name=?", (name,)).fetchone()
            if not exists:
                conn.execute(
                    "insert into workflow_templates(template_id,name,description,trigger_type,steps_json,owner,status,ai_recommendation,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?)",
                    ("WF-" + uuid.uuid4().hex[:10], name, desc, trigger, json.dumps(steps, ensure_ascii=False), U(r"\u7cfb\u7edf"), "active", U(r"\u7b49\u5f85 AI \u63a5\u5165\u540e\u751f\u6210\u6d41\u7a0b\u4f18\u5316\u5efa\u8bae\u3002"), user_id, now, now),
                )

    def automation_summary(self):
        with db() as conn:
            self.seed_workflow_templates(conn)
            running = conn.execute("select count(*) c from automations where status='running'").fetchone()["c"]
            pending = conn.execute("select count(*) c from automations where status in ('draft','active','paused')").fetchone()["c"]
            failed = conn.execute("select count(*) c from automation_runs where status='failed'").fetchone()["c"]
            templates = conn.execute("select * from workflow_templates order by updated_at desc limit 50").fetchall()
            automations = conn.execute("select * from automations order by updated_at desc limit 50").fetchall()
            runs = conn.execute("select * from automation_runs order by created_at desc limit 20").fetchall()
            notifications = conn.execute("select * from notifications order by created_at desc limit 20").fetchall()
        daily_jobs = [
            U(r"CEO \u6bcf\u65e5\u7ecf\u8425\u65e5\u62a5"),
            U(r"\u5e93\u5b58\u98ce\u9669\u626b\u63cf"),
            U(r"\u9500\u552e\u8d8b\u52bf\u626b\u63cf"),
            U(r"\u7814\u7a76\u6458\u8981"),
            U(r"\u77e5\u8bc6\u5e93\u6458\u8981"),
        ]
        triggers = ["manual", "scheduled", "sap_data_change", "document_uploaded", "knowledge_approved", "research_approved", "inventory_threshold", "sales_threshold"]
        actions = ["generate_summary", "create_task", "notify_manager", "generate_report", "suggest_purchasing", "suggest_markdown", "suggest_transfer", "create_meeting_note"]
        channels = ["in_app", "email", "enterprise_wechat_placeholder", "sms_placeholder"]
        return {"running": running, "pending": pending, "failed": failed, "templates": templates, "automations": automations, "runs": runs, "notifications": notifications, "daily_jobs": daily_jobs, "triggers": triggers, "actions": actions, "channels": channels}

    def login(self, msg=""):
        body = f"""
<div class="panel form">
  <form method="post" action="/login">
    <label>{T['email']}</label><input name="email" type="email" autocomplete="username" required>
    <label>{T['password']}</label><input name="password" type="password" autocomplete="current-password" required>
    <p><button>{T['login']}</button></p>
  </form>
  <p><a href="/register">{T['register']}</a></p>
</div>"""
        self.out(layout(T["brand"], body, msg=msg))

    def login_post(self):
        form = self.form()
        email = form.get("email", "").strip().lower()
        password = form.get("password", "")
        now = int(time.time())
        with db() as conn:
            user = conn.execute("select * from users where email=?", (email,)).fetchone()
            if user and user["locked_until"] and user["locked_until"] > now:
                return self.login(T["locked"])
            ok = bool(user and user["status"] == "approved" and cp(password, user["password_hash"]))
            if ok:
                new_hash = hp(password) if needs_password_upgrade(password, user["password_hash"]) else user["password_hash"]
                conn.execute(
                    "update users set password_hash=?, failed_attempts=0, locked_until=0, last_login=?, updated_at=? where id=?",
                    (new_hash, now, now, user["id"]),
                )
                return self.redir("/", "fp_session={}; Path=/; HttpOnly; Secure; SameSite=Lax".format(sign(str(user["id"]))))
            if user:
                attempts = int(user["failed_attempts"] or 0) + 1
                locked_until = now + LOCK_SECONDS if attempts >= LOCK_LIMIT else 0
                conn.execute(
                    "update users set failed_attempts=?, locked_until=?, updated_at=? where id=?",
                    (attempts, locked_until, now, user["id"]),
                )
                if locked_until:
                    return self.login(T["locked"])
        return self.login(T["bad"])

    def register(self, msg=""):
        body = f"""
<div class="panel form">
  <form method="post" action="/register">
    <label>{T['name']}</label><input name="name" required>
    <label>{T['phone']}</label><input name="phone">
    <label>{T['store']}</label><input name="store">
    <label>{T['email']}</label><input name="email" type="email" autocomplete="username" required>
    <label>{T['password']}</label><input name="password" type="password" autocomplete="new-password" required>
    <p><button>{T['register']}</button></p>
  </form>
  <p><a href="/login">{T['login']}</a></p>
</div>"""
        self.out(layout(T["register"], body, msg=msg))

    def register_post(self):
        form = self.form()
        try:
            with db() as conn:
                conn.execute(
                    "insert into users(email,name,phone,store,role,status,password_hash,created_at,updated_at) values(?,?,?,?,?,?,?,?,?)",
                    (
                        form.get("email", "").strip().lower(),
                        form.get("name", "").strip(),
                        form.get("phone", "").strip(),
                        form.get("store", "").strip(),
                        "employee",
                        "pending",
                        hp(form.get("password", "")),
                        int(time.time()),
                        int(time.time()),
                    ),
                )
            return self.login(T["pending"])
        except sqlite3.IntegrityError:
            return self.register(T["duplicate"])

    def card(self, title, text, href, cls="btn", allow=True):
        if allow:
            action = f'<a class="{cls} full" href="{esc(href)}">{esc(title)}</a>'
            extra = ""
        else:
            action = f'<span class="btn gray full">{T["no_permission"]}</span>'
            extra = " disabled"
        return f'<div class="card{extra}"><div><h2>{esc(title)}</h2><p>{esc(text)}</p></div>{action}</div>'

    def metric(self, label, value, note=""):
        return '<div class="metric"><span>{}</span><strong>{}</strong><span>{}</span></div>'.format(esc(label), esc(value), esc(note))

    def bullets(self, items):
        clean = [item for item in items if item]
        return '<ul class="list">' + "".join("<li>{}</li>".format(esc(item)) for item in clean) + "</ul>"

    def require_login(self, user):
        if not user:
            self.redir("/login")
            return None
        return user

    def can_open(self, user, roles):
        return bool(user and user["role"] in roles)

    def log_action(self, user, action, target_type="", target_id=None, detail=""):
        try:
            with db() as conn:
                conn.execute(
                    "insert into activity_log(user_id,action,target_type,target_id,detail,created_at) values(?,?,?,?,?,?)",
                    (user["id"] if user else None, action, target_type, target_id, detail, ts()),
                )
        except Exception:
            pass

    def record_allowed(self, user, module):
        data = MODULES.get("/" + module_key(module))
        return bool(data and self.can_open(user, data[2]))

    def can_view_knowledge(self, user, row):
        if not user or not row:
            return False
        visibility = row["visibility"] if "visibility" in row.keys() else "public_internal"
        if visibility == "public_internal":
            return True
        if visibility == "manager_only":
            return user["role"] in ("boss", "admin", "store_manager")
        if visibility == "finance_only":
            return user["role"] in ("boss", "admin", "finance")
        if visibility == "owner_only":
            return int(row["created_by"] or 0) == int(user["id"])
        if visibility == "restricted":
            return user["role"] in ("boss", "admin")
        return user["role"] in ("boss", "admin")

    def knowledge_to_json(self, row, include_body=True):
        data = row_dict(row) or {}
        result = {
            "id": data.get("id"),
            "knowledge_id": data.get("knowledge_id") or f"KB-{data.get('id')}",
            "title": data.get("title"),
            "content": data.get("body") if include_body else None,
            "source_type": data.get("source_type"),
            "source_id": data.get("source_id"),
            "source_file_id": data.get("source_file_id"),
            "object_type": data.get("object_type"),
            "object_id": data.get("object_id"),
            "summary": data.get("summary") or data.get("ai_summary"),
            "human_summary": data.get("human_summary"),
            "keywords": data.get("keywords"),
            "tags": data.get("tags"),
            "auto_tags": data.get("auto_tags"),
            "manual_tags": data.get("manual_tags"),
            "status": data.get("status") or "draft",
            "visibility": data.get("visibility") or "public_internal",
            "embedding_status": data.get("embedding_status") or "pending",
            "created_by": data.get("created_by"),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
        }
        if not include_body:
            result.pop("content", None)
        return result

    def create_chunks(self, conn, knowledge_id, document_id, text, now):
        conn.execute("delete from knowledge_chunks where knowledge_id=?", (knowledge_id,))
        chunks = chunk_text(text)
        for idx, part in enumerate(chunks):
            conn.execute(
                "insert into knowledge_chunks(chunk_id,knowledge_id,document_id,chunk_index,chunk_text,token_count,embedding_status,created_at) values(?,?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, knowledge_id, document_id, idx, part, max(1, len(part) // 2), "pending", now),
            )
        return len(chunks)

    def knowledge_status_text(self, row):
        status = (row["status"] if row and "status" in row.keys() else "") or "draft"
        labels = {
            "draft": U(r"\u8349\u7a3f"),
            "uploaded": U(r"\u5df2\u4e0a\u4f20"),
            "parsed": U(r"\u89e3\u6790\u5b8c\u6210"),
            "summarized": U(r"\u7b49\u5f85 AI \u6458\u8981\u751f\u6210"),
            "embedded": U(r"\u7b49\u5f85\u5411\u91cf\u5316"),
            "ready": U(r"\u53ef\u7528\u4e8e AI \u67e5\u8be2"),
            "failed": U(r"\u5904\u7406\u5931\u8d25"),
        }
        return labels.get(status, status)

    def build_ai_answer(self, question, scope, rows):
        citations = []
        for row in rows[:5]:
            citations.append(
                {
                    "knowledge_id": row["knowledge_id"] or f"KB-{row['id']}",
                    "title": row["title"],
                    "status": row["status"] or "draft",
                    "source_type": row["source_type"],
                    "url": f"/knowledge/view?id={row['id']}",
                }
            )
        if citations:
            answer = U(r"AI \u67e5\u8be2\u4e2d\u5fc3\u5df2\u627e\u5230\u76f8\u5173\u77e5\u8bc6\u6761\u76ee\u3002\u5f53\u524d\u7248\u672c\u53ea\u505a\u68c0\u7d22\u548c\u5f15\u7528\u51c6\u5907\uff0c\u4e0d\u751f\u6210\u672a\u7ecf\u9a8c\u8bc1\u7684\u7ecf\u8425\u7ed3\u8bba\u3002")
            confidence = "retrieval_ready"
        else:
            answer = U(r"AI \u67e5\u8be2\u4e2d\u5fc3\u5df2\u5efa\u7acb\u3002\u5f53\u524d\u7b49\u5f85\u63a5\u5165\u66f4\u591a\u77e5\u8bc6\u5e93\u5185\u5bb9\u3001SAP \u6570\u636e\u548c\u5927\u6a21\u578b API\u3002")
            confidence = "no_internal_hit"
        return {
            "answer": answer,
            "confidence": confidence,
            "cited_documents": citations,
            "cited_chunks": [],
            "cited_sap_records": [],
            "related_objects": [],
            "generated_at": ts(),
            "model_name": os.environ.get("AI_MODEL_NAME", "not_connected"),
            "limitations": [
                U(r"\u672a\u7f16\u9020 SAP \u6570\u636e\u6216\u7ecf\u8425\u7ed3\u8bba\u3002"),
                U(r"\u5411\u91cf\u68c0\u7d22\u548c\u771f\u6b63\u5927\u6a21\u578b\u56de\u7b54\u5c06\u5728\u540e\u7eed\u63a5\u5165\u3002"),
                U(r"\u7b54\u6848\u9700\u4f9d\u636e\u5f15\u7528\u6765\u6e90\u590d\u6838\u3002"),
            ],
        }

    def placeholder(self, user, title, text):
        user = self.require_login(user)
        if not user:
            return
        api_list = [
            "POST /api/upload",
            "POST /api/knowledge/create",
            "GET /api/knowledge/list",
            "GET /api/knowledge/:id",
            "POST /api/search/web",
            "POST /api/search/save",
            "POST /api/ai/chat",
            "POST /api/ai/summarize",
            "POST /api/ai/classify",
            "GET /api/dashboard/summary",
        ]
        body = f"""
<div class="panel">
  <h2>{esc(title)}</h2>
  <p>{esc(text)}</p>
  <h2>{U(r'\u5df2\u9884\u7559\u63a5\u53e3')}</h2>
  {self.bullets(api_list)}
  <p><a class="btn" href="/">{U(r'\u8fd4\u56de\u9996\u9875')}</a></p>
</div>"""
        self.out(layout(title, body, user=user))

    def module_page(self, user, path):
        user = self.require_login(user)
        if not user:
            return
        module = module_key(path)
        title, text, roles = MODULES[path]
        if not self.can_open(user, roles):
            return self.dashboard(user)
        q = parse_qs(urlparse(self.path).query).get("q", [""])[0].strip()
        sql = "select * from records where module=? and status!='deleted'"
        params = [module]
        if q:
            sql += " and (title like ? or tags like ? or summary like ? or data_json like ?)"
            like = "%" + q + "%"
            params += [like, like, like, like]
        sql += " order by updated_at desc limit 100"
        with db() as conn:
            rows = conn.execute(sql, params).fetchall()
        abilities = [
            U(r"\u65b0\u5efa / \u7f16\u8f91 / \u67e5\u770b\u8be6\u60c5"),
            U(r"\u641c\u7d22 / \u7b5b\u9009 / \u6807\u7b7e\u7ba1\u7406"),
            U(r"\u4e0a\u4f20\u56fe\u7247\u3001PDF\u3001Word\u3001Excel\u3001PPT\u3001TXT\u3001Markdown"),
            U(r"\u6587\u4ef6\u5939 / \u81ea\u52a8\u5f52\u6863 / \u65f6\u95f4\u8f74"),
            U(r"AI \u603b\u7ed3 / AI \u5efa\u8bae / AI \u67e5\u8be2"),
            U(r"\u64cd\u4f5c\u65e5\u5fd7 / \u6743\u9650\u63a7\u5236 / Excel \u5bfc\u5165\u5bfc\u51fa"),
        ]
        items = ""
        for row in rows:
            items += "<tr><td>{}</td><td>{}</td><td>{}</td><td><a href=\"/records/view?id={}\">{}</a> <a href=\"/records/edit?id={}\">{}</a></td></tr>".format(
                esc(row["title"]),
                esc(row["tags"]),
                esc(dt(row["updated_at"])),
                row["id"],
                U(r"\u8be6\u60c5"),
                row["id"],
                U(r"\u7f16\u8f91"),
            )
        if not items:
            items = '<tr><td colspan="4" class="small">{}</td></tr>'.format(U(r"\u6682\u65e0\u6863\u6848\uff0c\u53ef\u4ee5\u5148\u65b0\u5efa\u4e00\u6761\u3002"))
        body = f"""
<div class="panel">
  <h2>{esc(title)}</h2>
  <p>{esc(text)}</p>
  <div class="inline">
    <a class="btn" href="/records/new?module={esc(module)}">{U(r'\u65b0\u5efa')}</a>
    <a class="btn green" href="/records/export?module={esc(module)}">{U(r'Excel \u5bfc\u51fa')}</a>
    <a class="btn orange" href="/upload">{U(r'\u4e0a\u4f20\u9644\u4ef6')}</a>
  </div>
</div>
<div class="panel">
  <form method="get" action="/{esc(module)}">
    <label>{U(r'\u641c\u7d22')}</label><input name="q" value="{esc(q)}" placeholder="{U(r'\u8f93\u5165\u540d\u79f0\u3001\u6807\u7b7e\u6216\u5185\u5bb9')}">
    <p><button>{U(r'\u641c\u7d22')}</button></p>
  </form>
  <table><thead><tr><th>{U(r'\u540d\u79f0')}</th><th>{U(r'\u6807\u7b7e')}</th><th>{U(r'\u66f4\u65b0')}</th><th>{T['action']}</th></tr></thead><tbody>{items}</tbody></table>
</div>
<div class="panel">
  <h2>{U(r'\u901a\u7528\u80fd\u529b')}</h2>
  {self.bullets(abilities)}
  <form method="post" action="/records/import">
    <input type="hidden" name="module" value="{esc(module)}">
    <label>{U(r'Excel/CSV \u6279\u91cf\u5bfc\u5165')}</label>
    <textarea name="csv_text" rows="5" placeholder="{U(r'\u7c98\u8d34 Excel \u590d\u5236\u7684\u8868\u683c\uff1a\u7b2c\u4e00\u5217\u4e3a\u540d\u79f0\uff0c\u7b2c\u4e8c\u5217\u4e3a\u6807\u7b7e\uff0c\u7b2c\u4e09\u5217\u4e3a\u5907\u6ce8')}"></textarea>
    <p><button>{U(r'\u6279\u91cf\u5bfc\u5165')}</button></p>
  </form>
</div>"""
        self.out(layout(title, body, user=user))

    def record_form(self, user, edit=False):
        user = self.require_login(user)
        if not user:
            return
        query = parse_qs(urlparse(self.path).query)
        row = None
        module = module_key(query.get("module", [""])[0])
        if edit:
            rid = query.get("id", [""])[0]
            with db() as conn:
                row = conn.execute("select * from records where id=? and status!='deleted'", (rid,)).fetchone()
            if not row:
                return self.redir("/")
            module = row["module"]
        if not self.record_allowed(user, module):
            return self.dashboard(user)
        title = row["title"] if row else ""
        tags = row["tags"] if row else ""
        summary = row["summary"] if row else ""
        data = json.loads(row["data_json"] or "{}") if row else {}
        body = f"""
<div class="panel form">
  <form method="post" action="/records/save">
    <input type="hidden" name="id" value="{esc(row['id'] if row else '')}">
    <input type="hidden" name="module" value="{esc(module)}">
    <label>{U(r'\u540d\u79f0')}</label><input name="title" value="{esc(title)}" required>
    <label>{U(r'\u6807\u7b7e')}</label><input name="tags" value="{esc(tags)}" placeholder="{U(r'\u591a\u4e2a\u6807\u7b7e\u7528\u9017\u53f7\u5206\u9694')}">
    <label>{U(r'\u6458\u8981')}</label><textarea name="summary">{esc(summary)}</textarea>
    <label>{U(r'\u6838\u5fc3\u5b57\u6bb51')}</label><input name="field1" value="{esc(data.get('field1',''))}">
    <label>{U(r'\u6838\u5fc3\u5b57\u6bb52')}</label><input name="field2" value="{esc(data.get('field2',''))}">
    <label>{U(r'\u8be6\u7ec6\u5185\u5bb9')}</label><textarea name="body">{esc(data.get('body',''))}</textarea>
    <p><button>{T['save']}</button></p>
  </form>
</div>"""
        self.out(layout((U(r"\u7f16\u8f91") if edit else U(r"\u65b0\u5efa")) + " - " + module_title(module), body, user=user))

    def record_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        form = self.form()
        module = module_key(form.get("module"))
        if not self.record_allowed(user, module):
            return self.dashboard(user)
        rid = form.get("id", "").strip()
        title = form.get("title", "").strip()
        data = {"field1": form.get("field1", ""), "field2": form.get("field2", ""), "body": form.get("body", "")}
        now = ts()
        with db() as conn:
            if rid:
                conn.execute(
                    "update records set title=?, tags=?, summary=?, data_json=?, updated_at=? where id=?",
                    (title, form.get("tags", ""), form.get("summary", ""), json.dumps(data, ensure_ascii=False), now, rid),
                )
                target_id = int(rid)
                action = "record_update"
            else:
                cur = conn.execute(
                    "insert into records(module,title,tags,summary,data_json,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?)",
                    (module, title, form.get("tags", ""), form.get("summary", ""), json.dumps(data, ensure_ascii=False), user["id"], now, now),
                )
                target_id = cur.lastrowid
                action = "record_create"
            conn.execute(
                "insert into timeline_events(target_type,target_id,title,body,created_by,created_at) values(?,?,?,?,?,?)",
                ("record", target_id, U(r"\u6863\u6848\u5df2\u4fdd\u5b58"), title, user["id"], now),
            )
        self.log_action(user, action, "record", target_id, title)
        return self.redir(f"/records/view?id={target_id}")

    def record_view(self, user):
        user = self.require_login(user)
        if not user:
            return
        rid = parse_qs(urlparse(self.path).query).get("id", [""])[0]
        with db() as conn:
            row = conn.execute("select * from records where id=? and status!='deleted'", (rid,)).fetchone()
            events = conn.execute("select * from timeline_events where target_type='record' and target_id=? order by created_at desc limit 20", (rid,)).fetchall()
            logs = conn.execute("select * from activity_log where target_type='record' and target_id=? order by created_at desc limit 20", (rid,)).fetchall()
        if not row or not self.record_allowed(user, row["module"]):
            return self.redir("/")
        data = json.loads(row["data_json"] or "{}")
        event_html = self.bullets([dt(e["created_at"]) + " " + e["title"] for e in events]) if events else "<p class='small'>暂无时间轴。</p>"
        log_html = self.bullets([dt(l["created_at"]) + " " + l["action"] for l in logs]) if logs else "<p class='small'>暂无操作日志。</p>"
        body = f"""
<div class="panel">
  <h2>{esc(row['title'])}</h2>
  <p class="small">{module_title(row['module'])} ｜ {U(r'\u6807\u7b7e')}：{esc(row['tags'])} ｜ {U(r'\u66f4\u65b0')}：{esc(dt(row['updated_at']))}</p>
  <p>{esc(row['summary'])}</p>
  <div class="split">
    <div><h2>{U(r'\u8be6\u7ec6\u5185\u5bb9')}</h2><p>{esc(data.get('body',''))}</p></div>
    <div><h2>{U(r'AI \u5efa\u8bae')}</h2>{self.bullets([U(r'\u5b8c\u5584\u56fe\u7247\u3001\u9644\u4ef6\u548c\u5173\u8054\u5173\u7cfb\u3002'), U(r'\u8865\u5145\u9500\u552e\u6570\u636e\u548c\u5386\u53f2\u8bb0\u5f55\uff0c\u4fbf\u4e8e\u540e\u7eed AI \u5206\u6790\u3002')])}</div>
  </div>
  <div class="inline"><a class="btn" href="/records/edit?id={row['id']}">{U(r'\u7f16\u8f91')}</a><a class="btn gray" href="/{esc(row['module'])}">{U(r'\u8fd4\u56de')}</a><form method="post" action="/records/delete"><input type="hidden" name="id" value="{row['id']}"><button class="red">{U(r'\u5220\u9664')}</button></form></div>
</div>
<div class="split">
  <div class="panel"><h2>{U(r'\u65f6\u95f4\u8f74')}</h2>{event_html}</div>
  <div class="panel"><h2>{U(r'\u64cd\u4f5c\u65e5\u5fd7')}</h2>{log_html}</div>
</div>"""
        self.out(layout(row["title"], body, user=user, wide=True))

    def record_delete(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        form = self.form()
        rid = form.get("id")
        with db() as conn:
            row = conn.execute("select * from records where id=?", (rid,)).fetchone()
            if row and self.record_allowed(user, row["module"]):
                conn.execute("update records set status='deleted', updated_at=? where id=?", (ts(), rid))
                self.log_action(user, "record_delete", "record", rid, row["title"])
                return self.redir("/" + row["module"])
        return self.redir("/")

    def records_export(self, user):
        user = self.require_login(user)
        if not user:
            return
        module = module_key(parse_qs(urlparse(self.path).query).get("module", [""])[0])
        if not self.record_allowed(user, module):
            return self.dashboard(user)
        with db() as conn:
            rows = conn.execute("select * from records where module=? and status!='deleted' order by updated_at desc", (module,)).fetchall()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([U(r"\u540d\u79f0"), U(r"\u6807\u7b7e"), U(r"\u6458\u8981"), U(r"\u66f4\u65b0\u65f6\u95f4")])
        for row in rows:
            writer.writerow([row["title"], row["tags"], row["summary"], dt(row["updated_at"])])
        return self.file_out(module + "_export.csv", buf.getvalue())

    def records_import(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        form = self.form()
        module = module_key(form.get("module"))
        if not self.record_allowed(user, module):
            return self.dashboard(user)
        text = form.get("csv_text", "")
        count = 0
        now = ts()
        with db() as conn:
            for row in csv.reader(io.StringIO(text), delimiter="\t"):
                if not row:
                    continue
                if len(row) == 1 and "," in row[0]:
                    row = next(csv.reader([row[0]]))
                title = (row[0] if len(row) > 0 else "").strip()
                if not title or title in (U(r"\u540d\u79f0"), "title"):
                    continue
                tags = row[1].strip() if len(row) > 1 else ""
                summary = row[2].strip() if len(row) > 2 else ""
                conn.execute(
                    "insert into records(module,title,tags,summary,data_json,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?)",
                    (module, title, tags, summary, "{}", user["id"], now, now),
                )
                count += 1
        self.log_action(user, "records_import", "record", None, f"{module}:{count}")
        return self.redir("/" + module)

    def upload(self, user):
        user = self.require_login(user)
        if not user:
            return
        module_opts = "".join('<option value="{}">{}</option>'.format(module_key(k), esc(v[0])) for k, v in MODULES.items())
        object_opts = "".join('<option value="{}">{}</option>'.format(module_key(k), esc(v[0])) for k, v in MODULES.items())
        body = f"""
<div class="panel form">
  <h2>{U(r'\u6587\u4ef6\u4e0a\u4f20\u4e0e\u81ea\u52a8\u5f52\u6863')}</h2>
  <form method="post" action="/upload" enctype="multipart/form-data">
    <label>{U(r'\u6587\u4ef6')}</label><input name="file" type="file" required>
    <label>{U(r'\u5f52\u5c5e\u6a21\u5757')}</label><select name="module"><option value="knowledge">{U(r'\u77e5\u8bc6\u4e2d\u5fc3')}</option>{module_opts}</select>
    <label>{U(r'\u5173\u8054\u5bf9\u8c61\u7c7b\u578b')}</label><select name="object_type"><option value="">{U(r'\u6682\u4e0d\u5173\u8054')}</option>{object_opts}</select>
    <label>{U(r'\u5173\u8054\u5bf9\u8c61 ID')}</label><input name="object_id" placeholder="{U(r'\u53ef\u9009\uff1a\u6863\u6848 ID')}">
    <label>{U(r'\u53ef\u89c1\u8303\u56f4')}</label><select name="visibility"><option value="public_internal">{U(r'\u516c\u53f8\u5185\u90e8')}</option><option value="manager_only">{U(r'\u7ba1\u7406\u5c42')}</option><option value="finance_only">{U(r'\u8d22\u52a1')}</option><option value="owner_only">{U(r'\u4ec5\u521b\u5efa\u4eba')}</option><option value="restricted">{U(r'\u8001\u677f/\u7ba1\u7406\u5458')}</option></select>
    <label>{U(r'\u6240\u5c5e\u5206\u7c7b')}</label><input name="category" placeholder="01_公司制度 / 02_产品资料 / 07_库存采购">
    <label>{U(r'\u8865\u5145\u8bf4\u660e')}</label><textarea name="description"></textarea>
    <p><button>{U(r'\u4e0a\u4f20\u5e76\u81ea\u52a8\u5165\u5e93')}</button></p>
  </form>
</div>"""
        self.out(layout(U(r"\u6587\u4ef6\u4e0a\u4f20"), body, user=user))

    def upload_post(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        form = self.multipart()
        item = form["file"] if "file" in form else None
        if not item or not getattr(item, "filename", ""):
            return self.upload(user)
        original = Path(item.filename).name
        module = module_key(form.getfirst("module", "knowledge"))
        category = form.getfirst("category", "").strip()
        description = form.getfirst("description", "").strip()
        object_type = module_key(form.getfirst("object_type", ""))
        object_id = form.getfirst("object_id", "").strip()
        visibility = form.getfirst("visibility", "public_internal")
        if visibility not in ("public_internal", "manager_only", "finance_only", "owner_only", "restricted"):
            visibility = "public_internal"
        folder = Path(UPLOAD_DIR) / module
        folder.mkdir(parents=True, exist_ok=True)
        saved = uuid.uuid4().hex + Path(original).suffix.lower()
        path = folder / saved
        data = item.file.read()
        path.write_bytes(data)
        extracted = extract_file_text(str(path), original)
        combined = "\n".join([original, description, extracted])
        category = category or classify_text(combined)
        summary = summarize_text(extracted or description)
        tags = extract_tags(combined)
        status = "parsed" if extracted else "uploaded"
        knowledge_code = "KB-" + uuid.uuid4().hex[:12]
        now = ts()
        with db() as conn:
            kcur = conn.execute(
                """insert into knowledge_items(
 title,category,tags,body,ai_summary,source_type,source_ref,created_by,created_at,updated_at,
 knowledge_id,source_id,object_type,object_id,summary,keywords,status,visibility,auto_tags,manual_tags,embedding_status
) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    original,
                    category,
                    tags,
                    extracted or description,
                    summary if extracted else U(r"\u7b49\u5f85 AI \u6458\u8981\u751f\u6210"),
                    "document",
                    original,
                    user["id"],
                    now,
                    now,
                    knowledge_code,
                    saved,
                    object_type,
                    int(object_id) if object_id.isdigit() else None,
                    summary,
                    tags,
                    status,
                    visibility,
                    tags,
                    "",
                    "pending",
                ),
            )
            kid = kcur.lastrowid
            fcur = conn.execute(
                "insert into uploaded_files(original_name,saved_name,path,mime,size,category,description,extracted_text,knowledge_id,created_by,created_at) values(?,?,?,?,?,?,?,?,?,?,?)",
                (original, saved, str(path), mimetypes.guess_type(original)[0], len(data), category, description, extracted, kid, user["id"], now),
            )
            fid = fcur.lastrowid
            conn.execute("update knowledge_items set source_file_id=? where id=?", (fid, kid))
            self.create_chunks(conn, kid, fid, extracted, now)
        self.log_action(user, "file_upload", "knowledge", kid, original)
        return self.redir(f"/knowledge/view?id={kid}")

    def knowledge_form(self, user):
        user = self.require_login(user)
        if not user:
            return
        object_opts = "".join('<option value="{}">{}</option>'.format(module_key(k), esc(v[0])) for k, v in MODULES.items())
        body = f"""
<div class="panel form">
  <h2>{U(r'\u65b0\u5efa\u77e5\u8bc6')}</h2>
  <form method="post" action="/knowledge/save">
    <label>{U(r'\u6807\u9898')}</label><input name="title" required>
    <label>{U(r'\u5206\u7c7b')}</label><input name="category" placeholder="01_公司制度">
    <label>{U(r'\u6807\u7b7e')}</label><input name="tags">
    <label>{U(r'\u53ef\u89c1\u8303\u56f4')}</label><select name="visibility"><option value="public_internal">{U(r'\u516c\u53f8\u5185\u90e8')}</option><option value="manager_only">{U(r'\u7ba1\u7406\u5c42')}</option><option value="finance_only">{U(r'\u8d22\u52a1')}</option><option value="owner_only">{U(r'\u4ec5\u521b\u5efa\u4eba')}</option><option value="restricted">{U(r'\u8001\u677f/\u7ba1\u7406\u5458')}</option></select>
    <label>{U(r'\u5173\u8054\u5bf9\u8c61')}</label><select name="object_type"><option value="">{U(r'\u6682\u4e0d\u5173\u8054')}</option>{object_opts}</select>
    <label>{U(r'\u5173\u8054\u5bf9\u8c61 ID')}</label><input name="object_id" placeholder="{U(r'\u53ef\u9009\uff1a\u6863\u6848 ID')}">
    <label>{U(r'\u6b63\u6587')}</label><textarea name="body" required></textarea>
    <p><button>{T['save']}</button></p>
  </form>
</div>"""
        self.out(layout(U(r"\u65b0\u5efa\u77e5\u8bc6"), body, user=user))

    def knowledge_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        form = self.form()
        body = form.get("body", "")
        category = form.get("category", "").strip() or classify_text(body)
        visibility = form.get("visibility", "public_internal")
        if visibility not in ("public_internal", "manager_only", "finance_only", "owner_only", "restricted"):
            visibility = "public_internal"
        object_type = module_key(form.get("object_type", ""))
        object_id = form.get("object_id", "").strip()
        tags = form.get("tags", "") or extract_tags(body)
        summary = summarize_text(body)
        now = ts()
        with db() as conn:
            cur = conn.execute(
                """insert into knowledge_items(
 title,category,tags,body,ai_summary,source_type,source_ref,created_by,created_at,updated_at,
 knowledge_id,source_id,object_type,object_id,summary,keywords,status,visibility,auto_tags,manual_tags,embedding_status
) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    form.get("title", "").strip(),
                    category,
                    tags,
                    body,
                    summary,
                    "note",
                    "",
                    user["id"],
                    now,
                    now,
                    "KB-" + uuid.uuid4().hex[:12],
                    "",
                    object_type,
                    int(object_id) if object_id.isdigit() else None,
                    summary,
                    tags,
                    "ready" if body.strip() else "draft",
                    visibility,
                    tags,
                    "",
                    "pending",
                ),
            )
            kid = cur.lastrowid
            self.create_chunks(conn, kid, None, body, now)
        self.log_action(user, "knowledge_create", "knowledge", kid, form.get("title", ""))
        return self.redir(f"/knowledge/view?id={kid}")

    def knowledge_view(self, user):
        user = self.require_login(user)
        if not user:
            return
        kid = parse_qs(urlparse(self.path).query).get("id", [""])[0]
        with db() as conn:
            row = conn.execute("select * from knowledge_items where id=?", (kid,)).fetchone()
        if not row:
            return self.redir("/knowledge")
        body = f"""
<div class="panel">
  <h2>{esc(row['title'])}</h2>
  <p class="small">{esc(row['category'])} ｜ {esc(row['tags'])} ｜ {esc(row['source_type'])}：{esc(row['source_ref'])}</p>
  <h2>{U(r'AI \u6458\u8981')}</h2><p>{esc(row['ai_summary'])}</p>
  <h2>{U(r'\u6b63\u6587')}</h2><p>{esc(row['body'])}</p>
  <p><a class="btn" href="/ai-query">{U(r'\u7528 AI \u67e5\u8be2')}</a> <a class="btn gray" href="/knowledge">{U(r'\u8fd4\u56de')}</a></p>
</div>"""
        self.out(layout(row["title"], body, user=user, wide=True))

    def ai_assistant(self, user, answer="", question="", refs=None):
        user = self.require_login(user)
        if not user:
            return
        refs = refs or []
        ref_html = self.bullets(refs) if refs else "<p class='small'>暂无引用，提问后会显示来源。</p>"
        body = f"""
<div class="panel form">
  <h2>{U(r'AI \u667a\u80fd\u4f53\u67e5\u8be2')}</h2>
  <form method="post" action="/ai-query">
    <label>{U(r'\u95ee\u9898')}</label><textarea name="question" required>{esc(question)}</textarea>
    <label>{U(r'\u8303\u56f4')}</label><select name="scope"><option value="all">{U(r'\u5168\u516c\u53f8')}</option><option value="stores">{U(r'\u95e8\u5e97')}</option><option value="products">{U(r'\u4ea7\u54c1')}</option><option value="finance">{U(r'\u8d22\u52a1')}</option></select>
    <p><button>{U(r'\u67e5\u8be2')}</button></p>
  </form>
</div>
<div class="panel"><h2>{U(r'AI \u56de\u7b54')}</h2><p>{esc(answer or U(r'\u8bf7\u8f93\u5165\u95ee\u9898\uff0c\u7cfb\u7edf\u4f1a\u5148\u67e5\u5185\u90e8\u77e5\u8bc6\u5e93\u3002'))}</p><h2>{U(r'\u5f15\u7528\u6765\u6e90')}</h2>{ref_html}</div>"""
        self.out(layout(U(r"AI \u667a\u80fd\u4f53\u67e5\u8be2"), body, user=user, wide=True))

    def ai_assistant_post(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        form = self.form()
        question = form.get("question", "").strip()
        words = [w for w in re.split(r"\s+", question) if w][:5]
        with db() as conn:
            rows = []
            for w in words or [question]:
                rows += conn.execute("select * from knowledge_items where title like ? or body like ? or tags like ? order by updated_at desc limit 5", (f"%{w}%", f"%{w}%", f"%{w}%")).fetchall()
        seen, refs, snippets = set(), [], []
        for row in rows:
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            refs.append(f"{row['title']} / {row['category']}")
            snippets.append(row["ai_summary"] or summarize_text(row["body"], 120))
        if snippets:
            answer = U(r"\u6839\u636e\u5185\u90e8\u77e5\u8bc6\u5e93\uff0c\u521d\u6b65\u7ed3\u8bba\uff1a") + " ".join(snippets[:3])
        else:
            answer = U(r"\u5185\u90e8\u77e5\u8bc6\u5e93\u6682\u672a\u547d\u4e2d\u8db3\u591f\u5185\u5bb9\uff0c\u5efa\u8bae\u5148\u4e0a\u4f20\u76f8\u5173\u6587\u6863\uff0c\u6216\u5230\u5916\u7f51\u641c\u7d22\u9875\u6293\u53d6\u8d44\u6599\u540e\u5165\u5e93\u3002")
        self.log_action(user, "ai_query", "knowledge", None, question)
        return self.ai_assistant(user, answer, question, refs)

    def web_search(self, user, msg=""):
        user = self.require_login(user)
        if not user:
            return
        body = f"""
<div class="panel form">
  <h2>{U(r'\u5916\u7f51\u8d44\u6599\u4fdd\u5b58\u5230\u77e5\u8bc6\u5e93')}</h2>
  <p class="small">{U(r'\u7b2c\u4e00\u7248\u652f\u6301\u7c98\u8d34\u7f51\u9875 URL \u6293\u53d6\u6b63\u6587\uff0c\u540e\u7eed\u518d\u63a5 Bing/SerpAPI/Tavily\u3002')}</p>
  <form method="post" action="/web-search">
    <label>URL</label><input name="url" placeholder="https://...">
    <label>{U(r'\u6807\u9898')}</label><input name="title">
    <p><button>{U(r'\u6293\u53d6\u5e76\u4fdd\u5b58')}</button></p>
  </form>
</div>"""
        self.out(layout(U(r"\u5916\u7f51\u641c\u7d22"), body, user=user, msg=msg))

    def web_search_post(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        form = self.form()
        url = form.get("url", "").strip()
        text = fetch_url_text(url)
        if not text:
            return self.web_search(user, U(r"\u6293\u53d6\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5 URL\u3002"))
        title = form.get("title", "").strip() or summarize_text(text, 40)
        now = ts()
        with db() as conn:
            cur = conn.execute(
                "insert into knowledge_items(title,category,tags,body,ai_summary,source_type,source_ref,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?)",
                (title, classify_text(text), extract_tags(text), text, summarize_text(text), U(r"\u5916\u7f51\u641c\u7d22"), url, user["id"], now, now),
            )
            kid = cur.lastrowid
        self.log_action(user, "web_save", "knowledge", kid, url)
        return self.redir(f"/knowledge/view?id={kid}")

    def agents(self, user):
        user = self.require_login(user)
        if not user:
            return
        agents = [U(r"AI \u603b\u7ecf\u7406"), U(r"AI \u8d22\u52a1\u603b\u76d1"), U(r"AI \u91c7\u8d2d\u7ecf\u7406"), U(r"AI \u5e93\u5b58\u7ecf\u7406"), U(r"AI \u54c1\u724c\u7ecf\u7406"), U(r"AI \u95e8\u5e97\u7ecf\u7406"), U(r"AI \u4eba\u4e8b\u7ecf\u7406"), U(r"AI \u5185\u5bb9\u7ecf\u7406"), U(r"AI \u5ba2\u670d"), U(r"AI \u6cd5\u52a1"), U(r"AI \u6570\u636e\u5206\u6790\u5e08"), U(r"AI \u6295\u8d44\u52a9\u624b")]
        cards = "".join(self.card(a, U(r"\u57fa\u4e8e\u6743\u9650\u8303\u56f4\u67e5\u8be2\u6570\u636e\uff0c\u8f93\u51fa\u5efa\u8bae\u548c\u884c\u52a8\u6e05\u5355\u3002"), "/ai-query", "btn", True) for a in agents)
        self.out(layout(U(r"AI \u667a\u80fd\u4f53\u77e9\u9635"), '<div class="grid">' + cards + "</div>", user=user, wide=True))

    def business_overview(self, user):
        user = self.require_login(user)
        if not user:
            return
        s = load_summary()
        metrics = "".join([
            self.metric(U(r"\u672c\u6708\u9500\u552e"), U(r"\uffe5") + money(s.get("month_sales")), pct(s.get("completion_rate"))),
            self.metric(U(r"\u672c\u6708\u6bdb\u5229"), U(r"\uffe5") + money(s.get("month_gross_profit")), U(r"\u6bdb\u5229\u7387 ") + pct(s.get("yesterday_gross_margin"))),
            self.metric(U(r"\u5e93\u5b58\u91d1\u989d"), U(r"\uffe5") + money(s.get("inventory_amount")), U(r"\u98ce\u9669 ") + money(s.get("risk_count"))),
        ])
        body = f"<div class='panel'><h2>{U(r'\u7ecf\u8425\u603b\u89c8')}</h2><div class='metrics'>{metrics}</div>{self.bullets(s.get('ai_suggestions', []))}</div>"
        self.out(layout(U(r"\u7ecf\u8425\u603b\u89c8"), body, user=user, wide=True))

    def sap_sync(self, user):
        user = self.require_login(user)
        if not user:
            return
        s = load_summary()
        body = f"""
<div class="panel">
  <h2>SAP B1 {U(r'\u540c\u6b65\u72b6\u6001')}</h2>
  <div class="metrics">
    {self.metric(U(r'\u6570\u636e\u65e5\u671f'), s.get('data_date'), U(r'\u6458\u8981\u6587\u4ef6'))}
    {self.metric(U(r'\u6628\u65e5\u9500\u552e'), U(r'\uffe5') + money(s.get('yesterday_sales')), U(r'SAP B1'))}
    {self.metric(U(r'\u5e93\u5b58\u91d1\u989d'), U(r'\uffe5') + money(s.get('inventory_amount')), U(r'\u5df2\u540c\u6b65'))}
  </div>
  <p class="small">{U(r'\u624b\u52a8\u540c\u6b65\u5efa\u8bae\u5728\u670d\u52a1\u5668\u6267\u884c systemctl start firefox-sap-sync.service\uff0c\u9875\u9762\u5148\u63d0\u4f9b\u72b6\u6001\u67e5\u770b\u3002')}</p>
</div>"""
        self.out(layout(U(r"SAP B1 \u540c\u6b65"), body, user=user, wide=True))

    def dashboard(self, user):
        role = user["role"]
        can_boss = role in ("boss", "admin", "finance", "purchasing")
        can_manager = role in ("boss", "admin", "store_manager", "purchasing", "finance")
        can_admin = role == "admin"
        cards = [
            self.card(U(r"AI \u603b\u7ecf\u7406"), U(r"\u8001\u677f\u9a7e\u9a76\u8231\uff0c\u67e5\u770b\u7ecf\u8425\u5206\u6790\u548c\u51b3\u7b56\u5efa\u8bae\u3002"), "https://dify.huyan.vafox.com/chat/firefox-ai-ceo", "btn", can_boss),
            self.card(U(r"AI \u5e97\u957f"), U(r"\u95e8\u5e97\u65e5\u5e38\u7ba1\u7406\u3001\u8bdd\u672f\u3001\u4f1a\u5458\u8ddf\u8fdb\u548c\u4efb\u52a1\u63d0\u9192\u3002"), "https://dify.huyan.vafox.com/chat/firefox-ai-store-manager", "btn green", can_manager),
            self.card(U(r"\u706b\u72d0\u72f8\u77e5\u8bc6\u5e93"), U(r"\u67e5\u770b\u516c\u53f8\u67b6\u6784\u3001\u95e8\u5e97 SOP\u3001\u9879\u76ee\u548c\u57f9\u8bad\u8d44\u6599\u3002"), "/wiki/", "btn red", True),
            self.card(U(r"\u95e8\u5e97\u65e5\u62a5"), U(r"\u67e5\u770b\u6bcf\u65e5\u9500\u552e\u3001\u6bdb\u5229\u3001\u4efb\u52a1\u548c\u95e8\u5e97\u590d\u76d8\u3002"), "/wiki/firefox-hq/daily", "btn orange", True),
            self.card(U(r"\u5e93\u5b58\u5206\u6790"), U(r"\u67e5\u770b SAP B1 \u540c\u6b65\u72b6\u6001\u3001\u5e93\u5b58\u548c\u9500\u552e\u6570\u636e\u5165\u53e3\u3002"), "/wiki/firefox-hq/sap-b1", "btn dark", can_manager),
            self.card(U(r"\u7cfb\u7edf\u7ba1\u7406"), U(r"\u5ba1\u6838\u5458\u5de5\u3001\u7981\u7528\u8d26\u53f7\u3001\u4fee\u6539\u89d2\u8272\u548c\u91cd\u7f6e\u5bc6\u7801\u3002"), "/admin", "btn dark", can_admin),
        ]
        info = '<div class="panel"><strong>{}</strong><p class="small">{}：{} · {}：{} · {}：{}</p></div>'.format(
            U(r"\u5f53\u524d\u8d26\u53f7"),
            T["name"],
            esc(user["name"]),
            T["store"],
            esc(user["store"]),
            T["role"],
            esc(ROLES.get(role, role)),
        )
        self.out(layout(U(r"\u706b\u72d0\u72f8\u5de5\u4f5c\u53f0\u9996\u9875"), '<div class="grid">' + "".join(cards) + "</div>" + info, user=user))

    def dashboard(self, user):
        role = user["role"]
        can_boss = role in ("boss", "admin", "finance", "purchasing")
        can_manager = role in ("boss", "admin", "store_manager", "purchasing", "finance")
        can_admin = role == "admin"
        summary = load_summary()
        quick = f"""
<div class="panel">
  <h2>{U(r'\u5feb\u901f\u7ecf\u8425\u63d0\u793a')}</h2>
  <p class="small">{U(r'\u6628\u65e5\u9500\u552e')}：{U(r'\uffe5') + money(summary.get("yesterday_sales"))} ｜ {U(r'\u672c\u6708\u5b8c\u6210\u7387')}：{pct(summary.get("completion_rate"))} ｜ {U(r'\u6570\u636e\u65e5\u671f')}：{esc(summary.get("data_date"))}</p>
</div>"""
        cards = [
            self.card(U(r"AI \u603b\u7ecf\u7406"), U(r"\u6253\u5f00 AI \u603b\u7ecf\u7406\u6668\u62a5\uff0c\u67e5\u770b\u9500\u552e\u3001\u6bdb\u5229\u3001\u5e93\u5b58\u548c\u7ecf\u8425\u5efa\u8bae\u3002"), "/ai-ceo", "btn", can_boss),
            self.card(U(r"\u7ecf\u8425\u603b\u89c8"), U(r"\u8fdb\u5165\u9500\u552e\u3001\u6bdb\u5229\u3001\u5e93\u5b58\u548c\u98ce\u9669\u6570\u636e\u770b\u677f\u3002"), "/overview", "btn dark", can_boss),
            self.card(U(r"\u95e8\u5e97\u4e2d\u5fc3"), U(r"\u95e8\u5e97\u6863\u6848\u3001\u7ecf\u8425\u6570\u636e\u3001\u65f6\u95f4\u8f74\u548c AI \u5206\u6790\u3002"), "/stores", "btn green", can_manager),
            self.card(U(r"\u5458\u5de5\u4e2d\u5fc3"), U(r"\u5458\u5de5\u6863\u6848\u3001\u9500\u552e\u8868\u73b0\u3001\u57f9\u8bad\u8bb0\u5f55\u548c AI \u5efa\u8bae\u3002"), "/employees", "btn green", can_manager),
            self.card(U(r"\u54c1\u724c\u4e2d\u5fc3"), U(r"\u54c1\u724c\u6863\u6848\u3001\u5408\u4f5c\u6587\u4ef6\u3001\u54c1\u724c\u9500\u552e\u548c AI \u5206\u6790\u3002"), "/brands", "btn", role in ("boss", "admin", "purchasing", "store_manager")),
            self.card(U(r"\u4ea7\u54c1\u4e2d\u5fc3"), U(r"\u4ea7\u54c1\u6863\u6848\u3001\u5e93\u5b58\u3001\u9500\u552e\u6570\u636e\u548c AI \u8bdd\u672f\u3002"), "/products", "btn", True),
            self.card(U(r"\u4f9b\u5e94\u5546\u4e2d\u5fc3"), U(r"\u4f9b\u5e94\u5546\u6863\u6848\u3001\u5408\u540c\u3001\u91c7\u8d2d\u548c\u4ed8\u6b3e\u8bb0\u5f55\u3002"), "/suppliers", "btn orange", role in ("boss", "admin", "purchasing", "finance")),
            self.card(U(r"\u987e\u5ba2/\u4f1a\u5458\u4e2d\u5fc3"), U(r"\u4f1a\u5458\u6863\u6848\u3001\u8d2d\u4e70\u5386\u53f2\u3001\u504f\u597d\u6807\u7b7e\u548c\u7ef4\u62a4\u5efa\u8bae\u3002"), "/members", "btn green", True),
            self.card(U(r"\u8d22\u52a1\u4e2d\u5fc3"), U(r"\u5bf9\u516c\u8d26\u52a1\u3001\u73b0\u91d1\u8d26\u3001\u4ed8\u6b3e\u8bc4\u4f30\u548c\u8d44\u91d1\u8ba1\u5212\u3002"), "/finance", "btn dark", role in ("boss", "admin", "finance")),
            self.card(U(r"\u5e93\u5b58\u91c7\u8d2d\u4e2d\u5fc3"), U(r"\u67e5\u770b SAP B1 \u540c\u6b65\u3001\u5e93\u5b58\u91d1\u989d\u548c\u91c7\u8d2d\u9884\u8b66\u3002"), "/inventory", "btn dark", can_manager),
            self.card(U(r"\u5185\u5bb9\u53d1\u5e03\u4e2d\u5fc3"), U(r"\u65b0\u5a92\u4f53\u63a8\u5e7f\u3001\u95e8\u5e97\u5185\u5bb9\u3001\u4ea7\u54c1\u7d20\u6750\u548c\u53d1\u5e03\u8ba1\u5212\u3002"), "/content", "btn orange", True),
            self.card(U(r"\u77e5\u8bc6\u4e2d\u5fc3"), U(r"\u516c\u53f8\u5236\u5ea6\u3001SOP\u3001\u57f9\u8bad\u3001\u4ea7\u54c1\u8d44\u6599\u548c AI \u5f00\u53d1\u6587\u6863\u3002"), "/knowledge", "btn red", True),
            self.card(U(r"AI \u667a\u80fd\u4f53\u67e5\u8be2"), U(r"\u4f18\u5148\u67e5\u5185\u90e8\u77e5\u8bc6\u5e93\uff0c\u4e0d\u8db3\u65f6\u518d\u63a5\u5916\u7f51\u641c\u7d22\u3002"), "/ai-assistant", "btn", True),
            self.card(U(r"\u4efb\u52a1\u4e2d\u5fc3"), U(r"\u4eca\u65e5\u5f85\u529e\u3001\u95e8\u5e97\u4efb\u52a1\u3001\u81ea\u52a8\u5316\u4efb\u52a1\u548c\u8ddf\u8fdb\u63d0\u9192\u3002"), "/tasks", "btn", True),
            self.card(U(r"AI \u81ea\u52a8\u5316"), U(r"\u6d41\u7a0b\u6a21\u677f\u3001\u89e6\u53d1\u5668\u3001AI \u52a8\u4f5c\u3001\u6267\u884c\u5386\u53f2\u548c\u901a\u77e5\u4e2d\u5fc3\u3002"), "/automation", "btn", can_manager),
            self.card(U(r"AI \u8bb0\u5fc6\u4e2d\u5fc3"), U(r"\u957f\u671f\u7ecf\u8425\u539f\u5219\u3001\u51b3\u7b56\u3001\u504f\u597d\u3001\u5b9a\u4ef7\u548c\u98ce\u9669\u8bb0\u5fc6\u3002"), "/memory", "btn", True),
            self.card(U(r"\u4f01\u4e1a\u77e5\u8bc6\u56fe\u8c31"), U(r"\u8fde\u63a5\u95e8\u5e97\u3001\u54c1\u724c\u3001\u4ea7\u54c1\u3001\u77e5\u8bc6\u3001\u8bb0\u5fc6\u3001\u4efb\u52a1\u548c\u98ce\u9669\u3002"), "/graph", "btn green", can_manager),
            self.card(U(r"\u7cfb\u7edf\u7ba1\u7406"), U(r"\u5ba1\u6838\u5458\u5de5\u3001\u7981\u7528\u8d26\u53f7\u3001\u4fee\u6539\u89d2\u8272\u548c\u91cd\u7f6e\u5bc6\u7801\u3002"), "/admin", "btn dark", can_admin),
        ]
        info = '<div class="panel"><strong>{}</strong><p class="small">{}：{} ｜ {}：{} ｜ {}：{}</p></div>'.format(
            U(r"\u5f53\u524d\u8d26\u53f7"),
            T["name"],
            esc(user["name"]),
            T["store"],
            esc(user["store"]),
            T["role"],
            esc(ROLES.get(role, role)),
        )
        info = '<div class="panel"><strong>{}</strong><p class="small">{}：{} ｜ {}：{} ｜ {}：{}</p></div>'.format(
            U(r"\u5f53\u524d\u8d26\u53f7"), T["name"], esc(user["name"]), T["store"], esc(user["store"]), T["role"], esc(ROLES.get(role, role))
        )
        self.out(layout(T["brand"], quick + '<div class="grid">' + "".join(cards) + "</div>" + info, user=user, wide=True))

    def ai_ceo(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_open(user, ("boss", "admin", "finance", "purchasing")):
            return self.dashboard(user)
        summary = load_summary()
        metrics = "".join(
            [
                self.metric(U(r"\u672c\u6708\u9500\u552e"), U(r"\uffe5") + money(summary.get("month_sales")), U(r"\u5b8c\u6210\u7387 ") + pct(summary.get("completion_rate"))),
                self.metric(U(r"\u672c\u6708\u6bdb\u5229"), U(r"\uffe5") + money(summary.get("month_gross_profit")), U(r"\u6628\u65e5\u6bdb\u5229\u7387 ") + pct(summary.get("yesterday_gross_margin"))),
                self.metric(U(r"\u5e93\u5b58\u91d1\u989d"), U(r"\uffe5") + money(summary.get("inventory_amount")), U(r"\u98ce\u9669\u6570\u91cf ") + money(summary.get("risk_count"))),
                self.metric(U(r"\u4f1a\u5458"), U(r"\u5f85\u63a5\u5165"), U(r"\u540e\u7eed\u4ece SAP/Dify \u8865\u5145")),
                self.metric(U(r"\u6570\u636e\u65e5\u671f"), summary.get("data_date"), U(r"\u6bcf\u65e5 2:00 \u81ea\u52a8\u540c\u6b65")),
            ]
        )
        body = f"""
<div class="panel">
  <h2>{U(r'AI \u603b\u7ecf\u7406\u6668\u62a5')}</h2>
  <div class="metrics">{metrics}</div>
  <div class="split">
    <div><h2>{U(r'\u7ecf\u8425\u5224\u65ad')}</h2>{self.bullets(summary.get("ai_suggestions", [])[:5])}</div>
    <div><h2>{U(r'\u4eca\u65e5\u52a8\u4f5c')}</h2>{self.bullets(summary.get("todos", []))}</div>
  </div>
  <p><a class="btn" href="https://dify.huyan.vafox.com">{U(r'\u7ee7\u7eed\u548c AI \u804a\u5929')}</a></p>
</div>"""
        self.out(layout(U(r"AI \u603b\u7ecf\u7406"), body, user=user, wide=True))

    def ai_store_manager(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_open(user, ("boss", "admin", "store_manager", "purchasing", "finance")):
            return self.dashboard(user)
        summary = load_summary()
        stores = summary.get("top_stores", []) or []
        if user["role"] == "store_manager" and user["store"]:
            store_key = str(user["store"]).strip()
            stores = [s for s in stores if store_key in str(s.get("store", ""))] or stores[:1]
        store_rows = ""
        for item in stores[:8]:
            store_rows += '<div class="store-row"><strong>{}</strong><span>{}：￥{}</span><span>{}：￥{}</span></div>'.format(
                esc(item.get("store", U(r"\u672a\u547d\u540d\u95e8\u5e97"))),
                U(r"\u9500\u552e"),
                money(item.get("sales")),
                U(r"\u6bdb\u5229"),
                money(item.get("gross_profit")),
            )
        if not store_rows:
            store_rows = '<p class="small">{}</p>'.format(U(r"\u6682\u65e0\u95e8\u5e97\u6570\u636e\uff0c\u5148\u663e\u793a\u6d4b\u8bd5\u6a21\u677f\u3002"))
        body = f"""
<div class="panel">
  <h2>{U(r'AI \u5e97\u957f')}</h2>
  <p class="small">{U(r'\u5e97\u957f\u53ea\u770b\u81ea\u5df1\u6709\u6743\u9650\u7684\u95e8\u5e97\uff1b\u8001\u677f\u548c\u7ba1\u7406\u5458\u53ef\u770b\u5168\u90e8\u95e8\u5e97\u3002')}</p>
  {store_rows}
</div>
<div class="split">
  <div class="panel"><h2>{U(r'\u4eca\u65e5\u4efb\u52a1')}</h2>{self.bullets([U(r'\u68c0\u67e5\u672c\u5e97\u65e5\u76ee\u6807\u5dee\u989d\u3002'), U(r'\u8ddf\u8fdb\u91cd\u70b9\u4f1a\u5458\u56de\u8bbf\u3002'), U(r'\u76d8\u70b9\u9ad8\u5e93\u5b58\u548c\u4f4e\u9500\u552e\u5546\u54c1\u3002')])}</div>
  <div class="panel"><h2>{U(r'\u5e93\u5b58\u63d0\u9192')}</h2>{self.bullets([U(r'\u6ede\u9500\u548c\u5c3a\u7801\u7ed3\u6784\u5206\u6790\u5c06\u4ece SAP B1 \u7ee7\u7eed\u8865\u5145\u3002'), U(r'\u5f53\u524d\u5148\u7528\u5e93\u5b58\u91d1\u989d\u548c\u98ce\u9669\u6570\u91cf\u505a\u95e8\u5e97\u9884\u8b66\u3002')])}</div>
</div>"""
        self.out(layout(U(r"AI \u5e97\u957f"), body, user=user, wide=True))

    def knowledge(self, user):
        user = self.require_login(user)
        if not user:
            return
        cats = [
            (U(r"\u516c\u53f8\u5236\u5ea6"), "/wiki/firefox-hq/company-architecture"),
            ("SOP", "/wiki/firefox-hq/operations"),
            (U(r"\u54c1\u724c"), "/wiki/firefox-hq/brands"),
            (U(r"\u4ea7\u54c1"), "/wiki/firefox-hq/supply-chain"),
            (U(r"\u57f9\u8bad"), "/wiki/firefox-hq/tasks"),
            (U(r"\u5927\u5e97\u9879\u76ee"), "/wiki/firefox-hq/big-store-plan"),
            (U(r"AI \u5f00\u53d1\u6587\u6863"), "/wiki/firefox-hq/company-ai-server-plan"),
            (U(r"\u6587\u4ef6\u4e0a\u4f20"), "/upload"),
            (U(r"\u5916\u7f51\u641c\u7d22"), "/web-search"),
            (U(r"AI \u52a9\u624b"), "/ai-assistant"),
        ]
        pills = "".join('<a class="pill" href="{}">{}</a>'.format(esc(href), esc(name)) for name, href in cats)
        body = f"""
<div class="panel">
  <h2>{U(r'\u706b\u72d0\u72f8 AI \u4f01\u4e1a\u77e5\u8bc6\u5e93')}</h2>
  <p class="small">{U(r'\u6309\u7ecf\u8425\u573a\u666f\u5206\u7c7b\uff0c\u65b9\u4fbf\u5458\u5de5\u624b\u673a\u6253\u5f00\u3001\u641c\u7d22\u548c\u5b66\u4e60\u3002')}</p>
  <div>{pills}</div>
  <form method="get" action="/wiki/search" style="margin-top:14px">
    <label>{U(r'\u5168\u6587\u641c\u7d22')}</label><input name="q" placeholder="{U(r'\u8f93\u5165\u5173\u952e\u8bcd\uff0c\u5982\uff1a\u85aa\u916c\u3001\u5357\u5c71\u3001SAP B1')}">
    <p><button>{U(r'\u641c\u7d22\u77e5\u8bc6\u5e93')}</button></p>
  </form>
</div>"""
        self.out(layout(U(r"\u706b\u72d0\u72f8 AI \u4f01\u4e1a\u77e5\u8bc6\u5e93"), body, user=user))

    def inventory(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_open(user, ("boss", "admin", "store_manager", "purchasing", "finance")):
            return self.dashboard(user)
        summary = load_summary()
        body = f"""
<div class="panel">
  <h2>{U(r'\u5e93\u5b58\u5206\u6790')}</h2>
  <div class="metrics">
    {self.metric(U(r'\u5e93\u5b58\u91d1\u989d'), U(r'\uffe5') + money(summary.get('inventory_amount')), U(r'SAP B1'))}
    {self.metric(U(r'\u98ce\u9669\u6570\u91cf'), money(summary.get('risk_count')), U(r'\u9700\u8ddf\u8fdb'))}
    {self.metric(U(r'\u6570\u636e\u65e5\u671f'), summary.get('data_date'), U(r'\u6bcf\u65e5 2:00'))}
  </div>
  <p><a class="btn dark" href="/wiki/firefox-hq/sap-b1">{U(r'\u67e5\u770b SAP B1 \u540c\u6b65\u8bf4\u660e')}</a></p>
</div>"""
        self.out(layout(U(r"\u5e93\u5b58\u5206\u6790"), body, user=user, wide=True))

    def change_password(self, user, msg=""):
        if not user:
            return self.redir("/login")
        body = f"""
<div class="panel form">
  <form method="post" action="/change-password">
    <label>{U(r'\u539f\u5bc6\u7801')}</label><input name="old_password" type="password" required>
    <label>{T['new_password']}</label><input name="new_password" type="password" required>
    <p><button>{T['save']}</button></p>
  </form>
</div>"""
        self.out(layout(T["change_password"], body, user=user, msg=msg))

    def change_password_post(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        form = self.form()
        if not cp(form.get("old_password", ""), user["password_hash"]):
            return self.change_password(user, U(r"\u539f\u5bc6\u7801\u4e0d\u6b63\u786e\u3002"))
        with db() as conn:
            conn.execute(
                "update users set password_hash=?, reset_required=0, updated_at=? where id=?",
                (hp(form.get("new_password", "")), int(time.time()), user["id"]),
            )
        return self.change_password(user, T["password_changed"])

    def role_select(self, value):
        return '<select name="role">' + "".join(
            '<option value="{}"{}>{}</option>'.format(k, " selected" if value == k else "", esc(v)) for k, v in ROLES.items()
        ) + "</select>"

    def status_select(self, value):
        return '<select name="status">' + "".join(
            '<option value="{}"{}>{}</option>'.format(k, " selected" if value == k else "", esc(v)) for k, v in STATUS.items()
        ) + "</select>"

    def admin(self, msg=""):
        user = self.require_admin()
        if not user:
            return
        with db() as conn:
            rows = conn.execute("select * from users order by status='pending' desc, created_at desc").fetchall()
        body = f'<div class="panel"><h2>{T["users"]}</h2><p class="small">{U(r"\u65b0\u5458\u5de5\u6ce8\u518c\u540e\u9ed8\u8ba4\u4e3a\u5f85\u5ba1\u6838\u3002\u7ba1\u7406\u5458\u53ef\u4ee5\u5ba1\u6838\u901a\u8fc7\u3001\u7981\u7528\u8d26\u53f7\u3001\u4fee\u6539\u89d2\u8272\u548c\u91cd\u7f6e\u5bc6\u7801\u3002")}</p><table><thead><tr><th>{T["name"]}</th><th>{T["email"]}</th><th>{T["phone"]}</th><th>{T["store"]}</th><th>{T["role"]}</th><th>{T["status"]}</th><th>{T["action"]}</th></tr></thead><tbody>'
        for row in rows:
            update = (
                '<form method="post" action="/admin/update">'
                f'<input type="hidden" name="id" value="{row["id"]}">'
                f'{self.role_select(row["role"])}{self.status_select(row["status"])}'
                f'<button>{T["save"]}</button></form>'
            )
            reset = (
                '<form method="post" action="/admin/reset-password">'
                f'<input type="hidden" name="id" value="{row["id"]}">'
                f'<input name="new_password" type="text" placeholder="{T["new_password"]}" required>'
                f'<button class="gray">{T["reset"]}</button></form>'
            )
            body += "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td><div class=\"inline\">{}{}</div></td></tr>".format(
                esc(row["name"]),
                esc(row["email"]),
                esc(row["phone"]),
                esc(row["store"]),
                esc(ROLES.get(row["role"], row["role"])),
                esc(STATUS.get(row["status"], row["status"])),
                update,
                reset,
            )
        body += "</tbody></table></div>"
        self.out(layout(T["admin"], body, user=user, msg=msg, wide=True))

    def admin_update(self):
        user = self.require_admin()
        if not user:
            return
        form = self.form()
        role = form.get("role", "employee") if form.get("role") in ROLES else "employee"
        status = form.get("status", "pending") if form.get("status") in STATUS else "pending"
        with db() as conn:
            conn.execute("update users set role=?, status=?, updated_at=? where id=?", (role, status, int(time.time()), form.get("id")))
        return self.redir("/admin")

    def admin_reset_password(self):
        user = self.require_admin()
        if not user:
            return
        form = self.form()
        new_password = form.get("new_password", "")
        if len(new_password) < 6:
            return self.admin(U(r"\u65b0\u5bc6\u7801\u81f3\u5c11 6 \u4f4d\u3002"))
        with db() as conn:
            conn.execute(
                "update users set password_hash=?, failed_attempts=0, locked_until=0, reset_required=1, updated_at=? where id=?",
                (hp(new_password), int(time.time()), form.get("id")),
            )
        return self.redir("/admin")

    def dashboard(self, user):
        role = user["role"]
        can_boss = role in ("boss", "admin", "finance", "purchasing")
        can_manager = role in ("boss", "admin", "store_manager", "purchasing", "finance")
        can_admin = role == "admin"
        cards = [
            self.card(U(r"AI \u603b\u7ecf\u7406"), U(r"\u4eca\u5929\u516c\u53f8\u60c5\u51b5\u3001\u98ce\u9669\u63d0\u9192\u3001\u7ecf\u8425\u5efa\u8bae\u3002"), "/ai-ceo", "btn", can_boss),
            self.card(U(r"\u7ecf\u8425\u603b\u89c8"), U(r"\u9500\u552e\u3001\u5229\u6da6\u3001\u5e93\u5b58\u3001\u73b0\u91d1\u6d41\u3002"), "/business-overview", "btn dark", can_boss),
            self.card(U(r"\u95e8\u5e97\u4e2d\u5fc3"), U(r"\u5357\u5c71\u5e97\u3001\u632f\u5174\u5e97\u3001\u822a\u82d1\u5e97\u7b49\u95e8\u5e97\u6863\u6848\u3002"), "/stores", "btn green", can_manager),
            self.card(U(r"\u5458\u5de5\u4e2d\u5fc3"), U(r"\u5458\u5de5\u4fe1\u606f\u3001\u9500\u552e\u3001\u6536\u5165\u3001\u6210\u957f\u8bb0\u5f55\u3002"), "/employees", "btn green", can_manager),
            self.card(U(r"\u54c1\u724c\u4e2d\u5fc3"), U(r"KAILAS\u3001Mammut\u3001OSPREY\u3001Deuter \u7b49\u54c1\u724c\u6863\u6848\u3002"), "/brands", "btn", role in ("boss", "admin", "purchasing", "store_manager")),
            self.card(U(r"\u4ea7\u54c1\u4e2d\u5fc3"), U(r"\u4ea7\u54c1\u8bf4\u660e\u3001\u5e93\u5b58\u3001\u9500\u552e\u5386\u53f2\u3001AI \u8bdd\u672f\u3002"), "/products", "btn", True),
            self.card(U(r"\u4f9b\u5e94\u5546\u4e2d\u5fc3"), U(r"\u5408\u540c\u3001\u4ed8\u6b3e\u3001\u4f9b\u8d27\u8bb0\u5f55\u3002"), "/suppliers", "btn orange", role in ("boss", "admin", "purchasing", "finance")),
            self.card(U(r"\u987e\u5ba2\u4e2d\u5fc3"), U(r"\u6d88\u8d39\u8bb0\u5f55\u3001\u6807\u7b7e\u3001\u4f1a\u5458\u8d21\u732e\u3002"), "/members", "btn green", True),
            self.card(U(r"\u5e93\u5b58\u91c7\u8d2d"), U(r"\u5e93\u5b58\u98ce\u9669\u3001\u91c7\u8d2d\u9884\u8b66\u3001SAP B1 \u6458\u8981\u3002"), "/inventory", "btn dark", can_manager),
            self.card(U(r"\u8d22\u52a1\u4e2d\u5fc3"), U(r"\u8d44\u91d1\u3001\u4ed8\u6b3e\u3001\u8d39\u7528\u3001\u5229\u6da6\u5206\u6790\u3002"), "/finance", "btn dark", role in ("boss", "admin", "finance")),
            self.card(U(r"\u5185\u5bb9\u4e2d\u5fc3"), U(r"\u516c\u4f17\u53f7\u3001\u89c6\u9891\u53f7\u3001\u5c0f\u7ea2\u4e66\u3001\u6296\u97f3\u7b49\u5185\u5bb9\u6846\u67b6\u3002"), "/content-center", "btn orange", True),
            self.card(U(r"\u77e5\u8bc6\u4e2d\u5fc3"), U(r"\u6587\u6863\u3001\u5408\u540c\u3001\u4f1a\u8bae\u7eaa\u8981\u3001AI \u95ee\u7b54\u7684\u77e5\u8bc6\u5165\u53e3\u3002"), "/knowledge", "btn red", True),
            self.card(U(r"AI \u667a\u80fd\u4f53"), U(r"AI CEO\u3001AI CFO\u3001AI \u91c7\u8d2d\u3001AI \u5e93\u5b58\u7b49\u667a\u80fd\u4f53\u77e9\u9635\u3002"), "/agents", "btn", True),
            self.card(U(r"\u5de5\u4f5c\u6d41"), U(r"\u91c7\u8d2d\u3001\u4ed8\u6b3e\u3001\u5408\u540c\u3001\u8bf7\u5047\u3001\u5185\u5bb9\u5ba1\u6838\u6d41\u7a0b\u9884\u7559\u3002"), "/workflow", "btn", True),
            self.card(U(r"\u7cfb\u7edf\u7ba1\u7406"), U(r"\u8d26\u53f7\u3001\u6743\u9650\u3001\u5ba1\u6838\u548c\u91cd\u7f6e\u5bc6\u7801\u3002"), "/admin", "btn dark", can_admin),
        ]
        info = '<div class="panel"><strong>{}</strong><p class="small">{}：{} ｜ {}：{} ｜ {}：{}</p></div>'.format(
            U(r"\u5f53\u524d\u8d26\u53f7"), T["name"], esc(user["name"]), T["store"], esc(user["store"]), T["role"], esc(ROLES.get(role, role))
        )
        self.out(layout(T["brand"], '<div class="grid">' + "".join(cards) + "</div>" + info, user=user, wide=True))

    def module_page(self, user, path):
        user = self.require_login(user)
        if not user:
            return
        module = module_key(path)
        title, text, roles = MODULES[path]
        if not self.can_open(user, roles):
            return self.dashboard(user)
        q = parse_qs(urlparse(self.path).query).get("q", [""])[0].strip()
        sql = "select * from records where module=? and status!='deleted'"
        params = [module]
        if q:
            like = "%" + q + "%"
            sql += " and (title like ? or tags like ? or summary like ? or data_json like ?)"
            params += [like, like, like, like]
        sql += " order by updated_at desc limit 100"
        with db() as conn:
            rows = conn.execute(sql, params).fetchall()
        field_html = "".join('<span class="pill">{}</span>'.format(esc(f)) for f in ARCHIVE_FIELDS.get(module, []))
        row_html = ""
        for row in rows:
            row_html += "<tr><td>{}</td><td>{}</td><td>{}</td><td><a href=\"/records/view?id={}\">{}</a> <a href=\"/records/edit?id={}\">{}</a></td></tr>".format(
                esc(row["title"]), esc(row["tags"]), esc(dt(row["updated_at"])), row["id"], U(r"\u8be6\u60c5"), row["id"], U(r"\u7f16\u8f91")
            )
        if not row_html:
            row_html = '<tr><td colspan="4" class="small">{}</td></tr>'.format(U(r"\u6682\u65e0\u6863\u6848\uff0c\u53ef\u4ee5\u5148\u65b0\u5efa\u4e00\u6761\u3002"))
        abilities = [U(r"\u65b0\u5efa"), U(r"\u7f16\u8f91"), U(r"\u5220\u9664"), U(r"\u8be6\u60c5\u9875"), U(r"\u641c\u7d22"), U(r"\u6807\u7b7e"), U(r"\u5907\u6ce8"), U(r"\u65f6\u95f4\u8f74"), U(r"\u5173\u8054\u5bf9\u8c61"), U(r"\u9644\u4ef6"), U(r"\u56fe\u7247/PDF/Word/Excel/\u89c6\u9891\u4e0a\u4f20"), U(r"AI \u67e5\u8be2\u9884\u7559")]
        body = f"""
<div class="panel">
  <h2>{esc(title)}</h2><p>{esc(text)}</p>
  <div class="inline"><a class="btn" href="/records/new?module={esc(module)}">{U(r'\u65b0\u5efa')}</a><a class="btn green" href="/records/export?module={esc(module)}">{U(r'Excel \u5bfc\u51fa')}</a><a class="btn orange" href="/upload">{U(r'\u4e0a\u4f20\u9644\u4ef6')}</a><a class="btn gray" href="/ai-query">{U(r'AI \u67e5\u8be2')}</a></div>
</div>
<div class="panel"><h2>{U(r'\u5b57\u6bb5\u89c4\u5212')}</h2><div>{field_html}</div></div>
<div class="panel">
  <form method="get" action="/{esc(module)}"><label>{U(r'\u641c\u7d22')}</label><input name="q" value="{esc(q)}" placeholder="{U(r'\u641c\u7d22\u540d\u79f0\u3001\u6807\u7b7e\u3001\u5185\u5bb9')}"><p><button>{U(r'\u641c\u7d22')}</button></p></form>
  <table><thead><tr><th>{U(r'\u540d\u79f0')}</th><th>{U(r'\u6807\u7b7e')}</th><th>{U(r'\u66f4\u65b0')}</th><th>{T['action']}</th></tr></thead><tbody>{row_html}</tbody></table>
</div>
<div class="panel"><h2>{U(r'\u7edf\u4e00\u6863\u6848\u80fd\u529b')}</h2>{self.bullets(abilities)}</div>"""
        self.out(layout(title, body, user=user, wide=True))

    def document_center(self, user):
        user = self.require_login(user)
        if not user:
            return
        with db() as conn:
            files = conn.execute("select * from uploaded_files order by created_at desc limit 80").fetchall()
        rows = "".join("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(esc(f["original_name"]), esc(f["category"]), esc(f["mime"]), esc(dt(f["created_at"]))) for f in files)
        if not rows:
            rows = '<tr><td colspan="4" class="small">{}</td></tr>'.format(U(r"\u6682\u65e0\u6587\u4ef6\uff0c\u8bf7\u5148\u4e0a\u4f20\u3002"))
        features = [U(r"\u4e0a\u4f20"), U(r"\u6587\u4ef6\u5217\u8868"), U(r"\u6587\u4ef6\u8be6\u60c5"), U(r"\u5173\u8054\u5bf9\u8c61"), U(r"\u6807\u7b7e"), U(r"OCR \u9884\u7559"), U(r"\u81ea\u52a8\u6458\u8981"), U(r"\u5411\u91cf\u5316\u9884\u7559"), U(r"AI Q&A")]
        body = f"<div class='panel'><h2>{U(r'\u7edf\u4e00\u6587\u4ef6\u4e2d\u5fc3')}</h2><p><a class='btn' href='/upload'>{U(r'\u4e0a\u4f20\u6587\u4ef6')}</a></p>{self.bullets(features)}</div><div class='panel'><table><thead><tr><th>{U(r'\u6587\u4ef6')}</th><th>{U(r'\u5206\u7c7b')}</th><th>{U(r'\u7c7b\u578b')}</th><th>{U(r'\u65f6\u95f4')}</th></tr></thead><tbody>{rows}</tbody></table></div>"
        self.out(layout(U(r"\u7edf\u4e00\u6587\u4ef6\u4e2d\u5fc3"), body, user=user, wide=True))

    def workflow_center(self, user):
        user = self.require_login(user)
        if not user:
            return
        flows = [U(r"\u91c7\u8d2d\u5ba1\u6279"), U(r"\u4ed8\u6b3e\u5ba1\u6279"), U(r"\u5408\u540c\u5ba1\u6279"), U(r"\u8bf7\u5047\u5ba1\u6279"), U(r"\u62db\u8058"), U(r"\u79bb\u804c"), U(r"\u95e8\u5e97\u4efb\u52a1\u5206\u914d"), U(r"\u5185\u5bb9\u5ba1\u6838")]
        cards = "".join(self.card(f, U(r"\u6d41\u7a0b\u5f15\u64ce\u9884\u7559\uff1a\u5ba1\u6279\u8282\u70b9\u3001\u6267\u884c\u4eba\u3001\u65f6\u95f4\u8f74\u3001\u901a\u77e5\u548c\u65e5\u5fd7\u3002"), "/tasks", "btn", True) for f in flows)
        self.out(layout(U(r"\u5de5\u4f5c\u6d41\u4e2d\u5fc3"), '<div class="grid">' + cards + "</div>", user=user, wide=True))

    def sap_api_placeholder(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        mapping = {
            "/api/sap/business-analysis": "business analysis",
            "/api/sap/profit-analysis": "profit analysis",
            "/api/sap/inventory-analysis": "inventory analysis",
            "/api/sap/sales-trend": "sales trend",
            "/api/sap/ai-analysis": "ai analysis",
        }
        return self.json_out({"ok": True, "endpoint": mapping.get(path, "sap placeholder"), "data": load_summary(), "note": "placeholder; existing SAP sync is unchanged"})

    def agents(self, user):
        user = self.require_login(user)
        if not user:
            return
        agent_defs = [
            (U(r"AI CEO / AI \u603b\u7ecf\u7406"), U(r"\u7ecf\u8425\u5224\u65ad\u3001\u98ce\u9669\u9884\u8b66\u3001\u884c\u52a8\u5efa\u8bae")),
            (U(r"AI CFO / AI \u8d22\u52a1\u603b\u76d1"), U(r"\u73b0\u91d1\u6d41\u3001\u8d39\u7528\u3001\u4ed8\u6b3e\u548c\u5229\u6da6\u5206\u6790")),
            (U(r"AI COO / AI \u8fd0\u8425\u603b\u76d1"), U(r"\u95e8\u5e97\u8fd0\u8425\u3001\u4efb\u52a1\u548c SOP \u63a8\u8fdb")),
            (U(r"AI \u91c7\u8d2d\u7ecf\u7406"), U(r"\u91c7\u8d2d\u3001\u8865\u8d27\u3001\u4f9b\u5e94\u5546\u548c\u8d26\u671f")),
            (U(r"AI \u5e93\u5b58\u7ecf\u7406"), U(r"\u5e93\u5b58\u91d1\u989d\u3001\u6ede\u9500\u3001\u8c03\u62e8\u548c\u98ce\u9669")),
            (U(r"AI \u54c1\u724c\u7ecf\u7406"), U(r"\u54c1\u724c\u9500\u552e\u3001\u6bdb\u5229\u3001\u5408\u4f5c\u548c\u672a\u6765\u89c4\u5212")),
            (U(r"AI \u95e8\u5e97\u7ecf\u7406"), U(r"\u95e8\u5e97\u9500\u552e\u3001\u4f1a\u5458\u3001\u5458\u5de5\u548c\u5e93\u5b58")),
            (U(r"AI \u8425\u9500\u7ecf\u7406"), U(r"\u5c0f\u7ea2\u4e66\u3001\u6296\u97f3\u3001\u89c6\u9891\u53f7\u3001\u516c\u4f17\u53f7")),
            (U(r"AI \u57f9\u8bad\u7ecf\u7406"), U(r"\u57f9\u8bad\u8bfe\u7a0b\u3001\u8003\u6838\u548c\u6210\u957f\u8bb0\u5f55")),
            (U(r"AI \u5ba2\u670d"), U(r"\u987e\u5ba2\u95ee\u9898\u3001\u552e\u540e\u548c\u4f1a\u5458\u7ef4\u62a4")),
            (U(r"AI \u79d8\u4e66"), U(r"\u4f1a\u8bae\u7eaa\u8981\u3001\u4efb\u52a1\u5206\u89e3\u548c\u63d0\u9192")),
        ]
        cards = "".join(self.card(name, desc + U(r"\u3002\u72b6\u6001\uff1a\u6846\u67b6\u5df2\u5c31\u7eea\uff0cAPI \u9884\u7559\u3002"), "/ai-query", "btn", True) for name, desc in agent_defs)
        self.out(layout(U(r"AI \u667a\u80fd\u4f53\u4e2d\u5fc3"), '<div class="grid">' + cards + "</div>", user=user, wide=True))

    def knowledge(self, user):
        user = self.require_login(user)
        if not user:
            return
        q = parse_qs(urlparse(self.path).query).get("q", [""])[0].strip()
        source_type = parse_qs(urlparse(self.path).query).get("source_type", [""])[0].strip()
        where = []
        params = []
        if q:
            like = "%" + q + "%"
            where.append("(title like ? or body like ? or summary like ? or keywords like ? or tags like ?)")
            params += [like, like, like, like, like]
        if source_type:
            where.append("source_type=?")
            params.append(source_type)
        sql = "select * from knowledge_items"
        if where:
            sql += " where " + " and ".join(where)
        sql += " order by updated_at desc limit 80"
        with db() as conn:
            all_rows = conn.execute(sql, params).fetchall()
            total = conn.execute("select count(*) c from knowledge_items").fetchone()["c"]
            waiting = conn.execute("select count(*) c from knowledge_items where status in ('uploaded','draft','summarized')").fetchone()["c"]
            ready = conn.execute("select count(*) c from knowledge_items where status in ('ready','parsed')").fetchone()["c"]
            failed = conn.execute("select count(*) c from knowledge_items where status='failed'").fetchone()["c"]
            by_source = conn.execute("select coalesce(source_type,'unknown') name, count(*) c from knowledge_items group by source_type order by c desc limit 8").fetchall()
        rows = [r for r in all_rows if self.can_view_knowledge(user, r)]
        cards = "".join(
            "<div class='card'><div><h2>{}</h2><p>{}</p><p class='small'>{} · {} · {}</p></div><a class='btn full' href='/knowledge/view?id={}'>{}</a></div>".format(
                esc(row["title"]),
                esc((row["summary"] or row["ai_summary"] or U(r"\u7b49\u5f85 AI \u6458\u8981\u751f\u6210"))[:180]),
                esc(row["source_type"]),
                esc(self.knowledge_status_text(row)),
                esc(row["tags"]),
                row["id"],
                U(r"\u67e5\u770b"),
            )
            for row in rows
        )
        if not cards:
            cards = "<div class='panel'><p class='small'>{}</p></div>".format(U(r"\u6682\u65e0\u77e5\u8bc6\u6761\u76ee\uff0c\u53ef\u4ee5\u5148\u4e0a\u4f20\u6587\u4ef6\u6216\u65b0\u5efa\u77e5\u8bc6\u3002"))
        source_pills = "".join('<span class="pill">{} {}</span>'.format(esc(r["name"]), r["c"]) for r in by_source)
        body = f"""
<div class="panel">
  <h2>{U(r'\u77e5\u8bc6\u5f15\u64ce\u4e2d\u5fc3')}</h2>
  <p class="small">{U(r'\u8fd9\u91cc\u662f FoxBrain \u7684\u4f01\u4e1a\u957f\u671f\u8bb0\u5fc6\uff1a\u6587\u6863\u3001\u5236\u5ea6\u3001\u5408\u540c\u3001SAP \u6458\u8981\u3001\u57f9\u8bad\u548c AI \u95ee\u7b54\u90fd\u4f1a\u6c89\u6dc0\u5230\u8fd9\u91cc\u3002')}</p>
  <div class="inline"><a class="btn" href="/upload">{U(r'\u4e0a\u4f20\u6587\u4ef6')}</a><a class="btn green" href="/knowledge/new">{U(r'\u65b0\u5efa\u77e5\u8bc6')}</a><a class="btn dark" href="/ai-query">{U(r'AI \u67e5\u8be2')}</a><a class="btn orange" href="/web-search">{U(r'\u5916\u7f51\u4fdd\u5b58')}</a></div>
</div>
<div class="metrics">
  {self.metric(U(r'\u77e5\u8bc6\u603b\u6570'), total, U(r'\u5168\u90e8\u6761\u76ee'))}
  {self.metric(U(r'\u7b49\u5f85\u5904\u7406'), waiting, U(r'\u89e3\u6790/\u6458\u8981/\u5411\u91cf'))}
  {self.metric(U(r'\u53ef AI \u67e5\u8be2'), ready, U(r'\u5df2\u89e3\u6790\u6216\u5c31\u7eea'))}
  {self.metric(U(r'\u5904\u7406\u5931\u8d25'), failed, U(r'\u9700\u4eba\u5de5\u590d\u6838'))}
</div>
<div class="panel">
  <form method="get" action="/knowledge">
    <label>{U(r'\u77e5\u8bc6\u641c\u7d22')}</label><input name="q" value="{esc(q)}" placeholder="{U(r'\u641c\u7d22\u6807\u9898\u3001\u6b63\u6587\u3001\u6458\u8981\u3001\u5173\u952e\u8bcd\u3001\u6807\u7b7e')}">
    <label>{U(r'\u6765\u6e90\u7c7b\u578b')}</label><input name="source_type" value="{esc(source_type)}" placeholder="document / note / web / sap_report">
    <p><button>{U(r'\u641c\u7d22')}</button></p>
  </form>
  <div>{source_pills}</div>
</div>
<div class="grid">{cards}</div>"""
        self.out(layout(U(r"\u77e5\u8bc6\u5f15\u64ce\u4e2d\u5fc3"), body, user=user, wide=True))

    def knowledge_view(self, user):
        user = self.require_login(user)
        if not user:
            return
        kid = parse_qs(urlparse(self.path).query).get("id", [""])[0]
        with db() as conn:
            row = conn.execute("select * from knowledge_items where id=?", (kid,)).fetchone()
            chunks = conn.execute("select * from knowledge_chunks where knowledge_id=? order by chunk_index limit 8", (kid,)).fetchall()
        if not row or not self.can_view_knowledge(user, row):
            return self.redir("/knowledge")
        chunk_rows = "".join(
            "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(c["chunk_index"] + 1, esc(c["embedding_status"]), esc(summarize_text(c["chunk_text"], 90)))
            for c in chunks
        )
        if not chunk_rows:
            chunk_rows = '<tr><td colspan="3" class="small">{}</td></tr>'.format(U(r"\u6682\u65e0\u5207\u7247\uff1a\u6587\u4ef6\u8fd8\u5728\u7b49\u5f85\u89e3\u6790\uff0c\u6216\u6ca1\u6709\u63d0\u53d6\u5230\u53ef\u7528\u6587\u672c\u3002"))
        summary_text = row["summary"] or row["ai_summary"] or U(r"\u7b49\u5f85 AI \u6458\u8981\u751f\u6210")
        pipeline = [
            U(r"\u5143\u6570\u636e\u5df2\u4fdd\u5b58"),
            self.knowledge_status_text(row),
            U(r"\u5173\u952e\u8bcd\uff1a") + (row["keywords"] or row["tags"] or ""),
            U(r"\u5411\u91cf\u5316\u72b6\u6001\uff1a") + (row["embedding_status"] or "pending"),
            U(r"\u53ef\u89c1\u8303\u56f4\uff1a") + (row["visibility"] or "public_internal"),
        ]
        relation_text = ""
        if row["object_type"]:
            relation_text = f"{row['object_type']} #{row['object_id'] or ''}"
        body = f"""
<div class="panel">
  <h2>{esc(row['title'])}</h2>
  <p class="small">{esc(row['knowledge_id'] or ('KB-' + str(row['id'])))} · {esc(row['category'])} · {esc(row['source_type'])} · {esc(row['source_ref'])}</p>
  <div class="inline"><span class="pill">{esc(self.knowledge_status_text(row))}</span><span class="pill">{esc(row['visibility'])}</span><span class="pill">{esc(row['embedding_status'])}</span></div>
  <h2>{U(r'\u6458\u8981')}</h2><p>{esc(summary_text)}</p>
  <h2>{U(r'\u77e5\u8bc6\u7ba1\u7ebf')}</h2>{self.bullets(pipeline)}
  <h2>{U(r'\u5173\u8054\u5bf9\u8c61')}</h2><p>{esc(relation_text or U(r'\u6682\u65e0\u5173\u8054\u5bf9\u8c61'))}</p>
  <h2>{U(r'\u6b63\u6587')}</h2><p>{esc(row['body'])}</p>
  <p><a class="btn" href="/ai-query">{U(r'\u7528 AI \u67e5\u8be2')}</a> <a class="btn gray" href="/knowledge">{U(r'\u8fd4\u56de')}</a></p>
</div>
<div class="panel"><h2>{U(r'\u6587\u6863\u5207\u7247')}</h2><table><thead><tr><th>#</th><th>{U(r'\u5411\u91cf\u72b6\u6001')}</th><th>{U(r'\u7247\u6bb5')}</th></tr></thead><tbody>{chunk_rows}</tbody></table></div>"""
        self.out(layout(row["title"], body, user=user, wide=True))

    def ai_assistant(self, user, answer_data=None, question="", refs=None):
        user = self.require_login(user)
        if not user:
            return
        answer_data = answer_data or self.build_ai_answer("", "all", [])
        citations = answer_data.get("cited_documents", [])
        citation_html = "".join(
            "<li><a href='{}'>{}</a> <span class='small'>{} · {}</span></li>".format(esc(c["url"]), esc(c["title"]), esc(c["knowledge_id"]), esc(c["status"]))
            for c in citations
        )
        if not citation_html:
            citation_html = "<li>{}</li>".format(U(r"\u6682\u65e0\u5f15\u7528\u6765\u6e90\u3002"))
        limits = self.bullets(answer_data.get("limitations", []))
        examples = [
            U(r"\u5357\u5c71\u5e97\u79df\u8d41\u5408\u540c\u5728\u54ea\u91cc\uff1f"),
            U(r"KAILAS \u57f9\u8bad\u8d44\u6599\u6709\u54ea\u4e9b\uff1f"),
            U(r"Osprey \u5e93\u5b58\u5206\u6790\u6709\u6ca1\u6709\u8d44\u6599\uff1f"),
            U(r"\u6700\u8fd1 30 \u5929\u54ea\u4e9b\u95e8\u5e97\u9700\u8981\u5173\u6ce8\uff1f"),
        ]
        scope_opts = "".join("<option value='{}'>{}</option>".format(k, esc(v)) for k, v in {
            "all": U(r"\u5168\u516c\u53f8"),
            "stores": U(r"\u95e8\u5e97"),
            "employees": U(r"\u5458\u5de5"),
            "brands": U(r"\u54c1\u724c"),
            "products": U(r"\u4ea7\u54c1"),
            "suppliers": U(r"\u4f9b\u5e94\u5546"),
            "members": U(r"\u987e\u5ba2"),
            "documents": U(r"\u6587\u4ef6"),
            "sap": "SAP",
        }.items())
        body = f"""
<div class="panel form">
  <h2>{U(r'AI \u67e5\u8be2\u4e2d\u5fc3 V1')}</h2>
  <p class="small">{U(r'\u5f53\u524d\u7248\u672c\u5148\u505a\u77e5\u8bc6\u68c0\u7d22\u3001\u5f15\u7528\u7ed3\u6784\u548c\u5386\u53f2\u7559\u75d5\uff0c\u4e0d\u7f16\u9020\u7ecf\u8425\u7ed3\u8bba\u3002')}</p>
  <form method="post" action="/ai-query">
    <label>{U(r'\u95ee\u9898')}</label><textarea name="question" required>{esc(question)}</textarea>
    <label>{U(r'\u8303\u56f4')}</label><select name="scope">{scope_opts}</select>
    <label>{U(r'\u5173\u8054\u5bf9\u8c61')}</label><input name="related_object" placeholder="stores:1 / brands:2 / documents">
    <p><button>{U(r'\u63d0\u95ee')}</button></p>
  </form>
  <h2>{U(r'\u793a\u4f8b\u95ee\u9898')}</h2>{self.bullets(examples)}
</div>
<div class="panel">
  <h2>{U(r'AI \u56de\u7b54')}</h2><p>{esc(answer_data.get('answer'))}</p>
  <p class="small">{U(r'\u7f6e\u4fe1\u72b6\u6001')}：{esc(answer_data.get('confidence'))} · {U(r'\u6a21\u578b')}：{esc(answer_data.get('model_name'))}</p>
  <h2>{U(r'\u5f15\u7528\u6765\u6e90')}</h2><ul class="list">{citation_html}</ul>
  <h2>{U(r'\u5c40\u9650\u8bf4\u660e')}</h2>{limits}
</div>"""
        self.out(layout(U(r"AI \u67e5\u8be2\u4e2d\u5fc3"), body, user=user, wide=True))

    def ai_assistant_post(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        form = self.form()
        question = form.get("question", "").strip()
        scope = form.get("scope", "all")
        terms = [w for w in re.split(r"\s+", question) if w][:6]
        rows = []
        with db() as conn:
            for term in terms or [question]:
                like = "%" + term + "%"
                hit_rows = conn.execute(
                    "select * from knowledge_items where title like ? or body like ? or summary like ? or keywords like ? or tags like ? order by updated_at desc limit 10",
                    (like, like, like, like, like),
                ).fetchall()
                rows.extend([r for r in hit_rows if self.can_view_knowledge(user, r)])
            seen = {}
            for row in rows:
                seen[row["id"]] = row
            rows = list(seen.values())[:10]
            answer_data = self.build_ai_answer(question, scope, rows)
            conn.execute(
                "insert into knowledge_query_history(user_id,question,scope,related_object_type,related_object_id,answer_json,created_at) values(?,?,?,?,?,?,?)",
                (user["id"], question, scope, "", None, json.dumps(answer_data, ensure_ascii=False), ts()),
            )
        self.log_action(user, "ai_query", "knowledge", None, question)
        return self.ai_assistant(user, answer_data, question)

    def api_knowledge_get(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if path in ("/api/knowledge", "/api/knowledge/search"):
            query = parse_qs(urlparse(self.path).query)
            q = query.get("q", [""])[0].strip()
            params = []
            sql = "select * from knowledge_items"
            if q:
                like = "%" + q + "%"
                sql += " where title like ? or body like ? or summary like ? or keywords like ? or tags like ?"
                params = [like, like, like, like, like]
            sql += " order by updated_at desc limit 100"
            with db() as conn:
                rows = [r for r in conn.execute(sql, params).fetchall() if self.can_view_knowledge(user, r)]
            return self.json_out({"ok": True, "items": [self.knowledge_to_json(r, include_body=False) for r in rows]})
        if path == "/api/knowledge/chunks":
            kid = parse_qs(urlparse(self.path).query).get("knowledge_id", [""])[0]
            with db() as conn:
                row = conn.execute("select * from knowledge_items where id=?", (kid,)).fetchone()
                chunks = conn.execute("select * from knowledge_chunks where knowledge_id=? order by chunk_index", (kid,)).fetchall()
            if not row or not self.can_view_knowledge(user, row):
                return self.json_out({"ok": False, "message": "not found"}, code=404)
            return self.json_out({"ok": True, "chunks": [row_dict(c) for c in chunks]})
        if path == "/api/knowledge/query-history":
            with db() as conn:
                rows = conn.execute("select * from knowledge_query_history where user_id=? order by created_at desc limit 50", (user["id"],)).fetchall()
            return self.json_out({"ok": True, "history": [row_dict(r) for r in rows]})
        m = re.match(r"^/api/knowledge/(\d+)$", path)
        if m:
            with db() as conn:
                row = conn.execute("select * from knowledge_items where id=?", (m.group(1),)).fetchone()
            if not row or not self.can_view_knowledge(user, row):
                return self.json_out({"ok": False, "message": "not found"}, code=404)
            return self.json_out({"ok": True, "item": self.knowledge_to_json(row)})
        return self.json_out({"ok": False, "message": "unknown knowledge api"}, code=404)

    def api_knowledge_post(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if path in ("/api/knowledge", "/api/knowledge/from-document"):
            form = self.form()
            title = form.get("title", "").strip() or U(r"\u672a\u547d\u540d\u77e5\u8bc6")
            content = form.get("content", "").strip()
            visibility = form.get("visibility", "public_internal")
            if visibility not in ("public_internal", "manager_only", "finance_only", "owner_only", "restricted"):
                visibility = "public_internal"
            now = ts()
            with db() as conn:
                cur = conn.execute(
                    """insert into knowledge_items(
 title,category,tags,body,ai_summary,source_type,source_ref,created_by,created_at,updated_at,
 knowledge_id,source_id,object_type,object_id,summary,keywords,status,visibility,auto_tags,manual_tags,embedding_status
) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        title,
                        form.get("category", "").strip() or classify_text(content),
                        form.get("tags", "").strip() or extract_tags(content),
                        content,
                        summarize_text(content) if content else U(r"\u7b49\u5f85 AI \u6458\u8981\u751f\u6210"),
                        form.get("source_type", "note"),
                        form.get("source_ref", ""),
                        user["id"],
                        now,
                        now,
                        "KB-" + uuid.uuid4().hex[:12],
                        form.get("source_id", ""),
                        module_key(form.get("object_type", "")),
                        int(form.get("object_id")) if str(form.get("object_id", "")).isdigit() else None,
                        summarize_text(content),
                        form.get("keywords", "").strip() or extract_tags(content),
                        "ready" if content else "draft",
                        visibility,
                        extract_tags(content),
                        form.get("manual_tags", ""),
                        "pending",
                    ),
                )
                kid = cur.lastrowid
                self.create_chunks(conn, kid, None, content, now)
            return self.json_out({"ok": True, "item": {"id": kid, "url": f"/knowledge/view?id={kid}"}})
        if path == "/api/knowledge/query":
            form = self.form()
            question = form.get("question", "").strip()
            scope = form.get("scope", "all")
            terms = [w for w in re.split(r"\s+", question) if w][:6]
            rows = []
            with db() as conn:
                for term in terms or [question]:
                    like = "%" + term + "%"
                    rows.extend(conn.execute("select * from knowledge_items where title like ? or body like ? or summary like ? or keywords like ? or tags like ? limit 10", (like, like, like, like, like)).fetchall())
                rows = [r for r in rows if self.can_view_knowledge(user, r)]
                answer_data = self.build_ai_answer(question, scope, rows)
                conn.execute("insert into knowledge_query_history(user_id,question,scope,answer_json,created_at) values(?,?,?,?,?)", (user["id"], question, scope, json.dumps(answer_data, ensure_ascii=False), ts()))
            return self.json_out({"ok": True, "result": answer_data})
        return self.json_out({"ok": False, "message": "unknown knowledge api"}, code=404)

    def empty_state(self, text):
        return "<p class='small'>{}</p>".format(esc(text))

    def cockpit_data(self):
        s = load_summary()
        has_sales = bool(float(s.get("month_sales") or 0) or float(s.get("yesterday_sales") or 0))
        empty = U(r"\u7b49\u5f85 SAP B1 \u6570\u636e\u540c\u6b65\u540e\u751f\u6210\u7ecf\u8425\u5206\u6790\u3002")
        return {
            "has_data": has_sales,
            "summary": s,
            "empty_message": empty,
            "metrics": {
                "today_sales": s.get("today_sales") or 0,
                "yesterday_sales": s.get("yesterday_sales") or 0,
                "month_sales": s.get("month_sales") or 0,
                "completion_rate": s.get("completion_rate") or 0,
                "gross_profit": s.get("month_gross_profit") or 0,
                "gross_margin": s.get("yesterday_gross_margin") or 0,
                "inventory_amount": s.get("inventory_amount") or 0,
                "risk_count": s.get("risk_count") or 0,
                "data_date": s.get("data_date") or "",
            },
            "ai_suggestions": s.get("ai_suggestions", []) or [],
            "todos": s.get("todos", []) or [],
            "top_stores": s.get("top_stores", []) or [],
            "top_brands": s.get("top_brands", []) or [],
        }

    def role_can_manage(self, user):
        return bool(user and user["role"] in ("boss", "admin", "finance", "purchasing", "store_manager"))

    def ai_ceo(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_open(user, ("boss", "admin", "finance", "purchasing")):
            return self.dashboard(user)
        data = self.cockpit_data()
        m = data["metrics"]
        metrics = "".join(
            [
                self.metric(U(r"\u6628\u65e5\u9500\u552e"), U(r"\uffe5") + money(m["yesterday_sales"]), U(r"\u6570\u636e\u65e5\u671f ") + str(m["data_date"])),
                self.metric(U(r"\u672c\u6708\u9500\u552e"), U(r"\uffe5") + money(m["month_sales"]), U(r"\u5b8c\u6210\u7387 ") + pct(m["completion_rate"])),
                self.metric(U(r"\u6bdb\u5229\u60c5\u51b5"), U(r"\uffe5") + money(m["gross_profit"]), U(r"\u6bdb\u5229\u7387 ") + pct(m["gross_margin"])),
                self.metric(U(r"\u5e93\u5b58\u91d1\u989d"), U(r"\uffe5") + money(m["inventory_amount"]), U(r"\u98ce\u9669\u6570\u91cf ") + money(m["risk_count"])),
            ]
        )
        default_wait = [data["empty_message"]]
        with db() as conn:
            memory_rows = conn.execute("select * from memories where status='approved' order by case importance when 'critical' then 0 when 'high' then 1 else 2 end, updated_at desc limit 6").fetchall()
        memory_refs = [m["title"] + " · " + m["memory_type"] for m in memory_rows if self.can_view_memory(user, m)]
        if not memory_refs:
            memory_refs = [U(r"\u6682\u65e0\u5df2\u5ba1\u6838\u8bb0\u5fc6\uff0cAI \u603b\u7ecf\u7406\u5c06\u5728\u51b3\u7b56\u548c\u539f\u5219\u5ba1\u6838\u540e\u5f15\u7528\u3002")]
        risk_items = [
            U(r"\u95e8\u5e97\u5f02\u5e38\uff1a\u7b49\u5f85\u95e8\u5e97\u9500\u552e\u3001\u6bdb\u5229\u548c\u5e93\u5b58\u6570\u636e\u5b8c\u6574\u540e\u5224\u65ad\u3002"),
            U(r"\u54c1\u724c\u5f02\u5e38\uff1a\u7b49\u5f85\u54c1\u724c\u7ef4\u5ea6 SAP \u5206\u6790\u63a5\u5165\u3002"),
            U(r"\u5e93\u5b58\u5f02\u5e38\uff1a\u53ef\u5148\u8fdb\u5165\u5e93\u5b58\u98ce\u9669\u9875\u68c0\u67e5\u3002"),
        ]
        body = f"""
<div class="panel">
  <h2>{U(r'AI \u603b\u7ecf\u7406\u65e5\u62a5')}</h2>
  <p class="small">{U(r'\u8001\u677f\u6bcf\u5929\u6253\u5f00 FoxBrain\uff0c\u5148\u770b\u4eca\u5929\u6700\u9700\u8981\u5173\u6ce8\u7684\u4e8b\u3002')}</p>
  <div class="metrics">{metrics}</div>
</div>
<div class="split">
  <div class="panel"><h2>{U(r'\u4eca\u65e5\u7ecf\u8425\u6458\u8981')}</h2>{self.bullets(data['ai_suggestions'][:5] or default_wait)}</div>
  <div class="panel"><h2>{U(r'\u4eca\u65e5\u98ce\u9669\u63d0\u9192')}</h2>{self.bullets(risk_items)}</div>
</div>
<div class="split">
  <div class="panel"><h2>{U(r'\u4eca\u65e5\u91cd\u70b9\u4efb\u52a1')}</h2>{self.bullets(data['todos'] or [U(r'\u53ef\u4ece AI \u5efa\u8bae\u8f6c\u6210\u4efb\u52a1\uff0c\u5e76\u5206\u914d\u8d23\u4efb\u4eba\u3002')])}<p><a class="btn" href="/tasks">{U(r'\u8fdb\u5165\u4efb\u52a1\u4e2d\u5fc3')}</a></p></div>
  <div class="panel"><h2>{U(r'\u5916\u90e8\u7814\u7a76\u63d0\u9192')}</h2>{self.bullets([U(r'\u7814\u7a76\u5f15\u64ce\u5df2\u9884\u7559\uff0c\u5916\u90e8\u4fe1\u606f\u9700\u5ba1\u6838\u540e\u624d\u80fd\u5165\u5e93\u3002'), U(r'\u672a\u914d\u7f6e\u5916\u90e8\u641c\u7d22 API \u65f6\u4e0d\u81ea\u52a8\u6293\u53d6\u65b0\u95fb\u3002')])}</div>
</div>
<div class="panel"><h2>{U(r'AI \u603b\u7ecf\u7406\u53c2\u8003\u8bb0\u5fc6')}</h2>{self.bullets(memory_refs)}<p><a class="btn" href="/memory">{U(r'\u8fdb\u5165\u8bb0\u5fc6\u4e2d\u5fc3')}</a></p></div>
<div class="panel">
  <h2>{U(r'AI \u5efa\u8bae')}</h2>
  {self.bullets([U(r'\u5148\u5b8c\u5584 SAP B1 \u6bcf\u65e5 2:00 \u540c\u6b65\u7a33\u5b9a\u6027\u3002'), U(r'\u628a Osprey \u4ef7\u683c\u98ce\u9669\u653e\u5165\u4e13\u9898\u8ddf\u8e2a\u3002'), U(r'\u628a\u91cd\u70b9\u7ecf\u8425\u5efa\u8bae\u8f6c\u6210\u4efb\u52a1\uff0c\u907f\u514d\u53ea\u770b\u4e0d\u505a\u3002')])}
  <p><a class="btn dark" href="/business-overview">{U(r'\u6253\u5f00\u7ecf\u8425\u9a7e\u9a76\u8231')}</a></p>
</div>"""
        self.out(layout(U(r"AI \u603b\u7ecf\u7406\u65e5\u62a5"), body, user=user, wide=True))

    def business_overview(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_open(user, ("boss", "admin", "finance", "purchasing")):
            return self.dashboard(user)
        data = self.cockpit_data()
        m = data["metrics"]
        empty = data["empty_message"]
        metrics = "".join(
            [
                self.metric(U(r"\u4eca\u65e5\u9500\u552e"), U(r"\uffe5") + money(m["today_sales"]), U(r"\u5b9e\u65f6\u6570\u636e\u5f85\u63a5\u5165")),
                self.metric(U(r"\u672c\u6708\u9500\u552e"), U(r"\uffe5") + money(m["month_sales"]), pct(m["completion_rate"])),
                self.metric(U(r"\u6bdb\u5229\u60c5\u51b5"), U(r"\uffe5") + money(m["gross_profit"]), pct(m["gross_margin"])),
                self.metric(U(r"\u5e93\u5b58\u91d1\u989d"), U(r"\uffe5") + money(m["inventory_amount"]), U(r"\u98ce\u9669 ") + money(m["risk_count"])),
            ]
        )
        store_cards = "".join(self.card(str(s.get("store", "")), U(r"\u7b49\u5f85\u95e8\u5e97\u8be6\u7ec6\u5206\u6790\u63a5\u5165\u3002"), "/stores/operations", "btn green", True) for s in data["top_stores"][:4])
        brand_cards = "".join(self.card(str(b.get("brand", "")), U(r"\u7b49\u5f85\u54c1\u724c\u9500\u552e\u3001\u6bdb\u5229\u548c\u5e93\u5b58\u5206\u6790\u3002"), "/brands/operations", "btn", True) for b in data["top_brands"][:4])
        body = f"""
<div class="panel"><h2>{U(r'\u7ecf\u8425\u9a7e\u9a76\u8231 V1')}</h2><p class="small">{U(r'\u4e0d\u505a\u5bc6\u96c6 ERP \u62a5\u8868\uff0c\u53ea\u628a\u8001\u677f\u4eca\u5929\u9700\u8981\u770b\u7684\u4e8b\u653e\u5728\u4e00\u5c4f\u3002')}</p><div class="metrics">{metrics}</div></div>
<div class="split">
  <div class="panel"><h2>{U(r'\u95e8\u5e97\u6392\u540d')}</h2>{('<div class="grid">' + store_cards + '</div>') if store_cards else self.empty_state(empty)}<p><a class="btn" href="/stores/operations">{U(r'\u95e8\u5e97\u7ecf\u8425')}</a></p></div>
  <div class="panel"><h2>{U(r'\u54c1\u724c\u6392\u540d')}</h2>{('<div class="grid">' + brand_cards + '</div>') if brand_cards else self.empty_state(empty)}<p><a class="btn" href="/brands/operations">{U(r'\u54c1\u724c\u7ecf\u8425')}</a></p></div>
</div>
<div class="split">
  <div class="panel"><h2>{U(r'\u5f02\u5e38\u63d0\u9192')}</h2>{self.bullets([U(r'\u5e93\u5b58\u98ce\u9669\u8bf7\u8fdb\u5165\u5e93\u5b58\u98ce\u9669\u9875\u8ddf\u8fdb\u3002'), U(r'Osprey \u4ef7\u683c\u98ce\u9669\u5df2\u5efa\u7acb\u4e13\u9898\u6a21\u677f\u3002')])}</div>
  <div class="panel"><h2>{U(r'AI \u5efa\u8bae')}</h2>{self.bullets(data['ai_suggestions'][:4] or [empty])}<p><a class="btn dark" href="/ai-ceo">{U(r'\u67e5\u770b AI \u603b\u7ecf\u7406\u65e5\u62a5')}</a></p></div>
</div>"""
        self.out(layout(U(r"\u7ecf\u8425\u9a7e\u9a76\u8231"), body, user=user, wide=True))

    def store_operations(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.role_can_manage(user):
            return self.dashboard(user)
        stores = [U(r"\u5357\u5c71\u5e97"), U(r"\u632f\u5174\u5e97"), U(r"\u822a\u82d1\u5e97"), U(r"\u91d1\u6c99\u5e97"), U(r"\u7f51\u5e97")]
        cards = "".join(self.card(store, U(r"\u9500\u552e\u3001\u6bdb\u5229\u3001\u5e93\u5b58\u3001\u8d39\u7528\u3001\u5458\u5de5\u548c AI \u5efa\u8bae\u7b49\u5f85\u6570\u636e\u63a5\u5165\u3002"), "/tasks", "btn green", True) for store in stores)
        body = f"<div class='panel'><h2>{U(r'\u95e8\u5e97\u7ecf\u8425')}</h2><p class='small'>{U(r'\u6309\u95e8\u5e97\u67e5\u770b\u9500\u552e\u3001\u6bdb\u5229\u3001\u5e93\u5b58\u3001\u8d39\u7528\u3001\u5458\u5de5\u548c\u98ce\u9669\u3002')}</p></div><div class='grid'>{cards}</div>"
        self.out(layout(U(r"\u95e8\u5e97\u7ecf\u8425"), body, user=user, wide=True))

    def brand_operations(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.role_can_manage(user):
            return self.dashboard(user)
        brands = ["KAILAS", "Osprey", "Mammut", "Salomon", "Deuter", "Gregory", "VAFOX"]
        cards = "".join(self.card(brand, U(r"\u9500\u552e\u8d8b\u52bf\u3001\u6bdb\u5229\u8d8b\u52bf\u3001\u5e93\u5b58\u538b\u529b\u3001\u6298\u6263\u98ce\u9669\u548c\u4f9b\u5e94\u5546\u98ce\u9669\u3002"), "/brands/osprey-risk" if brand == "Osprey" else "/tasks", "btn", True) for brand in brands)
        body = f"<div class='panel'><h2>{U(r'\u54c1\u724c\u7ecf\u8425')}</h2><p class='small'>{U(r'\u4e0d\u4f2a\u9020\u9500\u552e\u6570\u636e\uff0c\u6ca1\u6709 SAP \u7ef4\u5ea6\u65f6\u663e\u793a\u7b49\u5f85\u63a5\u5165\u3002')}</p></div><div class='grid'>{cards}</div>"
        self.out(layout(U(r"\u54c1\u724c\u7ecf\u8425"), body, user=user, wide=True))

    def inventory_risk(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.role_can_manage(user):
            return self.dashboard(user)
        data = self.cockpit_data()
        m = data["metrics"]
        body = f"""
<div class="panel"><h2>{U(r'\u5e93\u5b58\u98ce\u9669')}</h2><div class="metrics">{self.metric(U(r'\u5e93\u5b58\u91d1\u989d'), U(r'\uffe5') + money(m['inventory_amount']), U(r'SAP B1'))}{self.metric(U(r'\u98ce\u9669\u6570\u91cf'), money(m['risk_count']), U(r'\u9700\u8ddf\u8fdb'))}</div></div>
<div class="split">
  <div class="panel"><h2>{U(r'\u98ce\u9669\u7c7b\u578b')}</h2>{self.bullets([U(r'\u9ad8\u5e93\u5b58\u54c1\u724c'), U(r'\u9ad8\u5e93\u5b58\u4ea7\u54c1'), U(r'\u6ede\u9500\u4ea7\u54c1'), U(r'\u5b63\u8282\u98ce\u9669'), U(r'\u6298\u6263\u98ce\u9669'), U(r'\u73b0\u91d1\u6d41\u5360\u7528')])}</div>
  <div class="panel"><h2>{U(r'AI \u6e05\u8d27\u5efa\u8bae')}</h2>{self.bullets([data['empty_message'], U(r'\u540e\u7eed\u6309\u54c1\u724c\u3001SKU\u3001\u5c3a\u7801\u3001\u5e97\u94fa\u751f\u6210\u6e05\u8d27\u52a8\u4f5c\u3002')])}</div>
</div>"""
        self.out(layout(U(r"\u5e93\u5b58\u98ce\u9669"), body, user=user, wide=True))

    def osprey_risk(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.role_can_manage(user):
            return self.dashboard(user)
        body = f"""
<div class="panel"><h2>{U(r'Osprey \u4ef7\u683c\u98ce\u9669\u4e13\u9898')}</h2><p class="small">{U(r'\u8fd9\u662f\u7ed3\u6784\u5316\u5206\u6790\u6a21\u677f\uff0c\u4e0d\u628a\u8f93\u5165\u5185\u5bb9\u81ea\u52a8\u5f53\u4f5c\u7cfb\u7edf\u4e8b\u5b9e\u3002')}</p></div>
<div class="split">
  <div class="panel"><h2>{U(r'\u5f53\u524d\u95ee\u9898')}</h2>{self.bullets([U(r'\u4f4e\u6298\u6263\u9500\u552e\u53ef\u80fd\u5f71\u54cd\u6bdb\u5229\u548c\u7528\u6237\u4ef7\u683c\u9884\u671f\u3002'), U(r'\u8fd4\u70b9\u4e0d\u786e\u5b9a\u4f1a\u5f71\u54cd\u771f\u5b9e\u5229\u6da6\u3002'), U(r'\u4ee3\u7406/\u6e20\u9053\u7a33\u5b9a\u6027\u9700\u8981\u6301\u7eed\u89c2\u5bdf\u3002')])}</div>
  <div class="panel"><h2>{U(r'\u5bf9\u6bd4\u6a21\u578b')}</h2>{self.bullets([U(r'59 \u6298\u957f\u671f\u9500\u552e\u98ce\u9669'), U(r'60 / 62 / 65 \u6298\u5bf9\u6bd4'), U(r'\u8fd4\u70b9\u4f9d\u8d56\u98ce\u9669'), U(r'\u5e93\u5b58\u63d0\u8d27\u98ce\u9669')])}</div>
</div>
<div class="panel form">
  <h2>{U(r'\u7b80\u6613\u8bd5\u7b97\u5668')}</h2>
  <form method="post" action="/api/brands/osprey-risk/calculate">
    <label>{U(r'\u6210\u672c\u6298\u6263')}</label><input name="cost_discount" placeholder="0.50">
    <label>{U(r'\u9500\u552e\u6298\u6263')}</label><input name="selling_discount" placeholder="0.60">
    <label>{U(r'\u8fd4\u70b9\u6bd4\u7387')}</label><input name="rebate_rate" placeholder="0.03">
    <label>{U(r'\u5e93\u5b58\u91d1\u989d')}</label><input name="inventory_amount" placeholder="0">
    <label>{U(r'\u9884\u8ba1\u9500\u552e\u989d')}</label><input name="expected_sales_amount" placeholder="0">
    <label>{U(r'\u56fa\u5b9a\u8d39\u7528\u5206\u644a')}</label><input name="fixed_expense_allocation" placeholder="0">
    <p class="small">{U(r'\u7ed3\u679c\u7531 API \u8fd4\u56de JSON\uff0c\u4e0d\u5199\u6b7b\u8d22\u52a1\u7ed3\u8bba\u3002')}</p>
  </form>
</div>
<div class="split"><div class="panel"><h2>{U(r'\u76f8\u5173\u6587\u4ef6')}</h2>{self.empty_state(U(r'\u53ef\u4ece\u77e5\u8bc6\u5e93\u5173\u8054 Osprey \u6587\u6863\u3002'))}</div><div class="panel"><h2>{U(r'\u76f8\u5173\u7814\u7a76')}</h2>{self.empty_state(U(r'\u7814\u7a76\u5f15\u64ce\u63a5\u5165\u540e\u663e\u793a\u5916\u90e8\u4ef7\u683c\u89c2\u5bdf\u3002'))}</div></div>"""
        self.out(layout(U(r"Osprey \u4ef7\u683c\u98ce\u9669"), body, user=user, wide=True))

    def task_center(self, user):
        user = self.require_login(user)
        if not user:
            return
        with db() as conn:
            rows = conn.execute("select * from tasks order by status='done', updated_at desc limit 100").fetchall()
        cards = ""
        for row in rows:
            cards += "<div class='card'><div><h2>{}</h2><p>{}</p><p class='small'>{} · {} · {} · {}</p></div>{}</div>".format(
                esc(row["title"]), esc(row["description"]), esc(row["owner"]), esc(row["priority"]), esc(row["status"]), esc(row["due_date"]),
                "" if row["status"] == "done" else f"<form method='post' action='/tasks/complete'><input type='hidden' name='id' value='{row['id']}'><button>{U(r'完成')}</button></form>"
            )
        if not cards:
            cards = "<div class='panel'>{}</div>".format(self.empty_state(U(r"\u6682\u65e0\u4efb\u52a1\uff0c\u53ef\u4ece AI \u5efa\u8bae\u6216\u65e5\u5e38\u7ecf\u8425\u4e2d\u521b\u5efa\u3002")))
        body = f"""
<div class="panel form"><h2>{U(r'\u4efb\u52a1\u4e2d\u5fc3 V1')}</h2>
  <form method="post" action="/tasks/save">
    <label>{U(r'\u4efb\u52a1\u6807\u9898')}</label><input name="title" required>
    <label>{U(r'\u8bf4\u660e')}</label><textarea name="description"></textarea>
    <label>{U(r'\u8d23\u4efb\u4eba')}</label><input name="owner" placeholder="{esc(user['name'])}">
    <label>{U(r'\u4f18\u5148\u7ea7')}</label><select name="priority"><option value="normal">{U(r'\u666e\u901a')}</option><option value="high">{U(r'\u9ad8')}</option><option value="urgent">{U(r'\u7d27\u6025')}</option><option value="low">{U(r'\u4f4e')}</option></select>
    <label>{U(r'\u622a\u6b62\u65e5\u671f')}</label><input name="due_date" placeholder="2026-07-05">
    <label>{U(r'\u5173\u8054\u5bf9\u8c61')}</label><input name="related_object_type" placeholder="stores / brands / knowledge / research"><input name="related_object_id" placeholder="ID">
    <p><button>{U(r'\u521b\u5efa\u4efb\u52a1')}</button></p>
  </form>
</div>
<div class="grid">{cards}</div>"""
        self.out(layout(U(r"\u4efb\u52a1\u4e2d\u5fc3"), body, user=user, wide=True))

    def task_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        form = self.form()
        title = form.get("title", "").strip()
        if not title:
            return self.redir("/tasks")
        priority = form.get("priority", "normal")
        if priority not in ("low", "normal", "high", "urgent"):
            priority = "normal"
        related_id = form.get("related_object_id", "").strip()
        now = ts()
        with db() as conn:
            cur = conn.execute(
                "insert into tasks(task_id,title,description,owner,related_object_type,related_object_id,priority,status,due_date,source_type,source_id,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("TASK-" + uuid.uuid4().hex[:10], title, form.get("description", ""), form.get("owner", "") or user["name"], form.get("related_object_type", ""), int(related_id) if related_id.isdigit() else None, priority, "todo", form.get("due_date", ""), form.get("source_type", "manual"), form.get("source_id", ""), user["id"], now, now),
            )
            conn.execute("insert into timeline_events(target_type,target_id,title,body,created_by,created_at) values(?,?,?,?,?,?)", ("task", cur.lastrowid, U(r"\u521b\u5efa\u4efb\u52a1"), title, user["id"], now))
        self.log_action(user, "task_create", "task", cur.lastrowid, title)
        return self.redir("/tasks")

    def task_complete(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        tid = self.form().get("id")
        with db() as conn:
            conn.execute("update tasks set status='done', updated_at=? where id=?", (ts(), tid))
        self.log_action(user, "task_complete", "task", tid, "")
        return self.redir("/tasks")

    def health_payload(self):
        now = ts()
        checks = {}
        try:
            with db() as conn:
                conn.execute("select 1").fetchone()
            checks["database_status"] = "ok"
        except Exception:
            checks["database_status"] = "error"
        checks["sap_sync_status"] = "summary_file_present" if os.path.exists(SAP_SUMMARY_FILE) else "waiting"
        checks["document_engine_status"] = "ready"
        checks["knowledge_engine_status"] = "ready"
        checks["research_engine_status"] = "placeholder"
        checks["automation_engine_status"] = "ready"
        checks["memory_engine_status"] = "ready"
        checks["knowledge_graph_status"] = "ready"
        return {"status": "ok" if checks["database_status"] == "ok" else "degraded", "app_version": "FoxBrain V4 Task008", "environment": os.environ.get("APP_ENV", "production"), **checks, "timestamp": now}

    def api_health(self):
        return self.json_out(self.health_payload())

    def system_health(self, user):
        user = self.require_login(user)
        if not user:
            return
        payload = self.health_payload()
        items = [f"{k}: {v}" for k, v in payload.items()]
        body = f"<div class='panel'><h2>{U(r'\u7cfb\u7edf\u5065\u5eb7\u68c0\u67e5')}</h2>{self.bullets(items)}<p><a class='btn' href='/api/health'>{U(r'JSON \u5065\u5eb7\u63a5\u53e3')}</a></p></div>"
        self.out(layout(U(r"\u7cfb\u7edf\u5065\u5eb7\u68c0\u67e5"), body, user=user))

    def calculate_osprey_payload(self, form):
        def f(name):
            try:
                return float(form.get(name, "") or 0)
            except Exception:
                return 0.0
        cost_discount = f("cost_discount")
        selling_discount = f("selling_discount")
        rebate_rate = f("rebate_rate")
        expected_sales = f("expected_sales_amount")
        fixed_expense = f("fixed_expense_allocation")
        gross_margin = selling_discount - cost_discount
        rebate_adjusted = gross_margin + rebate_rate
        net_after_expense = expected_sales * rebate_adjusted - fixed_expense if expected_sales else 0
        risk_level = "unknown"
        if expected_sales:
            risk_level = "high" if net_after_expense < 0 else ("medium" if rebate_adjusted < 0.08 else "review")
        return {"gross_margin_spread": gross_margin, "rebate_adjusted_margin_spread": rebate_adjusted, "estimated_net_after_expense": net_after_expense, "risk_level": risk_level, "note": U(r"\u8bd5\u7b97\u4ec5\u57fa\u4e8e\u7528\u6237\u8f93\u5165\uff0c\u4e0d\u4ee3\u8868 SAP \u5b9e\u9645\u8d22\u52a1\u7ed3\u8bba\u3002")}

    def api_task005_get(self, user, path):
        if not user and path != "/api/health":
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if path == "/api/ai-ceo/daily-briefing":
            return self.json_out({"ok": True, "data": self.cockpit_data(), "message": "safe briefing payload"})
        if path == "/api/business/cockpit":
            return self.json_out({"ok": True, "data": self.cockpit_data()})
        if path == "/api/stores/operations":
            return self.json_out({"ok": True, "stores": [U(r"\u5357\u5c71\u5e97"), U(r"\u632f\u5174\u5e97"), U(r"\u822a\u82d1\u5e97"), U(r"\u91d1\u6c99\u5e97"), U(r"\u7f51\u5e97")], "message": self.cockpit_data()["empty_message"]})
        if path == "/api/brands/operations":
            return self.json_out({"ok": True, "brands": ["KAILAS", "Osprey", "Mammut", "Salomon", "Deuter", "Gregory", "VAFOX"], "message": self.cockpit_data()["empty_message"]})
        if path == "/api/inventory/risk":
            return self.json_out({"ok": True, "data": self.cockpit_data()["metrics"], "message": self.cockpit_data()["empty_message"]})
        if path == "/api/brands/osprey-risk":
            return self.json_out({"ok": True, "template": "osprey pricing risk", "message": U(r"\u4ec5\u4f5c\u4e3a\u7ed3\u6784\u5316\u98ce\u9669\u6a21\u677f\uff0c\u4e0d\u58f0\u660e\u4e3a\u7cfb\u7edf\u4e8b\u5b9e\u3002")})
        if path == "/api/tasks":
            with db() as conn:
                rows = conn.execute("select * from tasks order by updated_at desc limit 100").fetchall()
            return self.json_out({"ok": True, "tasks": [row_dict(r) for r in rows]})
        return self.json_out({"ok": False, "message": "unknown Task005 api"}, code=404)

    def api_task005_post(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if path == "/api/brands/osprey-risk/calculate":
            return self.json_out({"ok": True, "result": self.calculate_osprey_payload(self.form())})
        if path == "/api/tasks":
            form = self.form()
            now = ts()
            with db() as conn:
                cur = conn.execute(
                    "insert into tasks(task_id,title,description,owner,related_object_type,related_object_id,priority,status,due_date,source_type,source_id,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    ("TASK-" + uuid.uuid4().hex[:10], form.get("title", U(r"\u672a\u547d\u540d\u4efb\u52a1")), form.get("description", ""), form.get("owner", user["name"]), form.get("related_object_type", ""), None, form.get("priority", "normal"), "todo", form.get("due_date", ""), form.get("source_type", "api"), form.get("source_id", ""), user["id"], now, now),
                )
            return self.json_out({"ok": True, "task_id": cur.lastrowid})
        m = re.match(r"^/api/tasks/(\d+)/complete$", path)
        if m:
            with db() as conn:
                conn.execute("update tasks set status='done', updated_at=? where id=?", (ts(), m.group(1)))
            return self.json_out({"ok": True})
        m = re.match(r"^/api/tasks/(\d+)$", path)
        if m:
            form = self.form()
            with db() as conn:
                conn.execute("update tasks set title=coalesce(?,title), description=coalesce(?,description), owner=coalesce(?,owner), priority=coalesce(?,priority), status=coalesce(?,status), due_date=coalesce(?,due_date), updated_at=? where id=?", (form.get("title"), form.get("description"), form.get("owner"), form.get("priority"), form.get("status"), form.get("due_date"), ts(), m.group(1)))
            return self.json_out({"ok": True})
        return self.json_out({"ok": False, "message": "unknown Task005 api"}, code=404)

    def automation_center(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.role_can_manage(user):
            return self.dashboard(user)
        data = self.automation_summary()
        metrics = "".join(
            [
                self.metric(U(r"\u8fd0\u884c\u4e2d"), data["running"], U(r"\u5f53\u524d\u6d41\u7a0b")),
                self.metric(U(r"\u5f85\u5904\u7406"), data["pending"], U(r"\u542f\u7528/\u8349\u7a3f/\u6682\u505c")),
                self.metric(U(r"\u5931\u8d25\u4efb\u52a1"), data["failed"], U(r"\u9700\u590d\u6838")),
                self.metric(U(r"\u6a21\u677f"), len(data["templates"]), U(r"\u53ef\u590d\u7528")),
            ]
        )
        template_cards = "".join(
            "<div class='card'><div><h2>{}</h2><p>{}</p><p class='small'>{} · {}</p></div><span class='pill'>{}</span></div>".format(
                esc(t["name"]), esc(t["description"]), esc(t["trigger_type"]), esc(t["owner"]), esc(t["status"])
            )
            for t in data["templates"][:10]
        )
        automation_cards = "".join(
            "<div class='card'><div><h2>{}</h2><p>{}</p><p class='small'>{} · {} · {}</p></div><span class='pill'>{}</span></div>".format(
                esc(a["name"]), esc(a["description"]), esc(a["trigger_type"]), esc(a["action_type"]), esc(a["owner"]), esc(a["status"])
            )
            for a in data["automations"][:10]
        )
        if not automation_cards:
            automation_cards = "<div class='panel'>{}</div>".format(self.empty_state(U(r"\u6682\u65e0\u81ea\u52a8\u5316\u4efb\u52a1\uff0c\u53ef\u5148\u521b\u5efa\u4e00\u6761\u624b\u52a8\u6216\u5b9a\u65f6\u6d41\u7a0b\u3002")))
        body = f"""
<div class="panel">
  <h2>{U(r'AI \u81ea\u52a8\u5316\u4e2d\u5fc3')}</h2>
  <p class="small">{U(r'\u628a\u7ecf\u8425\u5efa\u8bae\u3001SAP \u626b\u63cf\u3001\u77e5\u8bc6\u5e93\u3001\u7814\u7a76\u5f15\u64ce\u548c\u4efb\u52a1\u4e2d\u5fc3\u8fde\u6210\u53ef\u6267\u884c\u7684 AI \u6d41\u7a0b\u3002')}</p>
  <div class="metrics">{metrics}</div>
</div>
<div class="split">
  <div class="panel form">
    <h2>{U(r'\u521b\u5efa\u81ea\u52a8\u5316')}</h2>
    <form method="post" action="/automation/save">
      <label>{U(r'\u540d\u79f0')}</label><input name="name" required>
      <label>{U(r'\u8bf4\u660e')}</label><textarea name="description"></textarea>
      <label>{U(r'\u89e6\u53d1\u5668')}</label><select name="trigger_type">{''.join('<option value="{}">{}</option>'.format(esc(x), esc(x)) for x in data['triggers'])}</select>
      <label>{U(r'AI \u52a8\u4f5c')}</label><select name="action_type">{''.join('<option value="{}">{}</option>'.format(esc(x), esc(x)) for x in data['actions'])}</select>
      <label>{U(r'\u8d1f\u8d23\u4eba')}</label><input name="owner" value="{esc(user['name'])}">
      <p><button>{U(r'\u4fdd\u5b58\u81ea\u52a8\u5316')}</button></p>
    </form>
  </div>
  <div class="panel">
    <h2>{U(r'AI \u6bcf\u65e5\u81ea\u52a8\u4efb\u52a1')}</h2>{self.bullets(data['daily_jobs'])}
    <h2>{U(r'\u901a\u77e5\u6e20\u9053')}</h2>{self.bullets(data['channels'])}
  </div>
</div>
<div class="panel"><h2>{U(r'\u5de5\u4f5c\u6d41\u6a21\u677f')}</h2><div class="grid">{template_cards}</div></div>
<div class="panel"><h2>{U(r'\u81ea\u52a8\u5316\u4efb\u52a1')}</h2><div class="grid">{automation_cards}</div></div>
<div class="panel"><h2>{U(r'\u6267\u884c\u5386\u53f2')}</h2>{self.bullets([dt(r['created_at']) + ' · ' + r['status'] + ' · ' + (r['message'] or '') for r in data['runs']] or [U(r'\u6682\u65e0\u6267\u884c\u8bb0\u5f55\u3002')])}</div>
<div class="panel"><h2>{U(r'\u901a\u77e5\u4e2d\u5fc3')}</h2>{self.bullets([n['channel'] + ' · ' + n['title'] + ' · ' + n['status'] for n in data['notifications']] or [U(r'\u6682\u65e0\u901a\u77e5\u3002')])}</div>"""
        self.out(layout(U(r"AI \u81ea\u52a8\u5316\u4e2d\u5fc3"), body, user=user, wide=True))

    def automation_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        if not self.role_can_manage(user):
            return self.redir("/")
        form = self.form()
        name = form.get("name", "").strip()
        if not name:
            return self.redir("/automation")
        now = ts()
        with db() as conn:
            cur = conn.execute(
                "insert into automations(automation_id,name,description,trigger_type,action_type,status,owner,ai_recommendation,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?)",
                ("AUTO-" + uuid.uuid4().hex[:10], name, form.get("description", ""), form.get("trigger_type", "manual"), form.get("action_type", "create_task"), "active", form.get("owner", user["name"]), U(r"\u7b49\u5f85 AI \u63a5\u5165\u540e\u6839\u636e\u6267\u884c\u5386\u53f2\u4f18\u5316\u6d41\u7a0b\u3002"), user["id"], now, now),
            )
            conn.execute("insert into automation_runs(run_id,automation_id,status,message,created_at) values(?,?,?,?,?)", ("RUN-" + uuid.uuid4().hex[:10], cur.lastrowid, "pending", U(r"\u81ea\u52a8\u5316\u5df2\u521b\u5efa\uff0c\u7b49\u5f85\u89e6\u53d1\u5668\u6267\u884c\u3002"), now))
        self.log_action(user, "automation_create", "automation", cur.lastrowid, name)
        return self.redir("/automation")

    def workflow_template_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        if not self.role_can_manage(user):
            return self.redir("/")
        form = self.form()
        now = ts()
        with db() as conn:
            conn.execute(
                "insert into workflow_templates(template_id,name,description,trigger_type,steps_json,owner,status,ai_recommendation,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?)",
                ("WF-" + uuid.uuid4().hex[:10], form.get("name", U(r"\u672a\u547d\u540d\u6d41\u7a0b")), form.get("description", ""), form.get("trigger_type", "manual"), json.dumps(csv_values(form.get("steps", "")), ensure_ascii=False), form.get("owner", user["name"]), form.get("status", "draft"), form.get("ai_recommendation", ""), user["id"], now, now),
            )
        return self.redir("/automation")

    def api_automation_get(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.role_can_manage(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        data = self.automation_summary()
        if path == "/api/automation":
            return self.json_out({"ok": True, "dashboard": {"running": data["running"], "pending": data["pending"], "failed": data["failed"], "daily_jobs": data["daily_jobs"], "triggers": data["triggers"], "actions": data["actions"]}, "automations": [row_dict(r) for r in data["automations"]]})
        if path == "/api/workflows":
            return self.json_out({"ok": True, "templates": [row_dict(r) for r in data["templates"]]})
        if path == "/api/notifications":
            return self.json_out({"ok": True, "notifications": [row_dict(r) for r in data["notifications"]]})
        return self.json_out({"ok": False, "message": "unknown automation api"}, code=404)

    def api_automation_post(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.role_can_manage(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        form = self.form()
        now = ts()
        if path == "/api/automation":
            with db() as conn:
                cur = conn.execute(
                    "insert into automations(automation_id,name,description,trigger_type,action_type,status,owner,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?)",
                    ("AUTO-" + uuid.uuid4().hex[:10], form.get("name", U(r"\u672a\u547d\u540d\u81ea\u52a8\u5316")), form.get("description", ""), form.get("trigger_type", "manual"), form.get("action_type", "create_task"), form.get("status", "draft"), form.get("owner", user["name"]), user["id"], now, now),
                )
            return self.json_out({"ok": True, "automation_id": cur.lastrowid})
        if path == "/api/workflows":
            with db() as conn:
                cur = conn.execute(
                    "insert into workflow_templates(template_id,name,description,trigger_type,steps_json,owner,status,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?)",
                    ("WF-" + uuid.uuid4().hex[:10], form.get("name", U(r"\u672a\u547d\u540d\u6d41\u7a0b")), form.get("description", ""), form.get("trigger_type", "manual"), json.dumps(csv_values(form.get("steps", "")), ensure_ascii=False), form.get("owner", user["name"]), form.get("status", "draft"), user["id"], now, now),
                )
            return self.json_out({"ok": True, "workflow_template_id": cur.lastrowid})
        return self.json_out({"ok": False, "message": "unknown automation api"}, code=404)

    def can_view_memory(self, user, row):
        if not user or not row:
            return False
        visibility = row["visibility"] if "visibility" in row.keys() else "manager_only"
        if visibility == "public_internal":
            return True
        if visibility == "manager_only":
            return user["role"] in ("boss", "admin", "store_manager")
        if visibility == "owner_only":
            return int(row["created_by"] or 0) == int(user["id"])
        if visibility == "finance_only":
            return user["role"] in ("boss", "admin", "finance")
        if visibility == "restricted":
            return user["role"] in ("boss", "admin")
        return user["role"] in ("boss", "admin")

    def can_approve_memory(self, user):
        return bool(user and user["role"] in ("boss", "admin", "store_manager"))

    def memory_to_json(self, row):
        return row_dict(row) or {}

    def memory_center(self, user):
        user = self.require_login(user)
        if not user:
            return
        qd = parse_qs(urlparse(self.path).query)
        q = qd.get("q", [""])[0].strip()
        memory_type = qd.get("type", [""])[0].strip()
        status = qd.get("status", [""])[0].strip()
        where, params = [], []
        if q:
            like = "%" + q + "%"
            where.append("(title like ? or content like ? or memory_type like ?)")
            params += [like, like, like]
        if memory_type:
            where.append("memory_type=?")
            params.append(memory_type)
        if status:
            where.append("status=?")
            params.append(status)
        sql = "select * from memories"
        if where:
            sql += " where " + " and ".join(where)
        sql += " order by case status when 'pending_review' then 0 when 'approved' then 1 else 2 end, updated_at desc limit 100"
        with db() as conn:
            rows = [r for r in conn.execute(sql, params).fetchall() if self.can_view_memory(user, r)]
            prefs = conn.execute("select * from user_preferences where user_id=? order by updated_at desc limit 20", (user["id"],)).fetchall()
            decisions = conn.execute("select * from decision_memories order by updated_at desc limit 8").fetchall()
            counts = {
                "total": conn.execute("select count(*) c from memories").fetchone()["c"],
                "pending": conn.execute("select count(*) c from memories where status='pending_review'").fetchone()["c"],
                "approved": conn.execute("select count(*) c from memories where status='approved'").fetchone()["c"],
                "archived": conn.execute("select count(*) c from memories where status='archived'").fetchone()["c"],
            }
        type_opts = [
            "company_principle", "user_preference", "business_decision", "pricing_rule", "brand_strategy",
            "store_strategy", "supplier_risk", "customer_insight", "ai_suggestion", "rejected_suggestion",
        ]
        cards = ""
        for row in rows:
            action = ""
            if self.can_approve_memory(user) and row["status"] == "pending_review":
                action = f"<form method='post' action='/memory/action'><input type='hidden' name='id' value='{row['id']}'><button name='action' value='approve'>{U(r'审核通过')}</button><button class='gray' name='action' value='reject'>{U(r'拒绝')}</button></form>"
            cards += "<div class='card'><div><h2>{}</h2><p>{}</p><p class='small'>{} · {} · {} · {}</p></div><a class='btn full' href='/memory/view?id={}'>{}</a>{}</div>".format(
                esc(row["title"]), esc(summarize_text(row["content"], 160)), esc(row["memory_type"]), esc(row["importance"]), esc(row["status"]), esc(dt(row["updated_at"])), row["id"], U(r"查看"), action
            )
        if not cards:
            cards = "<div class='panel'>{}</div>".format(self.empty_state(U(r"\u6682\u65e0\u8bb0\u5fc6\uff0cAI \u6216\u7ba1\u7406\u8005\u53ef\u5148\u521b\u5efa\u5f85\u5ba1\u6838\u8bb0\u5fc6\u3002")))
        pref_items = [f"{p['key']}: {p['value']} ({p['scope']})" for p in prefs] or [U(r"\u6682\u65e0\u504f\u597d\u8bbe\u7f6e\u3002")]
        decision_items = [d["decision_title"] + " · " + (d["decision_date"] or "") for d in decisions] or [U(r"\u6682\u65e0\u51b3\u7b56\u8bb0\u5fc6\u3002")]
        body = f"""
<div class="panel">
  <h2>{U(r'AI \u8bb0\u5fc6\u4e2d\u5fc3')}</h2>
  <p class="small">{U(r'\u8fd9\u91cc\u4fdd\u5b58\u957f\u671f\u7ecf\u8425\u539f\u5219\u3001\u7528\u6237\u504f\u597d\u3001\u51b3\u7b56\u3001\u5b9a\u4ef7\u89c4\u5219\u548c\u98ce\u9669\u5224\u65ad\u3002AI \u4e0d\u4f1a\u672a\u7ecf\u5ba1\u6838\u81ea\u52a8\u5199\u5165\u6c38\u4e45\u8bb0\u5fc6\u3002')}</p>
  <div class="metrics">{self.metric(U(r'\u8bb0\u5fc6\u603b\u6570'), counts['total'], U(r'\u5168\u90e8'))}{self.metric(U(r'\u5f85\u5ba1\u6838'), counts['pending'], U(r'\u9700\u590d\u6838'))}{self.metric(U(r'\u5df2\u901a\u8fc7'), counts['approved'], U(r'AI \u53ef\u53c2\u8003'))}{self.metric(U(r'\u5df2\u5f52\u6863'), counts['archived'], U(r'\u5386\u53f2'))}</div>
</div>
<div class="split">
  <div class="panel form">
    <h2>{U(r'\u65b0\u5efa\u5f85\u5ba1\u6838\u8bb0\u5fc6')}</h2>
    <form method="post" action="/memory/save">
      <label>{U(r'\u6807\u9898')}</label><input name="title" required>
      <label>{U(r'\u5185\u5bb9')}</label><textarea name="content"></textarea>
      <label>{U(r'\u8bb0\u5fc6\u7c7b\u578b')}</label><select name="memory_type">{''.join('<option value="{}">{}</option>'.format(esc(x), esc(x)) for x in type_opts)}</select>
      <label>{U(r'\u91cd\u8981\u6027')}</label><select name="importance"><option value="normal">normal</option><option value="high">high</option><option value="critical">critical</option><option value="low">low</option></select>
      <label>{U(r'\u53ef\u89c1\u8303\u56f4')}</label><select name="visibility"><option value="manager_only">manager_only</option><option value="public_internal">public_internal</option><option value="owner_only">owner_only</option><option value="finance_only">finance_only</option><option value="restricted">restricted</option></select>
      <p><button>{U(r'\u4fdd\u5b58\u5f85\u5ba1\u6838\u8bb0\u5fc6')}</button></p>
    </form>
  </div>
  <div class="panel form">
    <h2>{U(r'\u7528\u6237\u504f\u597d')}</h2>
    <form method="post" action="/preferences/save">
      <label>Key</label><input name="key" placeholder="dashboard_style / ai_response_style / risk_tolerance" required>
      <label>Value</label><input name="value" required>
      <label>Scope</label><input name="scope" value="user">
      <p><button>{U(r'\u4fdd\u5b58\u504f\u597d')}</button></p>
    </form>
    {self.bullets(pref_items)}
  </div>
</div>
<div class="panel">
  <form method="get" action="/memory">
    <label>{U(r'\u641c\u7d22\u8bb0\u5fc6')}</label><input name="q" value="{esc(q)}" placeholder="{U(r'\u641c\u7d22\u6807\u9898\u3001\u5185\u5bb9\u3001\u7c7b\u578b')}">
    <label>{U(r'\u7c7b\u578b')}</label><input name="type" value="{esc(memory_type)}">
    <label>{U(r'\u72b6\u6001')}</label><input name="status" value="{esc(status)}" placeholder="pending_review / approved / archived">
    <p><button>{U(r'\u641c\u7d22')}</button></p>
  </form>
</div>
<div class="grid">{cards}</div>
<div class="split"><div class="panel"><h2>{U(r'\u51b3\u7b56\u8bb0\u5fc6')}</h2>{self.bullets(decision_items)}<p><a class="btn" href="/decisions">{U(r'\u65b0\u589e\u51b3\u7b56')}</a></p></div><div class="panel"><h2>{U(r'AI \u603b\u7ecf\u7406\u53c2\u8003\u8bb0\u5fc6')}</h2>{self.bullets([U(r'\u6700\u8fd1\u91cd\u8981\u51b3\u7b56'), U(r'\u5f53\u524d\u7ecf\u8425\u539f\u5219'), U(r'\u98ce\u9669\u504f\u597d'), U(r'\u54c1\u724c\u7b56\u7565'), U(r'\u5b9a\u4ef7\u539f\u5219')])}</div></div>"""
        self.out(layout(U(r"AI \u8bb0\u5fc6\u4e2d\u5fc3"), body, user=user, wide=True))

    def memory_view(self, user):
        user = self.require_login(user)
        if not user:
            return
        mid = parse_qs(urlparse(self.path).query).get("id", [""])[0]
        with db() as conn:
            row = conn.execute("select * from memories where id=?", (mid,)).fetchone()
        if not row or not self.can_view_memory(user, row):
            return self.redir("/memory")
        body = f"""
<div class="panel">
  <h2>{esc(row['title'])}</h2>
  <p class="small">{esc(row['memory_id'])} · {esc(row['memory_type'])} · {esc(row['importance'])} · {esc(row['confidence'])} · {esc(row['status'])}</p>
  <p>{esc(row['content'])}</p>
  <h2>{U(r'\u5173\u8054\u5bf9\u8c61')}</h2><p>{esc(row['object_type'] or U(r'\u6682\u65e0'))} {esc(row['object_id'] or '')}</p>
  <p><a class="btn gray" href="/memory">{U(r'\u8fd4\u56de')}</a></p>
</div>"""
        self.out(layout(row["title"], body, user=user, wide=True))

    def memory_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        form = self.form()
        title = form.get("title", "").strip()
        if not title:
            return self.redir("/memory")
        visibility = form.get("visibility", "manager_only")
        if visibility not in ("public_internal", "manager_only", "owner_only", "finance_only", "restricted"):
            visibility = "manager_only"
        now = ts()
        with db() as conn:
            cur = conn.execute(
                "insert into memories(memory_id,title,content,memory_type,object_type,object_id,source_type,source_id,importance,confidence,visibility,status,created_by,created_at,updated_at,expires_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("MEM-" + uuid.uuid4().hex[:10], title, form.get("content", ""), form.get("memory_type", "company_principle"), module_key(form.get("object_type", "")), int(form.get("object_id")) if str(form.get("object_id", "")).isdigit() else None, form.get("source_type", "manual"), form.get("source_id", ""), form.get("importance", "normal"), form.get("confidence", "medium"), visibility, "pending_review", user["id"], now, now, None),
            )
        self.log_action(user, "memory_create", "memory", cur.lastrowid, title)
        return self.redir("/memory")

    def memory_action(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        if not self.can_approve_memory(user):
            return self.redir("/memory")
        form = self.form()
        action = form.get("action", "")
        status_map = {"approve": "approved", "reject": "archived", "archive": "archived", "expire": "expired"}
        status = status_map.get(action)
        if status:
            with db() as conn:
                conn.execute("update memories set status=?, updated_at=? where id=?", (status, ts(), form.get("id")))
            self.log_action(user, "memory_" + action, "memory", form.get("id"), "")
        return self.redir("/memory")

    def preference_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        form = self.form()
        key = form.get("key", "").strip()
        if not key:
            return self.redir("/memory")
        scope = form.get("scope", "user") or "user"
        now = ts()
        with db() as conn:
            conn.execute(
                "insert into user_preferences(preference_id,user_id,key,value,scope,created_at,updated_at) values(?,?,?,?,?,?,?) on conflict(user_id,key,scope) do update set value=excluded.value, updated_at=excluded.updated_at",
                ("PREF-" + uuid.uuid4().hex[:10], user["id"], key, form.get("value", ""), scope, now, now),
            )
        self.log_action(user, "preference_changed", "preference", None, key)
        return self.redir("/memory")

    def decision_memory(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.role_can_manage(user):
            return self.dashboard(user)
        with db() as conn:
            rows = conn.execute("select * from decision_memories order by updated_at desc limit 50").fetchall()
        cards = "".join("<div class='card'><div><h2>{}</h2><p>{}</p><p class='small'>{} · {}</p></div></div>".format(esc(r["decision_title"]), esc(r["reason"]), esc(r["owner"]), esc(r["decision_date"])) for r in rows)
        if not cards:
            cards = "<div class='panel'>{}</div>".format(self.empty_state(U(r"\u6682\u65e0\u51b3\u7b56\u8bb0\u5fc6\u3002")))
        body = f"""
<div class="panel form">
  <h2>{U(r'\u51b3\u7b56\u8bb0\u5fc6')}</h2>
  <form method="post" action="/decisions/save">
    <label>{U(r'\u51b3\u7b56\u6807\u9898')}</label><input name="decision_title" required>
    <label>{U(r'\u51b3\u7b56\u80cc\u666f')}</label><textarea name="decision_context"></textarea>
    <label>{U(r'\u8003\u8651\u8fc7\u7684\u9009\u9879')}</label><textarea name="options_considered"></textarea>
    <label>{U(r'\u9009\u62e9\u65b9\u6848')}</label><input name="selected_option">
    <label>{U(r'\u539f\u56e0')}</label><textarea name="reason"></textarea>
    <label>{U(r'\u98ce\u9669')}</label><textarea name="risks"></textarea>
    <label>{U(r'\u8d1f\u8d23\u4eba')}</label><input name="owner" value="{esc(user['name'])}">
    <label>{U(r'\u51b3\u7b56\u65e5\u671f')}</label><input name="decision_date" placeholder="2026-07-04">
    <label>{U(r'\u540e\u7eed\u4efb\u52a1')}</label><input name="follow_up_task">
    <p><button>{U(r'\u4fdd\u5b58\u51b3\u7b56')}</button></p>
  </form>
</div>
<div class="grid">{cards}</div>"""
        self.out(layout(U(r"\u51b3\u7b56\u8bb0\u5fc6"), body, user=user, wide=True))

    def decision_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        if not self.role_can_manage(user):
            return self.redir("/")
        form = self.form()
        title = form.get("decision_title", "").strip()
        if not title:
            return self.redir("/decisions")
        now = ts()
        with db() as conn:
            mem = conn.execute(
                "insert into memories(memory_id,title,content,memory_type,source_type,importance,confidence,visibility,status,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?)",
                ("MEM-" + uuid.uuid4().hex[:10], title, form.get("reason", ""), "business_decision", "decision", "high", "medium", "manager_only", "pending_review", user["id"], now, now),
            )
            conn.execute(
                "insert into decision_memories(decision_id,decision_title,decision_context,options_considered,selected_option,reason,risks,owner,decision_date,related_objects,follow_up_task,memory_id,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("DEC-" + uuid.uuid4().hex[:10], title, form.get("decision_context", ""), form.get("options_considered", ""), form.get("selected_option", ""), form.get("reason", ""), form.get("risks", ""), form.get("owner", user["name"]), form.get("decision_date", ""), form.get("related_objects", ""), form.get("follow_up_task", ""), mem.lastrowid, user["id"], now, now),
            )
        self.log_action(user, "decision_created", "decision", None, title)
        return self.redir("/decisions")

    def api_memory_get(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if path == "/api/memory":
            with db() as conn:
                rows = [r for r in conn.execute("select * from memories order by updated_at desc limit 100").fetchall() if self.can_view_memory(user, r)]
            return self.json_out({"ok": True, "memories": [self.memory_to_json(r) for r in rows]})
        m = re.match(r"^/api/memory/(\d+)$", path)
        if m:
            with db() as conn:
                row = conn.execute("select * from memories where id=?", (m.group(1),)).fetchone()
            if not row or not self.can_view_memory(user, row):
                return self.json_out({"ok": False, "message": "not found"}, code=404)
            return self.json_out({"ok": True, "memory": self.memory_to_json(row)})
        if path == "/api/preferences":
            with db() as conn:
                rows = conn.execute("select * from user_preferences where user_id=? order by updated_at desc", (user["id"],)).fetchall()
            return self.json_out({"ok": True, "preferences": [row_dict(r) for r in rows]})
        if path == "/api/decisions":
            if not self.role_can_manage(user):
                return self.json_out({"ok": False, "message": "no permission"}, code=403)
            with db() as conn:
                rows = conn.execute("select * from decision_memories order by updated_at desc limit 100").fetchall()
            return self.json_out({"ok": True, "decisions": [row_dict(r) for r in rows]})
        return self.json_out({"ok": False, "message": "unknown memory api"}, code=404)

    def api_memory_post(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        form = self.form()
        now = ts()
        if path == "/api/memory":
            title = form.get("title", "").strip() or U(r"\u672a\u547d\u540d\u8bb0\u5fc6")
            with db() as conn:
                cur = conn.execute(
                    "insert into memories(memory_id,title,content,memory_type,source_type,source_id,importance,confidence,visibility,status,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    ("MEM-" + uuid.uuid4().hex[:10], title, form.get("content", ""), form.get("memory_type", "company_principle"), form.get("source_type", "api"), form.get("source_id", ""), form.get("importance", "normal"), form.get("confidence", "medium"), form.get("visibility", "manager_only"), "pending_review", user["id"], now, now),
                )
            return self.json_out({"ok": True, "memory_id": cur.lastrowid})
        m = re.match(r"^/api/memory/(\d+)/(approve|reject|archive)$", path)
        if m:
            if not self.can_approve_memory(user):
                return self.json_out({"ok": False, "message": "no permission"}, code=403)
            status = {"approve": "approved", "reject": "archived", "archive": "archived"}[m.group(2)]
            with db() as conn:
                conn.execute("update memories set status=?, updated_at=? where id=?", (status, now, m.group(1)))
            return self.json_out({"ok": True})
        if path == "/api/preferences":
            key = form.get("key", "").strip()
            if not key:
                return self.json_out({"ok": False, "message": "key required"}, code=400)
            scope = form.get("scope", "user")
            with db() as conn:
                conn.execute("insert into user_preferences(preference_id,user_id,key,value,scope,created_at,updated_at) values(?,?,?,?,?,?,?) on conflict(user_id,key,scope) do update set value=excluded.value, updated_at=excluded.updated_at", ("PREF-" + uuid.uuid4().hex[:10], user["id"], key, form.get("value", ""), scope, now, now))
            return self.json_out({"ok": True})
        if path == "/api/decisions":
            if not self.role_can_manage(user):
                return self.json_out({"ok": False, "message": "no permission"}, code=403)
            with db() as conn:
                cur = conn.execute(
                    "insert into decision_memories(decision_id,decision_title,decision_context,options_considered,selected_option,reason,risks,owner,decision_date,related_objects,follow_up_task,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    ("DEC-" + uuid.uuid4().hex[:10], form.get("decision_title", U(r"\u672a\u547d\u540d\u51b3\u7b56")), form.get("decision_context", ""), form.get("options_considered", ""), form.get("selected_option", ""), form.get("reason", ""), form.get("risks", ""), form.get("owner", user["name"]), form.get("decision_date", ""), form.get("related_objects", ""), form.get("follow_up_task", ""), user["id"], now, now),
                )
            return self.json_out({"ok": True, "decision_id": cur.lastrowid})
        return self.json_out({"ok": False, "message": "unknown memory api"}, code=404)

    def can_view_graph(self, user):
        return bool(user)

    def can_manage_graph(self, user):
        return bool(user and user["role"] in ("boss", "admin", "store_manager", "purchasing", "finance"))

    def entity_to_json(self, row):
        return row_dict(row) or {}

    def relationship_to_json(self, row):
        data = row_dict(row) or {}
        data["source_entity_type"] = data.get("source_entity_type") or data.get("from_type")
        data["source_entity_id"] = data.get("source_entity_id") or data.get("from_id")
        data["target_entity_type"] = data.get("target_entity_type") or data.get("to_type")
        data["target_entity_id"] = data.get("target_entity_id") or data.get("to_id")
        return data

    def ensure_graph_entity(self, conn, entity_type, entity_key, entity_name, description="", source_type="", source_id="", user_id=None):
        row = conn.execute("select * from graph_entities where entity_type=? and entity_key=?", (entity_type, entity_key)).fetchone()
        now = ts()
        if row:
            conn.execute("update graph_entities set entity_name=?, description=coalesce(?,description), updated_at=? where id=?", (entity_name, description, now, row["id"]))
            return row["id"]
        cur = conn.execute(
            "insert into graph_entities(entity_id,entity_type,entity_key,entity_name,description,source_type,source_id,status,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?)",
            ("ENT-" + uuid.uuid4().hex[:10], entity_type, entity_key, entity_name, description, source_type, source_id, "active", user_id, now, now),
        )
        return cur.lastrowid

    def create_graph_relationship(self, conn, src_type, src_id, dst_type, dst_id, relationship_type, description="", evidence_type="", evidence_id=None, user_id=None):
        if not src_type or not dst_type or not src_id or not dst_id:
            return None
        existing = conn.execute(
            "select id from relations where source_entity_type=? and source_entity_id=? and target_entity_type=? and target_entity_id=? and relationship_type=?",
            (src_type, src_id, dst_type, dst_id, relationship_type),
        ).fetchone()
        now = ts()
        if existing:
            conn.execute("update relations set updated_at=?, description=coalesce(?,description) where id=?", (now, description, existing["id"]))
            return existing["id"]
        cur = conn.execute(
            """insert into relations(
 relationship_id,from_type,from_id,to_type,to_id,source_entity_type,source_entity_id,target_entity_type,target_entity_id,
 relation_type,relationship_type,strength,confidence,direction,description,evidence_type,evidence_id,created_by,created_at,updated_at
) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("REL-" + uuid.uuid4().hex[:10], src_type, src_id, dst_type, dst_id, src_type, src_id, dst_type, dst_id, relationship_type, relationship_type, "normal", "medium", "directed", description, evidence_type, evidence_id, user_id, now, now),
        )
        return cur.lastrowid

    def run_graph_extraction(self, user=None):
        created = {"entities": 0, "relationships": 0, "risks": 0}
        with db() as conn:
            before_entities = conn.execute("select count(*) c from graph_entities").fetchone()["c"]
            before_rels = conn.execute("select count(*) c from relations where relationship_id is not null").fetchone()["c"]
            for row in conn.execute("select * from records where status!='deleted'").fetchall():
                eid = self.ensure_graph_entity(conn, row["module"], f"record:{row['id']}", row["title"], row["summary"] or "", "record", str(row["id"]), user["id"] if user else None)
                if row["module"] == "products":
                    data = safe_json(row["data_json"], {})
                    brand = data.get(U(r"\u54c1\u724c")) or data.get("brand")
                    if brand:
                        bid = self.ensure_graph_entity(conn, "brand", "brand:" + str(brand).lower(), str(brand), "", "record_text", str(row["id"]), user["id"] if user else None)
                        self.create_graph_relationship(conn, "product", eid, "brand", bid, "belongs_to", U(r"\u4ece\u4ea7\u54c1\u6863\u6848\u54c1\u724c\u5b57\u6bb5\u63d0\u53d6"), "record", row["id"], user["id"] if user else None)
                if row["module"] == "employees":
                    data = safe_json(row["data_json"], {})
                    store = data.get(U(r"\u90e8\u95e8")) or data.get(U(r"\u95e8\u5e97")) or data.get("store")
                    if store:
                        sid = self.ensure_graph_entity(conn, "store", "store:" + str(store).lower(), str(store), "", "record_text", str(row["id"]), user["id"] if user else None)
                        self.create_graph_relationship(conn, "employee", eid, "store", sid, "works_at", U(r"\u4ece\u5458\u5de5\u6863\u6848\u95e8\u5e97/\u90e8\u95e8\u5b57\u6bb5\u63d0\u53d6"), "record", row["id"], user["id"] if user else None)
            for row in conn.execute("select * from knowledge_items order by updated_at desc limit 500").fetchall():
                kid = self.ensure_graph_entity(conn, "knowledge", f"knowledge:{row['id']}", row["title"], row["summary"] or row["ai_summary"] or "", "knowledge", str(row["id"]), user["id"] if user else None)
                if row["object_type"] and row["object_id"]:
                    oid = self.ensure_graph_entity(conn, row["object_type"], f"{row['object_type']}:{row['object_id']}", f"{row['object_type']} #{row['object_id']}", "", "knowledge_relation", str(row["id"]), user["id"] if user else None)
                    self.create_graph_relationship(conn, "knowledge", kid, row["object_type"], oid, "documented_by", U(r"\u4ece\u77e5\u8bc6\u6761\u76ee\u5173\u8054\u5bf9\u8c61\u63d0\u53d6"), "knowledge", row["id"], user["id"] if user else None)
            for row in conn.execute("select * from memories where status='approved'").fetchall():
                mid = self.ensure_graph_entity(conn, "memory", f"memory:{row['id']}", row["title"], row["content"] or "", "memory", str(row["id"]), user["id"] if user else None)
                if row["object_type"] and row["object_id"]:
                    oid = self.ensure_graph_entity(conn, row["object_type"], f"{row['object_type']}:{row['object_id']}", f"{row['object_type']} #{row['object_id']}", "", "memory_relation", str(row["id"]), user["id"] if user else None)
                    self.create_graph_relationship(conn, "memory", mid, row["object_type"], oid, "affects", U(r"\u4ece\u5df2\u5ba1\u6838\u8bb0\u5fc6\u5173\u8054\u5bf9\u8c61\u63d0\u53d6"), "memory", row["id"], user["id"] if user else None)
            for row in conn.execute("select * from tasks").fetchall():
                tid = self.ensure_graph_entity(conn, "task", f"task:{row['id']}", row["title"], row["description"] or "", "task", str(row["id"]), user["id"] if user else None)
                if row["related_object_type"] and row["related_object_id"]:
                    oid = self.ensure_graph_entity(conn, row["related_object_type"], f"{row['related_object_type']}:{row['related_object_id']}", f"{row['related_object_type']} #{row['related_object_id']}", "", "task_relation", str(row["id"]), user["id"] if user else None)
                    self.create_graph_relationship(conn, "task", tid, row["related_object_type"], oid, "related_to", U(r"\u4ece\u4efb\u52a1\u5173\u8054\u5bf9\u8c61\u63d0\u53d6"), "task", row["id"], user["id"] if user else None)
            after_entities = conn.execute("select count(*) c from graph_entities").fetchone()["c"]
            after_rels = conn.execute("select count(*) c from relations where relationship_id is not null").fetchone()["c"]
            created["entities"] = after_entities - before_entities
            created["relationships"] = after_rels - before_rels
        self.log_action(user, "graph_extraction_run", "graph", None, json.dumps(created, ensure_ascii=False))
        return created

    def graph_summary(self):
        with db() as conn:
            entity_count = conn.execute("select count(*) c from graph_entities").fetchone()["c"]
            relationship_count = conn.execute("select count(*) c from relations where relationship_id is not null or source_entity_type is not null").fetchone()["c"]
            risk_count = conn.execute("select count(*) c from graph_risks").fetchone()["c"]
            entities = conn.execute("select * from graph_entities order by updated_at desc limit 40").fetchall()
            relationships = conn.execute("select * from relations where relationship_id is not null or source_entity_type is not null order by created_at desc limit 40").fetchall()
            risks = conn.execute("select * from graph_risks order by updated_at desc limit 40").fetchall()
            by_type = conn.execute("select entity_type, count(*) c from graph_entities group by entity_type order by c desc limit 10").fetchall()
        return {"entity_count": entity_count, "relationship_count": relationship_count, "risk_count": risk_count, "entities": entities, "relationships": relationships, "risks": risks, "by_type": by_type}

    def graph_center(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_view_graph(user):
            return self.dashboard(user)
        q = parse_qs(urlparse(self.path).query).get("q", [""])[0].strip()
        data = self.graph_summary()
        entity_cards = ""
        entities = data["entities"]
        if q:
            ql = q.lower()
            entities = [e for e in entities if ql in (e["entity_name"] or "").lower() or ql in (e["entity_type"] or "").lower()]
        for e in entities[:12]:
            connected = 0
            with db() as conn:
                connected = conn.execute("select count(*) c from relations where (source_entity_type=? and source_entity_id=?) or (target_entity_type=? and target_entity_id=?) or (from_type=? and from_id=?) or (to_type=? and to_id=?)", (e["entity_type"], e["id"], e["entity_type"], e["id"], e["entity_type"], e["id"], e["entity_type"], e["id"])).fetchone()["c"]
            entity_cards += "<div class='card'><div><h2>{}</h2><p>{}</p><p class='small'>{} · {} connections</p></div><a class='btn full' href='/api/graph/entity-network?id={}'>{}</a></div>".format(esc(e["entity_name"]), esc(e["description"]), esc(e["entity_type"]), connected, e["id"], U(r"查看网络 JSON"))
        if not entity_cards:
            entity_cards = "<div class='panel'>{}</div>".format(self.empty_state(U(r"\u6682\u65e0\u56fe\u8c31\u5b9e\u4f53\uff0c\u53ef\u5148\u8fd0\u884c\u89c4\u5219\u62bd\u53d6\u3002")))
        rel_items = []
        for r in data["relationships"][:12]:
            rel = self.relationship_to_json(r)
            rel_items.append(f"{rel.get('source_entity_type')} #{rel.get('source_entity_id')} -> {rel.get('target_entity_type')} #{rel.get('target_entity_id')} / {rel.get('relationship_type') or rel.get('relation_type')}")
        risk_items = [f"{r['title']} · {r['risk_type']} · {r['level']}" for r in data["risks"][:10]] or [U(r"\u6682\u65e0\u98ce\u9669\u8bb0\u5f55\uff0c\u4e0d\u4f1a\u4f2a\u9020\u98ce\u9669\u503c\u3002")]
        type_pills = "".join("<span class='pill'>{} {}</span>".format(esc(r["entity_type"]), r["c"]) for r in data["by_type"])
        body = f"""
<div class="panel">
  <h2>{U(r'\u4f01\u4e1a\u77e5\u8bc6\u56fe\u8c31')}</h2>
  <p class="small">{U(r'\u628a\u95e8\u5e97\u3001\u5458\u5de5\u3001\u54c1\u724c\u3001\u4ea7\u54c1\u3001\u4f9b\u5e94\u5546\u3001\u77e5\u8bc6\u3001\u8bb0\u5fc6\u3001\u4efb\u52a1\u548c\u98ce\u9669\u8fde\u6210\u53ef\u7406\u89e3\u7684\u5173\u7cfb\u7f51\u3002')}</p>
  <div class="metrics">{self.metric(U(r'\u5b9e\u4f53'), data['entity_count'], U(r'\u5bf9\u8c61'))}{self.metric(U(r'\u5173\u7cfb'), data['relationship_count'], U(r'\u8fde\u63a5'))}{self.metric(U(r'\u98ce\u9669'), data['risk_count'], U(r'\u8bb0\u5f55'))}</div>
  <form method="get" action="/graph"><label>{U(r'\u56fe\u8c31\u641c\u7d22')}</label><input name="q" value="{esc(q)}" placeholder="{U(r'\u641c\u7d22\u5b9e\u4f53\u3001\u7c7b\u578b\u3001\u98ce\u9669\u5173\u952e\u8bcd')}"><p><button>{U(r'\u641c\u7d22')}</button></p></form>
  <form method="post" action="/api/graph/extract"><button class="dark">{U(r'\u8fd0\u884c\u89c4\u5219\u62bd\u53d6')}</button></form>
  <div>{type_pills}</div>
</div>
<div class="split"><div class="panel"><h2>{U(r'\u98ce\u9669\u5730\u56fe')}</h2>{self.bullets(risk_items)}<p><a class="btn" href="/api/graph/risk-map">{U(r'\u98ce\u9669\u5730\u56fe JSON')}</a></p></div><div class="panel"><h2>{U(r'Osprey \u98ce\u9669\u56fe\u8c31')}</h2>{self.bullets([U(r'\u54c1\u724c\uff1aOsprey'), U(r'\u5b9a\u4ef7\u98ce\u9669'), U(r'\u8fd4\u70b9\u4e0d\u786e\u5b9a'), U(r'\u76f8\u5173\u4efb\u52a1/\u6587\u6863/\u51b3\u7b56\u5f85\u63a5\u5165')])}<p><a class="btn" href="/api/graph/osprey-risk">{U(r'Osprey \u56fe\u8c31 JSON')}</a></p></div></div>
<div class="panel"><h2>{U(r'\u5b9e\u4f53\u6d4f\u89c8')}</h2><div class="grid">{entity_cards}</div></div>
<div class="panel"><h2>{U(r'\u5173\u7cfb\u6d4f\u89c8')}</h2>{self.bullets(rel_items or [U(r'\u6682\u65e0\u5173\u7cfb\uff0c\u8bf7\u5148\u8fd0\u884c\u62bd\u53d6\u6216\u624b\u52a8\u5efa\u7acb\u3002')])}</div>
<div class="panel"><h2>{U(r'AI \u67e5\u8be2\u56fe\u8c31\u4e0a\u4e0b\u6587')}</h2>{self.bullets([U(r'\u68c0\u7d22\u76f8\u5173\u5b9e\u4f53'), U(r'\u68c0\u7d22\u76f8\u5173\u5173\u7cfb'), U(r'\u68c0\u7d22\u8bc1\u636e'), U(r'\u7ec4\u5408\u4e0a\u4e0b\u6587'), U(r'\u5e26\u5f15\u7528\u56de\u7b54')])}</div>"""
        self.out(layout(U(r"\u4f01\u4e1a\u77e5\u8bc6\u56fe\u8c31"), body, user=user, wide=True))

    def api_graph_get(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_view_graph(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        if path == "/api/graph":
            data = self.graph_summary()
            return self.json_out({"ok": True, "dashboard": {"entities": data["entity_count"], "relationships": data["relationship_count"], "risks": data["risk_count"]}})
        if path == "/api/graph/entities":
            with db() as conn:
                rows = conn.execute("select * from graph_entities order by updated_at desc limit 200").fetchall()
            return self.json_out({"ok": True, "entities": [self.entity_to_json(r) for r in rows]})
        m = re.match(r"^/api/graph/entities/(\d+)$", path)
        if m:
            with db() as conn:
                row = conn.execute("select * from graph_entities where id=?", (m.group(1),)).fetchone()
            return self.json_out({"ok": bool(row), "entity": self.entity_to_json(row)})
        if path == "/api/graph/relationships":
            with db() as conn:
                rows = conn.execute("select * from relations where relationship_id is not null or source_entity_type is not null order by created_at desc limit 200").fetchall()
            return self.json_out({"ok": True, "relationships": [self.relationship_to_json(r) for r in rows]})
        if path == "/api/graph/search":
            q = parse_qs(urlparse(self.path).query).get("q", [""])[0].strip()
            like = "%" + q + "%"
            with db() as conn:
                rows = conn.execute("select * from graph_entities where entity_name like ? or entity_type like ? or description like ? order by updated_at desc limit 100", (like, like, like)).fetchall()
            return self.json_out({"ok": True, "entities": [self.entity_to_json(r) for r in rows]})
        if path == "/api/graph/entity-network":
            eid = parse_qs(urlparse(self.path).query).get("id", [""])[0]
            with db() as conn:
                entity = conn.execute("select * from graph_entities where id=?", (eid,)).fetchone()
                rels = conn.execute("select * from relations where source_entity_id=? or target_entity_id=? or from_id=? or to_id=? order by created_at desc limit 80", (eid, eid, eid, eid)).fetchall()
            return self.json_out({"ok": bool(entity), "entity": self.entity_to_json(entity), "relationships": [self.relationship_to_json(r) for r in rels]})
        if path == "/api/graph/risk-map":
            with db() as conn:
                rows = conn.execute("select * from graph_risks order by case level when 'critical' then 0 when 'high' then 1 when 'medium' then 2 else 3 end, updated_at desc limit 200").fetchall()
            return self.json_out({"ok": True, "risks": [row_dict(r) for r in rows], "message": U(r"\u6ca1\u6709\u771f\u5b9e\u8bb0\u5f55\u65f6\u4e0d\u4f2a\u9020\u98ce\u9669\u503c\u3002")})
        if path == "/api/graph/osprey-risk":
            return self.json_out({"ok": True, "brand": "Osprey", "nodes": ["Brand: Osprey", "Pricing risk", "Decision memory", "Research observation", "Inventory", "Supplier / agency", "Rebate uncertainty", "Tasks", "Documents", "AI suggestions"], "message": U(r"\u7ed3\u6784\u5360\u4f4d\uff1a\u4ec5\u663e\u793a\u5df2\u5f55\u5165\u6216\u5df2\u5173\u8054\u7684\u4fe1\u606f\uff0c\u4e0d\u58f0\u660e\u771f\u5b9e\u8d22\u52a1\u6570\u636e\u3002")})
        return self.json_out({"ok": False, "message": "unknown graph api"}, code=404)

    def api_graph_post(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_manage_graph(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        form = self.form()
        now = ts()
        if path == "/api/graph/entities":
            with db() as conn:
                eid = self.ensure_graph_entity(conn, form.get("entity_type", "unknown"), form.get("entity_key", "manual:" + uuid.uuid4().hex[:8]), form.get("entity_name", U(r"\u672a\u547d\u540d\u5b9e\u4f53")), form.get("description", ""), form.get("source_type", "manual"), form.get("source_id", ""), user["id"])
            self.log_action(user, "graph_entity_created", "graph_entity", eid, form.get("entity_name", ""))
            return self.json_out({"ok": True, "entity_id": eid})
        if path == "/api/graph/relationships":
            with db() as conn:
                rid = self.create_graph_relationship(conn, form.get("source_entity_type"), form.get("source_entity_id"), form.get("target_entity_type"), form.get("target_entity_id"), form.get("relationship_type", "related_to"), form.get("description", ""), form.get("evidence_type", ""), int(form.get("evidence_id")) if str(form.get("evidence_id", "")).isdigit() else None, user["id"])
            self.log_action(user, "graph_relationship_created", "graph_relationship", rid, form.get("relationship_type", ""))
            return self.json_out({"ok": True, "relationship_id": rid})
        if path == "/api/graph/extract":
            result = self.run_graph_extraction(user)
            return self.json_out({"ok": True, "result": result, "message": U(r"\u53ea\u4ece\u5df2\u6709\u660e\u786e\u5b57\u6bb5\u548c\u7528\u6237\u5173\u8054\u62bd\u53d6\uff0c\u4e0d\u7f16\u9020\u4e8b\u5b9e\u3002")})
        if path == "/api/graph/risk-map":
            with db() as conn:
                cur = conn.execute(
                    "insert into graph_risks(risk_id,title,risk_type,level,object_type,object_id,related_entities,evidence,recommendation,status,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    ("RISK-" + uuid.uuid4().hex[:10], form.get("title", U(r"\u672a\u547d\u540d\u98ce\u9669")), form.get("risk_type", "unknown"), form.get("level", "unknown"), form.get("object_type", ""), int(form.get("object_id")) if str(form.get("object_id", "")).isdigit() else None, form.get("related_entities", ""), form.get("evidence", ""), form.get("recommendation", ""), form.get("status", "open"), user["id"], now, now),
                )
            self.log_action(user, "graph_risk_created", "graph_risk", cur.lastrowid, form.get("title", ""))
            return self.json_out({"ok": True, "risk_id": cur.lastrowid})
        return self.json_out({"ok": False, "message": "unknown graph api"}, code=404)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), App).serve_forever()
