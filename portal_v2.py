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


APP_DIR = os.environ.get("APP_DIR", "/opt/firefox-portal")
DB = APP_DIR + "/portal.db"
SECRET_FILE = APP_DIR + "/secret.key"
ENV_FILE = APP_DIR + "/portal.env"
SAP_SUMMARY_FILE = os.environ.get("SAP_SUMMARY_FILE", "/opt/firefox-sap-sync/latest_summary.json")
UPLOAD_DIR = APP_DIR + "/uploads"
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8088"))
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
        ensure_column(conn, "knowledge_items", "owner", "owner text")
        ensure_column(conn, "knowledge_items", "department", "department text")
        ensure_column(conn, "knowledge_items", "version", "version text not null default '1.0'")
        ensure_column(conn, "knowledge_items", "retention_policy", "retention_policy text not null default 'standard'")
        ensure_column(conn, "knowledge_items", "deleted_at", "deleted_at integer")
        conn.execute("create index if not exists idx_knowledge_status on knowledge_items(status)")
        conn.execute("create index if not exists idx_knowledge_object on knowledge_items(object_type, object_id)")
        conn.execute("create index if not exists idx_knowledge_visibility on knowledge_items(visibility)")
        conn.execute("create index if not exists idx_knowledge_governance on knowledge_items(owner, department, retention_policy)")
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
        ensure_column(conn, "automations", "risk_level", "risk_level text not null default 'low'")
        ensure_column(conn, "automations", "approval_required", "approval_required integer not null default 0")
        ensure_column(conn, "automations", "approval_status", "approval_status text not null default 'not_required'")
        ensure_column(conn, "automations", "retry_policy", "retry_policy text not null default 'standard'")
        ensure_column(conn, "automations", "max_retries", "max_retries integer not null default 3")
        ensure_column(conn, "automations", "audit_status", "audit_status text not null default 'enabled'")
        conn.execute("create index if not exists idx_automations_approval on automations(approval_required, approval_status)")
        conn.execute("create index if not exists idx_automations_risk on automations(risk_level)")
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
        ensure_column(conn, "automation_runs", "attempt_no", "attempt_no integer not null default 1")
        ensure_column(conn, "automation_runs", "next_retry_at", "next_retry_at integer")
        ensure_column(conn, "automation_runs", "approval_id", "approval_id text")
        ensure_column(conn, "automation_runs", "audit_event_id", "audit_event_id text")
        conn.execute("create index if not exists idx_automation_runs_retry on automation_runs(status, next_retry_at)")
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
        conn.execute(
            """
create table if not exists agent_roles(
 id integer primary key autoincrement,
 agent_id text unique,
 agent_name text not null,
 agent_role text not null,
 description text,
 responsibilities text,
 tools text,
 knowledge_scope text,
 memory_scope text,
 permission_scope text,
 status text not null default 'active',
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_agent_roles_status on agent_roles(status)")
        conn.execute(
            """
create table if not exists agent_tasks(
 id integer primary key autoincrement,
 agent_task_id text unique,
 title text not null,
 description text,
 assigned_agent_id integer,
 requested_by integer,
 related_object_type text,
 related_object_id integer,
 input_context text,
 expected_output text,
 status text not null default 'draft',
 priority text not null default 'normal',
 due_at text,
 result_summary text,
 human_review_status text not null default 'pending',
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_agent_tasks_status on agent_tasks(status)")
        conn.execute("create index if not exists idx_agent_tasks_agent on agent_tasks(assigned_agent_id)")
        conn.execute(
            """
create table if not exists agent_discussions(
 id integer primary key autoincrement,
 discussion_id text unique,
 topic text not null,
 initiator_agent_id integer,
 participating_agents text,
 context_objects text,
 messages text,
 conclusion text,
 recommended_actions text,
 human_review_status text not null default 'pending',
 created_by integer,
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_agent_discussions_review on agent_discussions(human_review_status)")
        conn.execute(
            """
create table if not exists agent_tools(
 id integer primary key autoincrement,
 tool_id text unique,
 tool_name text not null,
 description text,
 input_schema text,
 output_schema text,
 permission_required text,
 status text not null default 'active',
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_agent_tools_status on agent_tools(status)")
        ensure_column(conn, "agent_tools", "tool_category", "tool_category text")
        ensure_column(conn, "agent_tools", "tool_version", "tool_version text not null default 'v1'")
        ensure_column(conn, "agent_tools", "risk_level", "risk_level text not null default 'low'")
        ensure_column(conn, "agent_tools", "approval_required", "approval_required integer not null default 0")
        ensure_column(conn, "agent_tools", "audit_event", "audit_event text")
        conn.execute("create index if not exists idx_agent_tools_category on agent_tools(tool_category)")
        conn.execute("create index if not exists idx_agent_tools_risk on agent_tools(risk_level, approval_required)")
        conn.execute(
            """
create table if not exists jarvis_conversations(
 id integer primary key autoincrement,
 conversation_id text unique,
 user_id integer not null,
 title text not null,
 status text not null default 'active',
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_jarvis_conversations_user on jarvis_conversations(user_id, updated_at)")
        conn.execute(
            """
create table if not exists jarvis_messages(
 id integer primary key autoincrement,
 message_id text unique,
 conversation_id integer not null,
 role text not null,
 content text,
 intent text,
 tool_calls text,
 cited_sources text,
 related_objects text,
 confidence text,
 created_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_jarvis_messages_conversation on jarvis_messages(conversation_id, created_at)")
        conn.execute(
            """
create table if not exists jarvis_action_confirmations(
 id integer primary key autoincrement,
 action_id text unique,
 conversation_id integer,
 action_type text not null,
 title text not null,
 reason text,
 payload_json text,
 status text not null default 'pending',
 created_by integer,
 decided_by integer,
 created_at integer not null,
 decided_at integer
)
"""
        )
        conn.execute("create index if not exists idx_jarvis_actions_status on jarvis_action_confirmations(status)")
        conn.execute(
            """
create table if not exists reports(
 id integer primary key autoincrement,
 report_id text unique,
 title text not null,
 report_type text not null,
 date_range_start text,
 date_range_end text,
 object_type text,
 object_id integer,
 status text not null default 'draft',
 summary text,
 key_findings text,
 risks text,
 opportunities text,
 recommended_actions text,
 data_sources text,
 cited_documents text,
 cited_research text,
 cited_memory text,
 cited_sap_records text,
 generated_by integer,
 reviewed_by integer,
 reviewed_at integer,
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_reports_type on reports(report_type)")
        conn.execute("create index if not exists idx_reports_status on reports(status)")
        conn.execute(
            """
create table if not exists report_templates(
 id integer primary key autoincrement,
 template_id text unique,
 template_name text not null,
 report_type text not null,
 description text,
 sections text,
 required_sources text,
 default_date_range text,
 visibility text not null default 'manager_only',
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_report_templates_type on report_templates(report_type)")
        conn.execute(
            """
create table if not exists report_schedules(
 id integer primary key autoincrement,
 schedule_id text unique,
 report_template_id integer,
 frequency text not null default 'daily',
 recipients text,
 enabled integer not null default 1,
 last_run_at integer,
 next_run_at integer,
 created_by integer,
 created_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_report_schedules_enabled on report_schedules(enabled)")
        conn.execute(
            """
create table if not exists content_drafts(
 id integer primary key autoincrement,
 content_id text unique,
 title text not null,
 content_type text not null default 'article',
 topic text,
 body text,
 summary text,
 target_platforms text,
 status text not null default 'draft',
 campaign_id integer,
 related_object_type text,
 related_object_id integer,
 source_type text,
 source_id text,
 created_by integer,
 reviewed_by integer,
 reviewed_at integer,
 review_notes text,
 compliance_status text,
 scheduled_at integer,
 published_at integer,
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_content_drafts_status on content_drafts(status)")
        conn.execute("create index if not exists idx_content_drafts_type on content_drafts(content_type)")
        conn.execute(
            """
create table if not exists content_platform_versions(
 id integer primary key autoincrement,
 version_id text unique,
 content_id integer not null,
 platform text not null,
 title text,
 body text,
 hashtags text,
 media_requirements text,
 length_limit text,
 tone text,
 status text not null default 'draft',
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_content_versions_content on content_platform_versions(content_id)")
        conn.execute("create index if not exists idx_content_versions_platform on content_platform_versions(platform)")
        conn.execute(
            """
create table if not exists content_campaigns(
 id integer primary key autoincrement,
 campaign_id text unique,
 campaign_name text not null,
 campaign_type text,
 start_date text,
 end_date text,
 target_stores text,
 target_brands text,
 target_products text,
 goal text,
 budget text,
 status text not null default 'draft',
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_content_campaigns_status on content_campaigns(status)")
        conn.execute(
            """
create table if not exists content_publish_queue(
 id integer primary key autoincrement,
 queue_id text unique,
 content_version_id integer,
 platform text,
 scheduled_at integer,
 status text not null default 'queued',
 error_message text,
 published_url text,
 created_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_content_queue_status on content_publish_queue(status)")
        conn.execute(
            """
create table if not exists field_submissions(
 id integer primary key autoincrement,
 submission_id text unique,
 submission_type text not null,
 title text not null,
 content text,
 store_id text,
 employee_id integer,
 related_object_type text,
 related_object_id integer,
 photos text,
 attachments text,
 tags text,
 status text not null default 'submitted',
 reviewed_by integer,
 reviewed_at integer,
 review_notes text,
 created_by integer,
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_field_submissions_type on field_submissions(submission_type)")
        conn.execute("create index if not exists idx_field_submissions_status on field_submissions(status)")
        conn.execute("create index if not exists idx_field_submissions_user on field_submissions(created_by, created_at)")
        conn.execute(
            """
create table if not exists store_diagnoses(
 id integer primary key autoincrement,
 diagnosis_id text unique,
 store_id text not null,
 date_range_start text,
 date_range_end text,
 sales_status text,
 margin_status text,
 traffic_status text,
 conversion_status text,
 inventory_status text,
 staff_status text,
 customer_status text,
 key_problems text,
 opportunities text,
 ai_suggestions text,
 data_sources text,
 status text not null default 'draft',
 created_by integer,
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_store_diagnoses_store on store_diagnoses(store_id, created_at)")
        conn.execute(
            """
create table if not exists store_growth_plans(
 id integer primary key autoincrement,
 growth_plan_id text unique,
 store_id text not null,
 title text not null,
 goal text,
 start_date text,
 end_date text,
 target_sales text,
 target_margin text,
 target_customers text,
 target_tasks text,
 key_actions text,
 related_brands text,
 related_products text,
 owner text,
 status text not null default 'draft',
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_store_growth_plans_store on store_growth_plans(store_id, status)")
        conn.execute(
            """
create table if not exists store_activities(
 id integer primary key autoincrement,
 activity_id text unique,
 store_id text not null,
 title text not null,
 activity_type text,
 start_date text,
 end_date text,
 target_customer text,
 target_brand text,
 target_product text,
 budget text,
 expected_result text,
 content_plan text,
 task_plan text,
 status text not null default 'draft',
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_store_activities_store on store_activities(store_id, status)")
        conn.execute(
            """
create table if not exists store_focus_items(
 id integer primary key autoincrement,
 focus_id text unique,
 store_id text not null,
 brand_id text,
 product_id text,
 focus_reason text,
 period text,
 status text not null default 'active',
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_store_focus_store on store_focus_items(store_id, status)")
        conn.execute(
            """
create table if not exists brand_diagnoses(
 id integer primary key autoincrement,
 diagnosis_id text unique,
 brand_id text not null,
 date_range_start text,
 date_range_end text,
 sales_status text,
 margin_status text,
 inventory_status text,
 discount_status text,
 supplier_status text,
 market_status text,
 customer_feedback text,
 key_problems text,
 opportunities text,
 ai_suggestions text,
 data_sources text,
 status text not null default 'draft',
 created_by integer,
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_brand_diagnoses_brand on brand_diagnoses(brand_id, created_at)")
        conn.execute(
            """
create table if not exists brand_strategies(
 id integer primary key autoincrement,
 strategy_id text unique,
 brand_id text not null,
 strategy_title text not null,
 brand_role text,
 target_customer text,
 target_stores text,
 pricing_principle text,
 inventory_principle text,
 content_principle text,
 growth_goal text,
 risk_control text,
 key_actions text,
 status text not null default 'draft',
 created_by integer,
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_brand_strategies_brand on brand_strategies(brand_id, status)")
        conn.execute(
            """
create table if not exists product_portfolios(
 id integer primary key autoincrement,
 portfolio_id text unique,
 brand_id text,
 product_id text,
 product_role text,
 season text,
 status text not null default 'draft',
 sales_level text,
 margin_level text,
 inventory_level text,
 markdown_level text,
 recommendation text,
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_product_portfolios_brand on product_portfolios(brand_id, status)")
        conn.execute(
            """
create table if not exists pricing_strategies(
 id integer primary key autoincrement,
 pricing_strategy_id text unique,
 brand_id text,
 product_id text,
 normal_discount text,
 promotion_discount text,
 clearance_discount text,
 minimum_allowed_discount text,
 rebate_assumption text,
 margin_warning_line text,
 notes text,
 status text not null default 'draft',
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_pricing_strategies_brand on pricing_strategies(brand_id, status)")
        conn.execute(
            """
create table if not exists supplier_brand_risks(
 id integer primary key autoincrement,
 risk_id text unique,
 supplier_id text,
 brand_id text,
 rebate_rate text,
 rebate_uncertainty text,
 contract_status text,
 agency_status text,
 payment_terms text,
 delivery_risk text,
 relationship_risk text,
 notes text,
 status text not null default 'draft',
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_supplier_brand_risks_brand on supplier_brand_risks(brand_id, status)")
        conn.execute(
            """
create table if not exists inventory_decision_risks(
 id integer primary key autoincrement,
 inventory_risk_id text unique,
 object_type text,
 object_id integer,
 brand_id text,
 product_id text,
 store_id text,
 risk_type text,
 risk_level text,
 inventory_quantity text,
 inventory_amount text,
 sales_velocity text,
 days_of_inventory text,
 margin_level text,
 markdown_need text,
 cash_occupation text,
 recommendation text,
 status text not null default 'draft',
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_inventory_decision_risks_type on inventory_decision_risks(risk_type, status)")
        conn.execute(
            """
create table if not exists replenishment_suggestions(
 id integer primary key autoincrement,
 suggestion_id text unique,
 store_id text,
 brand_id text,
 product_id text,
 reason text,
 sales_velocity text,
 current_stock text,
 suggested_quantity text,
 priority text,
 status text not null default 'draft',
 created_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_replenishment_status on replenishment_suggestions(status)")
        conn.execute(
            """
create table if not exists transfer_suggestions(
 id integer primary key autoincrement,
 transfer_id text unique,
 from_store_id text,
 to_store_id text,
 brand_id text,
 product_id text,
 quantity text,
 reason text,
 urgency text,
 status text not null default 'draft',
 created_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_transfer_status on transfer_suggestions(status)")
        conn.execute(
            """
create table if not exists markdown_suggestions(
 id integer primary key autoincrement,
 markdown_id text unique,
 brand_id text,
 product_id text,
 store_id text,
 current_discount text,
 suggested_discount text,
 reason text,
 expected_result text,
 risk_level text,
 approval_status text not null default 'pending_review',
 created_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_markdown_status on markdown_suggestions(approval_status)")
        conn.execute(
            """
create table if not exists future_orders(
 id integer primary key autoincrement,
 future_order_id text unique,
 supplier_id text,
 brand_id text,
 season text,
 order_amount text,
 deposit_amount text,
 deposit_rate text,
 expected_delivery_date text,
 cancellation_risk text,
 pricing_risk text,
 rebate_assumption text,
 status text not null default 'draft',
 decision_status text not null default 'pending',
 created_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_future_orders_brand on future_orders(brand_id, decision_status)")
        conn.execute(
            """
create table if not exists purchasing_plans(
 id integer primary key autoincrement,
 purchasing_plan_id text unique,
 title text not null,
 supplier_id text,
 brand_id text,
 season text,
 budget text,
 planned_items text,
 expected_margin text,
 risk_assessment text,
 status text not null default 'draft',
 created_by integer,
 created_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_purchasing_plans_status on purchasing_plans(status)")
        conn.execute(
            """
create table if not exists finance_profit_records(
 id integer primary key autoincrement,
 profit_record_id text unique,
 object_type text,
 object_id text,
 date_range_start text,
 date_range_end text,
 revenue real not null default 0,
 cost real not null default 0,
 gross_profit real not null default 0,
 gross_margin real not null default 0,
 expenses real not null default 0,
 net_profit real not null default 0,
 net_margin real not null default 0,
 rebate_amount real not null default 0,
 rebate_adjusted_profit real not null default 0,
 cash_occupation real not null default 0,
 data_sources text,
 status text not null default 'draft',
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_finance_profit_object on finance_profit_records(object_type, object_id, status)")
        conn.execute(
            """
create table if not exists finance_expenses(
 id integer primary key autoincrement,
 expense_id text unique,
 expense_type text not null,
 store_id text,
 department_id text,
 amount real not null default 0,
 period text,
 description text,
 related_object_type text,
 related_object_id text,
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_finance_expenses_type on finance_expenses(expense_type, period)")
        conn.execute(
            """
create table if not exists finance_rebates(
 id integer primary key autoincrement,
 rebate_id text unique,
 supplier_id text,
 brand_id text,
 period text,
 sales_amount real not null default 0,
 rebate_rate real not null default 0,
 expected_rebate real not null default 0,
 actual_rebate real not null default 0,
 status text not null default 'expected',
 uncertainty_level text not null default 'unknown',
 notes text,
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_finance_rebates_brand on finance_rebates(brand_id, status)")
        conn.execute(
            """
create table if not exists hr_performance_records(
 id integer primary key autoincrement,
 performance_id text unique,
 employee_id text,
 store_id text,
 period_start text,
 period_end text,
 sales_amount real not null default 0,
 gross_profit real not null default 0,
 gross_margin real not null default 0,
 tasks_completed integer not null default 0,
 customer_feedback_score real not null default 0,
 content_submissions integer not null default 0,
 training_completed integer not null default 0,
 attendance_status text,
 manager_review text,
 ai_evaluation text,
 status text not null default 'draft',
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_hr_performance_employee on hr_performance_records(employee_id, store_id, status)")
        conn.execute(
            """
create table if not exists hr_incentive_plans(
 id integer primary key autoincrement,
 incentive_plan_id text unique,
 plan_name text not null,
 plan_type text,
 store_id text,
 employee_id text,
 start_date text,
 end_date text,
 rule_description text,
 calculation_method text,
 target_sales real not null default 0,
 target_gross_profit real not null default 0,
 target_margin_rate real not null default 0,
 bonus_pool_rate real not null default 0,
 individual_weight real not null default 0,
 team_weight real not null default 0,
 break_even_sales real not null default 0,
 break_even_gross_profit real not null default 0,
 fixed_expenses real not null default 0,
 incentive_pool_rate real not null default 0,
 individual_allocation_rate real not null default 0,
 team_allocation_rate real not null default 0,
 carry_forward_rule text,
 notes text,
 status text not null default 'draft',
 created_by integer,
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_hr_incentive_plans_type on hr_incentive_plans(plan_type, status)")
        conn.execute(
            """
create table if not exists hr_training_records(
 id integer primary key autoincrement,
 training_id text unique,
 employee_id text,
 training_title text not null,
 training_type text,
 date text,
 result text,
 certificate text,
 notes text,
 created_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_hr_training_employee on hr_training_records(employee_id, date)")
        conn.execute(
            """
create table if not exists hr_growth_records(
 id integer primary key autoincrement,
 growth_id text unique,
 employee_id text,
 title text not null,
 description text,
 date text,
 related_store text,
 related_task text,
 related_performance text,
 created_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_hr_growth_employee on hr_growth_records(employee_id, date)")
        conn.execute(
            """
create table if not exists hr_candidates(
 id integer primary key autoincrement,
 candidate_id text unique,
 name text not null,
 phone text,
 target_position text,
 resume_file text,
 interview_status text,
 evaluation text,
 next_step text,
 created_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_hr_candidates_status on hr_candidates(interview_status)")
        conn.execute(
            """
create table if not exists customer_segments(
 id integer primary key autoincrement,
 segment_id text unique,
 segment_name text not null,
 description text,
 rules text,
 customer_count integer not null default 0,
 priority text,
 status text not null default 'draft',
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_customer_segments_status on customer_segments(status, priority)")
        conn.execute(
            """
create table if not exists customer_tags(
 id integer primary key autoincrement,
 tag_id text unique,
 tag_name text not null,
 tag_type text,
 description text,
 status text not null default 'active',
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_customer_tags_name on customer_tags(tag_name, status)")
        conn.execute(
            """
create table if not exists private_domain_groups(
 id integer primary key autoincrement,
 group_id text unique,
 group_name text not null,
 platform text,
 store_id text,
 owner_employee_id text,
 customer_count integer not null default 0,
 group_type text,
 topic text,
 status text not null default 'draft',
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_private_groups_store on private_domain_groups(store_id, status)")
        conn.execute(
            """
create table if not exists customer_followups(
 id integer primary key autoincrement,
 followup_id text unique,
 customer_id text,
 employee_id text,
 store_id text,
 followup_type text,
 content text,
 next_action text,
 due_date text,
 status text not null default 'todo',
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_customer_followups_status on customer_followups(status, due_date)")
        conn.execute(
            """
create table if not exists customer_events(
 id integer primary key autoincrement,
 event_id text unique,
 title text not null,
 store_id text,
 target_segments text,
 target_tags text,
 invitation_message text,
 status text not null default 'draft',
 created_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_customer_events_status on customer_events(status)")
        conn.execute(
            """
create table if not exists system_modules(
 id integer primary key autoincrement,
 module_id text unique,
 module_name text not null,
 module_key text not null,
 description text,
 route text,
 icon text,
 category text,
 status text not null default 'healthy',
 permission_required text,
 health_status text not null default 'healthy',
 version text,
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_system_modules_category on system_modules(category, status)")
        conn.execute(
            """
create table if not exists system_objects(
 id integer primary key autoincrement,
 object_type text unique,
 display_name text not null,
 plural_name text,
 route_pattern text,
 permission_scope text,
 searchable integer not null default 1,
 ai_accessible integer not null default 1,
 timeline_enabled integer not null default 1,
 audit_enabled integer not null default 1,
 created_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_system_objects_search on system_objects(searchable, ai_accessible)")
        conn.execute(
            """
create table if not exists system_settings(
 id integer primary key autoincrement,
 setting_key text unique,
 setting_value text,
 setting_group text,
 visibility text not null default 'admin',
 updated_by integer,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_system_settings_group on system_settings(setting_group)")
        conn.execute(
            """
create table if not exists system_risks(
 id integer primary key autoincrement,
 risk_id text unique,
 title text not null,
 risk_type text,
 level text not null default 'unknown',
 object_type text,
 object_id text,
 evidence text,
 recommended_action text,
 status text not null default 'new',
 owner text,
 due_date text,
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_system_risks_status on system_risks(status, level)")
        conn.execute(
            """
create table if not exists system_events(
 id integer primary key autoincrement,
 event_id text unique,
 event_type text not null,
 module_key text,
 object_type text,
 object_id text,
 title text not null,
 summary text,
 user_id integer,
 created_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_system_events_module on system_events(module_key, event_type)")
        conn.execute(
            """
create table if not exists sap_sync_history(
 id integer primary key autoincrement,
 sync_id text unique,
 job_name text not null default 'sap_b1_sync',
 trigger_type text,
 status text not null default 'pending',
 started_at integer,
 finished_at integer,
 duration_seconds real not null default 0,
 records_read integer not null default 0,
 records_written integer not null default 0,
 records_updated integer not null default 0,
 records_failed integer not null default 0,
 error_message text,
 log_path text,
 created_by integer
)
"""
        )
        conn.execute("create index if not exists idx_sap_sync_history_status on sap_sync_history(status, started_at)")
        conn.execute(
            """
create table if not exists job_locks(
 id integer primary key autoincrement,
 job_name text unique,
 lock_status text not null default 'free',
 locked_at integer,
 locked_by text,
 expires_at integer
)
"""
        )
        conn.execute(
            """
create table if not exists v5_items(
 id integer primary key autoincrement,
 item_id text unique,
 item_type text not null,
 title text not null,
 description text,
 status text not null default 'draft',
 priority text default 'normal',
 owner text,
 related_object_type text,
 related_object_id text,
 payload_json text,
 approval_status text default 'not_required',
 created_by integer,
 created_at integer not null,
 updated_at integer not null
)
"""
        )
        conn.execute("create index if not exists idx_v5_items_type on v5_items(item_type, status)")
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
.chat-shell{{display:grid;grid-template-columns:2fr 1fr;gap:14px;align-items:start}}.chat-message{{border:1px solid #e4ded2;border-radius:8px;padding:14px;margin:10px 0;background:#fff}}.chat-message.user{{background:#f2f6ff;border-color:#cad8ff}}.chat-message.assistant{{background:#fbfaf7}}.chat-input{{position:sticky;bottom:0;background:#f6f3ed;padding:10px 0 4px;border-top:1px solid #e5ded2}}.chipbar{{display:flex;gap:8px;overflow:auto;padding:4px 0 8px}}.chipbar button{{white-space:nowrap;width:auto;background:#fff;color:#1849a9;border:1px solid #cfd8ef}}.source-item{{border-top:1px solid #eee;padding:9px 0}}.confidence{{display:inline-block;border-radius:999px;background:#eef4ff;color:#1849a9;padding:5px 9px;font-weight:800}}
label{{display:block;font-weight:800;margin:12px 0 7px}}input,select,textarea{{width:100%;padding:14px;border:1px solid #cfc8bb;border-radius:8px;font-size:16px;background:#fff}}textarea{{min-height:120px;font-family:inherit}}
button,.btn{{display:inline-block;border:0;border-radius:8px;background:#1849a9;color:#fff;text-decoration:none;font-weight:800;padding:13px 16px;cursor:pointer;font-size:16px;text-align:center}}
.btn.full{{width:100%}}.red{{background:#ad1f15}}.green{{background:#18704c}}.dark{{background:#222}}.gray{{background:#777}}.orange{{background:#b45f06}}
.alert{{padding:12px;background:#fff7d6;border:1px solid #ecd27a;border-radius:8px;margin:12px 0}}table{{width:100%;border-collapse:collapse}}th,td{{border-bottom:1px solid #eee;padding:10px;text-align:left;vertical-align:top}}th{{white-space:nowrap}}.inline{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}.inline form{{display:inline}}.small{{font-size:13px;color:#666}}
@media(max-width:820px){{main{{width:calc(100% - 18px);padding-top:10px}}h1{{font-size:26px}}.grid,.metrics,.split,.chat-shell{{grid-template-columns:1fr;gap:12px}}.store-row{{grid-template-columns:1fr}}.card{{min-height:132px}}.btn,button{{width:100%;padding:15px}}.chipbar button{{width:auto}}.topbar{{align-items:flex-start;flex-direction:column}}.topbar a{{margin:0 12px 0 0}}table,tbody,tr,td,th{{display:block}}thead{{display:none}}tr{{border:1px solid #eee;border-radius:8px;margin:10px 0;padding:8px;background:#fff}}td{{border:0;padding:7px}}.inline{{display:block}}.inline form{{display:block;margin-top:8px}}}}
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
        if path == "/jarvis":
            return self.jarvis_center(user)
        if path == "/agents":
            return self.agents(user)
        if path == "/agents/collaboration":
            return self.agent_collaboration(user)
        if path in self.v5_page_routes():
            return self.v5_page(user, path)
        if path == "/sap-sync":
            return self.sap_sync(user)
        if path == "/data-pipeline":
            return self.data_pipeline_page(user)
        if path == "/apps":
            return self.apps_launcher(user)
        if path == "/desktop":
            return self.role_desktop(user)
        if path == "/command-center":
            return self.command_center(user)
        if path == "/work-queue":
            return self.work_queue_page(user)
        if path == "/approvals":
            return self.approvals_page(user)
        if path == "/system/upgrade":
            return self.system_upgrade_page(user)
        if path == "/documents":
            return self.document_center(user)
        if path == "/workflow":
            return self.workflow_center(user)
        if path == "/business-overview":
            return self.business_overview(user)
        if path == "/overview":
            return self.business_overview(user)
        if path == "/finance":
            return self.finance_center(user)
        if path == "/finance/store-profit":
            return self.finance_store_profit(user)
        if path == "/finance/brand-profit":
            return self.finance_brand_profit(user)
        if path == "/hr":
            return self.hr_center(user)
        if path == "/customer-growth":
            return self.customer_growth_center(user)
        if path == "/workspace":
            return self.workspace_center(user)
        if path == "/boss":
            return self.boss_workspace(user)
        if path == "/employee-workspace":
            return self.employee_workspace(user)
        if path == "/settings":
            return self.settings_center(user)
        if path == "/system/modules":
            return self.system_modules_page(user)
        if path == "/system/data-readiness":
            return self.data_readiness_page(user)
        if path == "/notifications":
            return self.notification_center(user)
        if path == "/risks":
            return self.risk_center(user)
        if path == "/timeline":
            return self.timeline_center(user)
        if path == "/stores/operations":
            return self.store_operations(user)
        if path == "/store-growth":
            return self.store_growth_center(user)
        if path == "/brands/operations":
            return self.brand_operations(user)
        if path == "/brand-growth":
            return self.brand_growth_center(user)
        if path == "/inventory/risk":
            return self.inventory_risk(user)
        if path == "/inventory-decision":
            return self.inventory_decision_center(user)
        if path == "/brands/osprey-inventory-decision":
            return self.osprey_inventory_decision(user)
        if path == "/brands/osprey-risk":
            return self.osprey_risk(user)
        if path == "/tasks":
            return self.task_center(user)
        if path == "/mobile":
            return self.mobile_center(user)
        if path == "/mobile/tasks":
            return self.mobile_tasks(user)
        if path == "/mobile/review":
            return self.mobile_review(user)
        if path == "/reports":
            return self.report_center(user)
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
        if path in ("/content", "/content-center"):
            return self.content_center(user)
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
        if path.startswith("/api/dashboard/"):
            return self.api_dashboard_get(user, path)
        if path == "/api/dashboard/ceo":
            return self.api_ceo_dashboard(user)
        if path.startswith("/api/inventory-decision"):
            return self.api_inventory_decision_get(user, path)
        if path.startswith("/api/finance"):
            return self.api_finance_get(user, path)
        if path.startswith("/api/hr"):
            return self.api_hr_get(user, path)
        if path.startswith("/api/customer-growth"):
            return self.api_customer_growth_get(user, path)
        if path.startswith("/api/system") or path.startswith("/api/search/global") or path.startswith("/api/workspace") or path.startswith("/api/boss") or path.startswith("/api/employee-workspace") or path.startswith("/api/settings") or path.startswith("/api/ai/context-packet") or path.startswith("/api/risks") or path.startswith("/api/timeline/global"):
            return self.api_platform_get(user, path)
        if path.startswith("/api/sap/sync") or path.startswith("/api/data-pipeline") or path.startswith("/api/system/data-freshness"):
            return self.api_sap_sync_get(user, path)
        if path.startswith("/api/apps") or path.startswith("/api/desktop") or path.startswith("/api/command-center") or path.startswith("/api/command-palette") or path.startswith("/api/object-actions") or path.startswith("/api/context-bar") or path.startswith("/api/work-queue") or path.startswith("/api/approvals") or path.startswith("/api/os/") or path.startswith("/api/system/upgrade"):
            return self.api_os_layer_get(user, path)
        if path.startswith("/api/ai-ceo") or path.startswith("/api/business") or path.startswith("/api/stores") or path.startswith("/api/brands") or path.startswith("/api/inventory") or path.startswith("/api/tasks"):
            return self.api_task005_get(user, path)
        if path.startswith("/api/automation") or path.startswith("/api/workflows") or path.startswith("/api/notifications"):
            return self.api_automation_get(user, path)
        if path.startswith("/api/memory") or path.startswith("/api/preferences") or path.startswith("/api/decisions"):
            return self.api_memory_get(user, path)
        if path.startswith("/api/graph"):
            return self.api_graph_get(user, path)
        if path.startswith("/api/agents"):
            return self.api_agents_get(user, path)
        if path.startswith("/api/jarvis"):
            return self.api_jarvis_get(user, path)
        if path.startswith("/api/reports") or path.startswith("/api/report-templates") or path.startswith("/api/report-schedules"):
            return self.api_reports_get(user, path)
        if path.startswith("/api/content"):
            return self.api_content_get(user, path)
        if path.startswith("/api/mobile") or path.startswith("/api/wecom"):
            return self.api_mobile_get(user, path)
        if path.startswith("/api/store-growth"):
            return self.api_store_growth_get(user, path)
        if path.startswith("/api/brand-growth"):
            return self.api_brand_growth_get(user, path)
        if path.startswith("/api/knowledge"):
            return self.api_knowledge_get(user, path)
        if path.startswith(("/api/operating-loop", "/api/strategy", "/api/digital-twin", "/api/kernel", "/api/data-fabric", "/api/data-sources", "/api/data-catalog", "/api/data-lineage", "/api/data-quality", "/api/data-freshness", "/api/data-ai-ready", "/api/data-access", "/api/integrations", "/api/security", "/api/operations", "/api/product", "/api/help", "/api/onboarding", "/api/feedback", "/api/action")):
            return self.api_v5_get(user, path)
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
        if path == "/jarvis/message":
            return self.jarvis_message_post()
        if path == "/jarvis/action":
            return self.jarvis_action_post()
        if path == "/reports/save":
            return self.report_save()
        if path == "/content/save":
            return self.content_save()
        if path == "/mobile/submissions/save":
            return self.mobile_submission_save()
        if path == "/mobile/tasks/complete":
            return self.mobile_task_complete()
        if path == "/store-growth/diagnosis/save":
            return self.store_growth_diagnosis_save()
        if path == "/store-growth/plans/save":
            return self.store_growth_plan_save()
        if path == "/store-growth/activities/save":
            return self.store_growth_activity_save()
        if path == "/store-growth/focus/save":
            return self.store_growth_focus_save()
        if path == "/brand-growth/diagnosis/save":
            return self.brand_growth_diagnosis_save()
        if path == "/brand-growth/strategies/save":
            return self.brand_growth_strategy_save()
        if path == "/brand-growth/portfolio/save":
            return self.brand_growth_portfolio_save()
        if path == "/brand-growth/pricing/save":
            return self.brand_growth_pricing_save()
        if path == "/inventory-decision/risks/save":
            return self.inventory_risk_save()
        if path == "/inventory-decision/replenishment/save":
            return self.replenishment_save()
        if path == "/inventory-decision/transfers/save":
            return self.transfer_suggestion_save()
        if path == "/inventory-decision/markdowns/save":
            return self.markdown_suggestion_save()
        if path == "/inventory-decision/future-orders/save":
            return self.future_order_save()
        if path == "/inventory-decision/purchasing-plans/save":
            return self.purchasing_plan_save()
        if path == "/finance/profit/save":
            return self.finance_profit_save()
        if path == "/finance/expenses/save":
            return self.finance_expense_save()
        if path == "/finance/rebates/save":
            return self.finance_rebate_save()
        if path == "/hr/performance/save":
            return self.hr_performance_save()
        if path == "/hr/incentive-plans/save":
            return self.hr_incentive_plan_save()
        if path == "/hr/training/save":
            return self.hr_training_save()
        if path == "/hr/growth-records/save":
            return self.hr_growth_save()
        if path == "/hr/candidates/save":
            return self.hr_candidate_save()
        if path == "/customer-growth/segments/save":
            return self.customer_segment_save()
        if path == "/customer-growth/tags/save":
            return self.customer_tag_save()
        if path == "/customer-growth/groups/save":
            return self.private_group_save()
        if path == "/customer-growth/followups/save":
            return self.customer_followup_save()
        if path == "/customer-growth/events/save":
            return self.customer_event_save()
        if path == "/risks/save":
            return self.risk_save()
        if path == "/notifications/read":
            return self.notification_read()
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
        if path.startswith("/api/inventory-decision"):
            return self.api_inventory_decision_post(self.current_user(), path)
        if path.startswith("/api/finance"):
            return self.api_finance_post(self.current_user(), path)
        if path.startswith("/api/hr"):
            return self.api_hr_post(self.current_user(), path)
        if path.startswith("/api/customer-growth"):
            return self.api_customer_growth_post(self.current_user(), path)
        if path.startswith("/api/notifications") or path.startswith("/api/settings") or path.startswith("/api/risks"):
            return self.api_platform_post(self.current_user(), path)
        if path.startswith("/api/sap/sync"):
            return self.api_sap_sync_post(self.current_user(), path)
        if path.startswith("/api/command-palette") or path.startswith("/api/approvals"):
            return self.api_os_layer_post(self.current_user(), path)
        if path.startswith("/api/ai-ceo") or path.startswith("/api/business") or path.startswith("/api/stores") or path.startswith("/api/brands") or path.startswith("/api/inventory") or path.startswith("/api/tasks"):
            return self.api_task005_post(self.current_user(), path)
        if path.startswith("/api/automation") or path.startswith("/api/workflows") or path.startswith("/api/notifications"):
            return self.api_automation_post(self.current_user(), path)
        if path.startswith("/api/memory") or path.startswith("/api/preferences") or path.startswith("/api/decisions"):
            return self.api_memory_post(self.current_user(), path)
        if path.startswith("/api/graph"):
            return self.api_graph_post(self.current_user(), path)
        if path.startswith("/api/hr"):
            return self.api_hr_put(self.current_user(), path)
        if path.startswith("/api/settings"):
            return self.api_platform_put(self.current_user(), path)
        if path.startswith("/api/agents"):
            return self.api_agents_post(self.current_user(), path)
        if path.startswith("/api/jarvis"):
            return self.api_jarvis_post(self.current_user(), path)
        if path.startswith("/api/reports") or path.startswith("/api/report-templates") or path.startswith("/api/report-schedules"):
            return self.api_reports_post(self.current_user(), path)
        if path.startswith("/api/content"):
            return self.api_content_post(self.current_user(), path)
        if path.startswith("/api/mobile") or path.startswith("/api/wecom"):
            return self.api_mobile_post(self.current_user(), path)
        if path.startswith("/api/store-growth"):
            return self.api_store_growth_post(self.current_user(), path)
        if path.startswith("/api/brand-growth"):
            return self.api_brand_growth_post(self.current_user(), path)
        if path.startswith("/api/knowledge"):
            return self.api_knowledge_post(self.current_user(), path)
        if path.startswith(("/api/operating-loop", "/api/strategy", "/api/digital-twin", "/api/kernel", "/api/data-fabric", "/api/data-sources", "/api/integrations", "/api/security", "/api/operations", "/api/product", "/api/feedback", "/api/action")):
            return self.api_v5_post(self.current_user(), path)
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
        if path.startswith("/api/agents"):
            return self.api_agents_post(self.current_user(), path)
        if path.startswith("/api/reports"):
            return self.api_reports_put(self.current_user(), path)
        if path.startswith("/api/content"):
            return self.api_content_put(self.current_user(), path)
        if path.startswith("/api/mobile"):
            return self.api_mobile_put(self.current_user(), path)
        if path.startswith("/api/store-growth"):
            return self.api_store_growth_put(self.current_user(), path)
        if path.startswith("/api/brand-growth"):
            return self.api_brand_growth_put(self.current_user(), path)
        if path.startswith(("/api/strategy", "/api/agents", "/api/digital-twin", "/api/kernel", "/api/data-fabric", "/api/integrations", "/api/security", "/api/operations", "/api/product", "/api/feedback", "/api/action")):
            return self.api_v5_post(self.current_user(), path)
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
            (U(r"SAP \u591c\u95f4\u540c\u6b65"), U(r"\u6bcf\u65e5\u56fa\u5b9a\u65f6\u95f4\u540c\u6b65 SAP B1 \u6458\u8981\u6570\u636e\uff0c\u5931\u8d25\u540e\u8bb0\u5f55\u65e5\u5fd7\u5e76\u53ef\u91cd\u8bd5\u3002"), "scheduled", [U(r"\u83b7\u53d6\u9501"), U(r"\u8bfb\u53d6 SAP"), U(r"\u5199\u5165\u6458\u8981"), U(r"\u8bb0\u5f55\u5ba1\u8ba1")]),
            (U(r"\u6bcf\u65e5\u7ecf\u8425\u65e5\u62a5"), U(r"\u57fa\u4e8e Dashboard \u6570\u636e\u670d\u52a1\u751f\u6210 CEO \u65e5\u62a5\u8349\u7a3f\u3002"), "scheduled", [U(r"\u8bfb\u53d6 KPI"), U(r"\u751f\u6210\u9884\u8b66"), U(r"\u751f\u6210 AI \u5efa\u8bae"), U(r"\u7b49\u5f85\u7ba1\u7406\u8005\u5ba1\u9605")]),
            (U(r"\u77e5\u8bc6\u5e93\u7d22\u5f15"), U(r"\u5bf9\u5df2\u4e0a\u4f20\u548c\u5df2\u5ba1\u6838\u77e5\u8bc6\u8fdb\u884c\u5206\u5757\u3001\u7d22\u5f15\u548c\u68c0\u7d22\u51c6\u5907\u3002"), "scheduled", [U(r"\u626b\u63cf\u77e5\u8bc6"), U(r"\u8865\u5145\u5143\u6570\u636e"), U(r"\u751f\u6210\u5206\u5757"), U(r"\u66f4\u65b0\u7d22\u5f15")]),
            (U(r"\u5ba1\u6279\u8def\u7531"), U(r"\u5c06\u4ef7\u683c\u3001\u5408\u540c\u3001\u8d22\u52a1\u3001\u5916\u90e8\u53d1\u5e03\u548c\u6279\u91cf\u6570\u636e\u53d8\u66f4\u9001\u5165\u4eba\u5de5\u5ba1\u6279\u3002"), "event", [U(r"\u68c0\u6d4b\u9ad8\u98ce\u9669"), U(r"\u751f\u6210\u5ba1\u6279\u5355"), U(r"\u901a\u77e5\u5ba1\u6279\u4eba"), U(r"\u5ba1\u6279\u540e\u6267\u884c")]),
            (U(r"\u5e93\u5b58\u9884\u8b66"), U(r"\u68c0\u6d4b\u4f4e\u5e93\u5b58\u3001\u6ede\u9500\u548c\u5e93\u5b58\u91d1\u989d\u5f02\u5e38\u3002"), "inventory_threshold", [U(r"\u8bfb\u53d6\u5e93\u5b58"), U(r"\u751f\u6210\u9884\u8b66"), U(r"\u751f\u6210\u8865\u8d27\u6216\u8c03\u62e8\u5efa\u8bae"), U(r"\u4eba\u5de5\u5ba1\u6838")]),
            (U(r"\u5ba2\u6237\u8ddf\u8fdb\u63d0\u9192"), U(r"\u68c0\u6d4b\u9ad8\u4ef7\u503c\u6c89\u9ed8\u4f1a\u5458\u5e76\u63d0\u9192\u95e8\u5e97\u8ddf\u8fdb\u3002"), "scheduled", [U(r"\u8bfb\u53d6\u4f1a\u5458"), U(r"\u8bc6\u522b\u6c89\u9ed8"), U(r"\u751f\u6210\u8ddf\u8fdb\u4efb\u52a1"), U(r"\u901a\u77e5\u95e8\u5e97")]),
            (U(r"\u5408\u540c\u5230\u671f\u63d0\u9192"), U(r"\u5bf9\u4f9b\u5e94\u5546\u5408\u540c\u548c\u623f\u79df\u7b49\u91cd\u8981\u5408\u540c\u63d0\u524d\u9884\u8b66\u3002"), "scheduled", [U(r"\u626b\u63cf\u5408\u540c"), U(r"\u8ba1\u7b97\u5230\u671f"), U(r"\u751f\u6210\u9884\u8b66"), U(r"\u8def\u7531\u5ba1\u6279")]),
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

    def automation_is_high_risk(self, action_type, name="", description=""):
        text = " ".join([str(action_type or ""), str(name or ""), str(description or "")]).lower()
        high_risk_terms = [
            "price", "pricing", "discount", "contract", "finance", "payment", "payable",
            "sap_write", "external_publish", "publish", "bulk", "batch", "delete",
            U(r"\u4ef7\u683c"), U(r"\u6298\u6263"), U(r"\u5408\u540c"), U(r"\u8d22\u52a1"), U(r"\u4ed8\u6b3e"), U(r"\u5916\u90e8\u53d1\u5e03"), U(r"\u6279\u91cf"),
        ]
        return any(term.lower() in text for term in high_risk_terms)

    def automation_framework_payload(self, user):
        data = self.automation_summary()
        return {
            "ok": True,
            "platform": "enterprise_automation_framework",
            "pack_alignment": ["Pack01 foundation", "Pack02 SAP AI", "Pack03 knowledge", "Pack04 agents", "Pack05 dashboard", "Pack06 automation"],
            "objectives": ["eliminate_repetitive_work", "standardize_approval_workflows", "scheduled_and_event_driven_automation", "human_approval_for_high_risk_actions"],
            "scheduler": self.automation_scheduler_payload()["scheduler"],
            "retry_policy": self.automation_retry_policy_payload()["retry_policy"],
            "approval_policy": self.automation_approval_policy_payload()["approval_policy"],
            "notification_center": self.automation_notification_payload(user)["notification_center"],
            "audit": self.automation_audit_payload()["audit"],
            "workflow_library": self.automation_workflow_library_payload(user)["workflow_library"],
            "summary": {"running": data["running"], "pending": data["pending"], "failed": data["failed"]},
        }

    def automation_scheduler_payload(self):
        return {
            "ok": True,
            "scheduler": {
                "supports": ["cron_schedules", "event_triggers", "retry_policy", "failure_notifications", "audit_history"],
                "cron_jobs": {
                    "sap_nightly_sync": os.environ.get("SAP_SYNC_TIME", "22:00"),
                    "knowledge_indexing": os.environ.get("KNOWLEDGE_INDEX_TIME", "02:00"),
                    "daily_business_report": os.environ.get("DAILY_REPORT_TIME", "08:00"),
                    "backup": os.environ.get("BACKUP_TIME", "03:00"),
                },
                "event_triggers": ["sap_data_change", "document_uploaded", "knowledge_approved", "inventory_threshold", "sales_threshold", "approval_decided"],
                "execution_rule": "scheduled_jobs_create_logs_and_never_bypass_approval",
            },
        }

    def automation_retry_policy_payload(self):
        return {
            "ok": True,
            "retry_policy": {
                "default_max_retries": 3,
                "backoff": "linear_5m_15m_30m",
                "retryable_statuses": ["failed", "timeout", "temporary_error"],
                "non_retryable_statuses": ["blocked_by_approval", "permission_denied", "validation_failed"],
                "failure_notification": True,
                "audit_each_attempt": True,
            },
        }

    def automation_approval_policy_payload(self):
        return {
            "ok": True,
            "approval_policy": {
                "required_for": ["price_changes", "financial_operations", "contract_execution", "external_publishing", "bulk_data_changes", "sap_write_back"],
                "default_for_high_risk": "pending_approval",
                "execution_rule": "high_risk_operations_are_never_auto_executed",
                "review_roles": ["boss", "admin", "finance"],
                "linked_agent_policy": "/api/agents/approval-policy",
            },
        }

    def automation_notification_payload(self, user):
        data = self.automation_summary()
        return {
            "ok": True,
            "notification_center": {
                "channels": ["in_app", "email", "enterprise_messaging_future", "mobile_push_future"],
                "failure_notifications": True,
                "approval_notifications": True,
                "notifications": [row_dict(r) for r in data["notifications"]],
            },
        }

    def automation_audit_payload(self):
        return {
            "ok": True,
            "audit": {
                "log_tables": ["automation_runs", "activity_log"],
                "events": ["automation_created", "automation_scheduled", "automation_started", "automation_failed", "automation_retried", "approval_requested", "approval_decided", "automation_completed"],
                "required_fields": ["automation_id", "run_id", "user_id", "status", "attempt_no", "message", "timestamp"],
                "rule": "every_automation_run_and_retry_must_be_audited",
            },
        }

    def automation_workflow_library_payload(self, user):
        data = self.automation_summary()
        return {
            "ok": True,
            "workflow_library": {
                "initial_workflows": ["SAP nightly sync", "Daily business report", "Knowledge indexing", "Approval routing", "Inventory alert", "Customer follow-up reminder", "Contract expiry reminder"],
                "templates": [row_dict(r) for r in data["templates"]],
            },
        }

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
        if user["role"] not in ("boss", "admin", "finance", "purchasing"):
            return self.dashboard(user)
        s = load_summary()
        status = self.sap_sync_status_payload()
        history_items = [h["sync_id"] + " · " + h["trigger_type"] + " · " + h["status"] for h in status["history"][:10]] or [U(r"\u6682\u65e0 SAP \u540c\u6b65\u5386\u53f2\u3002")]
        body = f"""
<div class="panel">
  <h2>SAP B1 {U(r'\u540c\u6b65\u72b6\u6001')}</h2>
  <div class="metrics">
    {self.metric(U(r'\u6570\u636e\u65e5\u671f'), s.get('data_date'), status['freshness'])}
    {self.metric(U(r'\u6628\u65e5\u9500\u552e'), U(r'\uffe5') + money(s.get('yesterday_sales')), U(r'SAP B1'))}
    {self.metric(U(r'\u5e93\u5b58\u91d1\u989d'), U(r'\uffe5') + money(s.get('inventory_amount')), U(r'\u5df2\u540c\u6b65'))}
    {self.metric(U(r'\u4e0a\u6b21\u540c\u6b65'), status['last_sync_time'], status['last_status'])}
    {self.metric(U(r'\u4e0b\u6b21\u540c\u6b65'), status['next_run_time'], U(r'\u6bcf\u665a 22:00'))}
  </div>
  <p class="small">{status['warning']}</p>
  <form method="post" action="/api/sap/sync/run"><button>{U(r'\u7acb\u5373\u540c\u6b65 SAP \u6570\u636e')}</button></form>
</div>
<div class="split">
  <div class="panel"><h2>{U(r'\u540c\u6b65\u5386\u53f2')}</h2>{self.bullets(history_items)}</div>
  <div class="panel"><h2>{U(r'\u914d\u7f6e\u72b6\u6001')}</h2>{self.bullets(status['config_status'])}</div>
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
            self.card(U(r"\u6bcf\u65e5\u884c\u52a8\u677f"), U(r"\u4eca\u5929\u8981\u51b3\u7b56\u3001\u8981\u6267\u884c\u3001\u8981\u590d\u76d8\u7684\u4e8b\u9879\u3002"), "/action/today", "btn dark", True),
            self.card(U(r"\u7ecf\u8425\u95ed\u73af"), U(r"SAP \u540c\u6b65\u3001AI \u6668\u62a5\u3001\u98ce\u9669\u3001\u4efb\u52a1\u3001\u665a\u95f4\u590d\u76d8\u3002"), "/operating-loop", "btn", can_boss),
            self.card(U(r"\u7ecf\u8425\u51b3\u7b56\u4e2d\u5fc3"), U(r"\u628a\u98ce\u9669\u3001\u6a21\u62df\u3001\u667a\u80fd\u4f53\u610f\u89c1\u8f6c\u6210\u53ef\u5ba1\u6279\u51b3\u7b56\u3002"), "/decision-center", "btn", can_boss),
            self.card(U(r"\u4f01\u4e1a\u6570\u5b57\u5b6a\u751f"), U(r"\u95e8\u5e97\u3001\u5458\u5de5\u3001\u54c1\u724c\u3001\u4ea7\u54c1\u3001\u4f9b\u5e94\u5546\u548c\u9879\u76ee\u5173\u7cfb\u3002"), "/digital-twin", "btn green", can_manager),
            self.card(U(r"AI \u603b\u7ecf\u7406"), U(r"\u6253\u5f00 AI \u603b\u7ecf\u7406\u6668\u62a5\uff0c\u67e5\u770b\u9500\u552e\u3001\u6bdb\u5229\u3001\u5e93\u5b58\u548c\u7ecf\u8425\u5efa\u8bae\u3002"), "/ai-ceo", "btn", can_boss),
            self.card(U(r"AI \u667a\u80fd\u4f53"), U(r"\u667a\u80fd\u4f53\u5e02\u573a\u3001\u5de5\u4f5c\u6d41\u3001\u884c\u52a8\u8ba1\u5212\u548c\u4eba\u5de5\u5ba1\u6279\u3002"), "/agents/runtime", "btn", can_manager),
            self.card(U(r"AI \u8bb0\u5fc6\u4e2d\u5fc3"), U(r"\u8bb0\u4f4f\u957f\u671f\u7ecf\u8425\u610f\u56fe\u3001\u5386\u53f2\u51b3\u7b56\u3001\u9879\u76ee\u8fdb\u5c55\u548c\u98ce\u9669\u63d0\u9192\u3002"), "/ai-memory", "btn", can_boss),
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
            self.card(U(r"\u624b\u673a\u4e00\u7ebf\u8fd0\u8425"), U(r"\u5458\u5de5\u624b\u673a\u62cd\u7167\u3001\u63d0\u4ea4\u95e8\u5e97\u8bb0\u5f55\u3001\u987e\u5ba2\u53cd\u9988\u3001\u5e93\u5b58\u95ee\u9898\u548c\u7ade\u54c1\u89c2\u5bdf\u3002"), "/mobile", "btn green", True),
            self.card(U(r"\u62a5\u544a\u4e2d\u5fc3"), U(r"AI \u65e5\u62a5\u3001\u5468\u62a5\u3001\u6708\u62a5\u3001\u95e8\u5e97\u62a5\u544a\u548c\u5e93\u5b58\u98ce\u9669\u62a5\u544a\u8349\u7a3f\u3002"), "/reports", "btn orange", can_manager),
            self.card(U(r"AI \u81ea\u52a8\u5316"), U(r"\u6d41\u7a0b\u6a21\u677f\u3001\u89e6\u53d1\u5668\u3001AI \u52a8\u4f5c\u3001\u6267\u884c\u5386\u53f2\u548c\u901a\u77e5\u4e2d\u5fc3\u3002"), "/automation", "btn", can_manager),
            self.card(U(r"AI \u8bb0\u5fc6\u4e2d\u5fc3"), U(r"\u957f\u671f\u7ecf\u8425\u539f\u5219\u3001\u51b3\u7b56\u3001\u504f\u597d\u3001\u5b9a\u4ef7\u548c\u98ce\u9669\u8bb0\u5fc6\u3002"), "/memory", "btn", True),
            self.card(U(r"\u4f01\u4e1a\u77e5\u8bc6\u56fe\u8c31"), U(r"\u8fde\u63a5\u95e8\u5e97\u3001\u54c1\u724c\u3001\u4ea7\u54c1\u3001\u77e5\u8bc6\u3001\u8bb0\u5fc6\u3001\u4efb\u52a1\u548c\u98ce\u9669\u3002"), "/graph", "btn green", can_manager),
            self.card(U(r"\u591a\u667a\u80fd\u4f53\u534f\u540c"), U(r"AI CEO\u3001CFO\u3001\u5e93\u5b58\u3001\u54c1\u724c\u3001\u95e8\u5e97\u7b49\u667a\u80fd\u4f53\u534f\u540c\u5206\u6790\u3002"), "/agents/collaboration", "btn", can_manager),
            self.card(U(r"\u95e8\u5e97\u589e\u957f\u5f15\u64ce"), U(r"\u95e8\u5e97\u8bca\u65ad\u3001\u589e\u957f\u8ba1\u5212\u3001\u6d3b\u52a8\u3001\u4efb\u52a1\u6267\u884c\u548c\u590d\u76d8\u62a5\u544a\u3002"), "/store-growth", "btn green", can_manager),
            self.card(U(r"\u54c1\u724c\u589e\u957f\u5f15\u64ce"), U(r"\u54c1\u724c\u89d2\u8272\u3001\u4ea7\u54c1\u7ec4\u5408\u3001\u5b9a\u4ef7\u98ce\u9669\u3001\u5e93\u5b58\u77e9\u9635\u548c Osprey \u6298\u6263\u8bd5\u7b97\u3002"), "/brand-growth", "btn", can_manager),
            self.card(U(r"\u5e93\u5b58\u91c7\u8d2d\u51b3\u7b56"), U(r"\u8865\u8d27\u3001\u8c03\u8d27\u3001\u964d\u4ef7\u3001\u6e05\u8d27\u3001\u671f\u8d27\u548c\u91c7\u8d2d\u51b3\u7b56\u6846\u67b6\u3002"), "/inventory-decision", "btn dark", can_manager),
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
            self.card("FoxBrain Jarvis", U(r"\u7edf\u4e00 AI \u603b\u7ba1\u5165\u53e3\uff1a\u76f4\u63a5\u95ee\u7ecf\u8425\u3001SAP\u3001\u77e5\u8bc6\u5e93\u3001\u4efb\u52a1\u548c\u667a\u80fd\u4f53\u534f\u540c\u3002"), "/jarvis", "btn", True),
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

    def api_ceo_dashboard(self, user):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        s = load_summary()
        return self.json_out({
            "ok": True,
            "dashboard": "ceo",
            "sales": {
                "yesterday_sales": s.get("yesterday_sales", 0),
                "month_sales": s.get("month_sales", 0),
                "completion_rate": s.get("completion_rate", 0),
            },
            "gross_profit": {
                "month_gross_profit": s.get("month_gross_profit", 0),
                "gross_margin": s.get("yesterday_gross_margin", 0),
            },
            "inventory_alerts": {
                "inventory_amount": s.get("inventory_amount", 0),
                "risk_count": s.get("risk_count", 0),
            },
            "pending_approvals": self.os_approvals_payload(user)["approvals"][:10],
            "sync_status": self.sap_sync_status_payload(),
            "ai_recommendations": s.get("ai_suggestions", []),
            "limitations": [U(r"\u4eea\u8868\u76d8\u4ec5\u5f15\u7528\u5df2\u63a5\u5165\u7684 SAP \u6458\u8981\u548c\u672c\u5730\u6570\u636e\uff0c\u4e0d\u7f16\u9020\u7ecf\u8425\u4e8b\u5b9e\u3002")],
        })

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

    def knowledge_platform_payload(self, user):
        with db() as conn:
            total = conn.execute("select count(*) c from knowledge_items where deleted_at is null").fetchone()["c"]
            chunks = conn.execute("select count(*) c from knowledge_chunks").fetchone()["c"]
            pending = conn.execute("select count(*) c from knowledge_items where deleted_at is null and status in ('uploaded','draft','summarized','pending_review')").fetchone()["c"]
        return {
            "ok": True,
            "platform": "enterprise_knowledge_platform",
            "stability_policy": "additive_only_preserve_existing_features",
            "pack_alignment": ["Pack01 foundation", "Pack02 SAP AI framework", "Pack03 knowledge platform"],
            "document_center": {
                "upload": "ready",
                "auto_parse": "framework_ready",
                "ai_summary": "rule_based_placeholder",
                "ai_category": "rule_based_placeholder",
            },
            "retrieval": {
                "keyword_search": "ready",
                "semantic_search": "qdrant_contract_ready",
                "hybrid_search": "contract_ready",
                "citations_required": True,
                "permission_enforced": True,
            },
            "governance": self.knowledge_governance_payload()["governance"],
            "knowledge_graph": self.knowledge_graph_contract_payload()["knowledge_graph"],
            "ai_access": {
                "agents": ["AI CEO", "AI CFO", "AI Store Manager", "AI Inventory Manager", "AI Product Manager", "AI Customer Service", "AI HR"],
                "entry": "/jarvis",
                "answer_rule": "answer_with_citations_and_limitations",
            },
            "metrics": {
                "knowledge_items": total,
                "chunks": chunks,
                "pending_review": pending,
                "worker_time": os.environ.get("KNOWLEDGE_INDEX_TIME", "02:00"),
            },
            "user": {"id": user["id"], "role": user["role"], "store": user["store"]},
        }

    def knowledge_governance_payload(self):
        return {
            "ok": True,
            "governance": {
                "required_metadata": ["owner", "department", "tags", "version", "visibility", "retention_policy"],
                "visibility_levels": ["public_internal", "manager_only", "finance_only", "owner_only", "restricted"],
                "lifecycle": ["uploaded", "parsed", "summarized", "pending_review", "ready", "archived", "deleted_recoverable"],
                "retention_policies": ["standard", "finance", "hr", "contract", "training"],
                "delete_policy": "soft_delete_recoverable",
                "approval_policy": "external_research_and_sensitive_documents_need_human_review",
                "audit_log": "activity_log",
            },
        }

    def knowledge_retrieval_contract_payload(self):
        return {
            "ok": True,
            "retrieval_contract": {
                "query_inputs": ["question", "scope", "role", "store", "object_type", "object_id"],
                "search_modes": ["keyword", "semantic", "hybrid"],
                "ranking_signals": ["permission", "title_match", "semantic_score", "recency", "source_quality"],
                "response_fields": ["answer", "citations", "limitations", "follow_up_actions"],
                "citation_fields": ["title", "url", "knowledge_id", "chunk_id", "source_ref"],
                "permission_rule": "filter_sources_before_answer_generation",
                "no_answer_rule": "state_missing_source_do_not_invent",
                "reindex": {"manual": True, "scheduled_time": os.environ.get("KNOWLEDGE_INDEX_TIME", "02:00")},
            },
        }

    def knowledge_graph_contract_payload(self):
        return {
            "ok": True,
            "knowledge_graph": {
                "entities": ["products", "brands", "stores", "employees", "customers", "suppliers", "contracts", "training", "meetings", "knowledge"],
                "relationships": ["belongs_to", "supplied_by", "sold_in", "trained_by", "mentions", "documented_by", "approved_by"],
                "ai_queryable": True,
                "source_module": "knowledge_center",
                "build_status": "framework_ready",
            },
        }

    def api_knowledge_get(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if path == "/api/knowledge/platform":
            return self.json_out(self.knowledge_platform_payload(user))
        if path == "/api/knowledge/ingestion/status":
            return self.json_out({
                "ok": True,
                "service": "knowledge_ingestion",
                "pipeline": ["upload", "ocr_if_needed", "metadata", "chunking", "embedding", "index", "permission", "search"],
                "supported_formats": ["pdf", "word", "excel", "powerpoint", "images", "markdown", "txt"],
                "planned_formats": ["audio", "video"],
                "ocr_status": "interface_ready",
                "semantic_search": "qdrant_foundation_ready",
                "metadata": "ready",
                "version_history": "framework_ready",
                "access_control": "visibility_and_role_based",
                "worker_job": os.environ.get("KNOWLEDGE_INDEX_TIME", "02:00"),
                "policy": "Human review required before external research becomes formal knowledge.",
            })
        if path == "/api/knowledge/governance":
            return self.json_out(self.knowledge_governance_payload())
        if path == "/api/knowledge/retrieval-contract":
            return self.json_out(self.knowledge_retrieval_contract_payload())
        if path == "/api/knowledge/graph-contract":
            return self.json_out(self.knowledge_graph_contract_payload())
        if path in ("/api/knowledge", "/api/knowledge/search"):
            query = parse_qs(urlparse(self.path).query)
            q = query.get("q", [""])[0].strip()
            params = []
            sql = "select * from knowledge_items where deleted_at is null"
            if q:
                like = "%" + q + "%"
                sql += " and (title like ? or body like ? or summary like ? or keywords like ? or tags like ?)"
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

    def dashboard_kpi_service_payload(self, user, scope="company"):
        data = self.cockpit_data()
        m = data["metrics"]
        sap = self.sap_sync_status_payload()
        return {
            "ok": True,
            "service": "dashboard_kpi_service",
            "scope": scope,
            "data_source": "unified_data_service",
            "business_data_only": True,
            "freshness": {
                "sap": sap["freshness"],
                "last_sync_time": sap["last_sync_time"],
                "next_run_time": sap["next_run_time"],
                "data_date": m["data_date"],
            },
            "kpis": {
                "sales": {
                    "today_sales": m["today_sales"],
                    "yesterday_sales": m["yesterday_sales"],
                    "month_sales": m["month_sales"],
                    "completion_rate": m["completion_rate"],
                },
                "profit": {
                    "gross_profit": m["gross_profit"],
                    "gross_margin": m["gross_margin"],
                    "cash_flow_summary": "pending_real_finance_sync",
                },
                "inventory": {
                    "inventory_amount": m["inventory_amount"],
                    "risk_count": m["risk_count"],
                },
                "stores": {
                    "ranking": data["top_stores"],
                    "scope_rule": "store_manager_only_authorized_store",
                },
                "brands": {
                    "ranking": data["top_brands"],
                },
            },
            "limitations": [data["empty_message"]] if not data["has_data"] else [],
        }

    def dashboard_alert_service_payload(self, user, scope="company"):
        data = self.cockpit_data()
        m = data["metrics"]
        sap = self.sap_sync_status_payload()
        alerts = []
        if (m["risk_count"] or 0):
            alerts.append({
                "alert_id": "inventory-risk",
                "type": "inventory",
                "level": "warning",
                "title": U(r"\u5e93\u5b58\u98ce\u9669\u63d0\u9192"),
                "message": U(r"\u5b58\u5728\u5e93\u5b58\u98ce\u9669\u6570\u91cf\uff0c\u9700\u8981\u68c0\u67e5\u6ede\u9500\u3001\u5c3a\u7801\u7ed3\u6784\u548c\u8c03\u62e8\u673a\u4f1a\u3002"),
                "evidence": [{"source": "summary", "field": "risk_count", "value": m["risk_count"]}],
                "approval_required": False,
            })
        if sap["last_status"] in ("failed", "error"):
            alerts.append({
                "alert_id": "sap-sync-failure",
                "type": "sync",
                "level": "critical",
                "title": U(r"SAP \u540c\u6b65\u5f02\u5e38"),
                "message": U(r"\u9a7e\u9a76\u8231\u6570\u636e\u53ef\u80fd\u4e0d\u65b0\u9c9c\uff0c\u9700\u5148\u5904\u7406 SAP \u540c\u6b65\u3002"),
                "evidence": [{"source": "sap_sync_status", "field": "last_status", "value": sap["last_status"]}],
                "approval_required": False,
            })
        if not data["has_data"]:
            alerts.append({
                "alert_id": "missing-business-data",
                "type": "data",
                "level": "info",
                "title": U(r"\u7b49\u5f85\u7ecf\u8425\u6570\u636e"),
                "message": data["empty_message"],
                "evidence": [{"source": "dashboard_kpi_service", "field": "has_data", "value": False}],
                "approval_required": False,
            })
        return {
            "ok": True,
            "service": "dashboard_alert_service",
            "scope": scope,
            "component": "alerts",
            "decoupled_from_business_data": True,
            "alert_types": ["low_inventory", "abnormal_margin", "sync_failures", "expiring_contracts", "high_value_inactive_customers"],
            "alerts": alerts,
            "high_risk_actions_require_approval": True,
        }

    def dashboard_recommendation_service_payload(self, user, scope="company"):
        data = self.cockpit_data()
        m = data["metrics"]
        suggestions = []
        raw = data["ai_suggestions"][:5]
        for idx, text in enumerate(raw, 1):
            suggestions.append({
                "recommendation_id": f"ai-summary-{idx}",
                "title": str(text),
                "basis": [{"source": "dashboard_summary", "field": "ai_suggestions", "value": str(text)}],
                "risk_level": "medium",
                "approval_required": True,
                "review_note": U(r"\u7ecf\u8425\u5efa\u8bae\u9700\u7ba1\u7406\u8005\u6838\u5bf9\u4f9d\u636e\u540e\u518d\u6267\u884c\u3002"),
            })
        if not suggestions:
            suggestions.append({
                "recommendation_id": "data-first",
                "title": U(r"\u5148\u786e\u4fdd SAP B1 \u6bcf\u65e5\u540c\u6b65\u7a33\u5b9a\uff0c\u518d\u751f\u6210\u7ecf\u8425\u5efa\u8bae\u3002"),
                "basis": [
                    {"source": "sap_sync_status", "field": "next_run_time", "value": self.sap_sync_status_payload()["next_run_time"]},
                    {"source": "dashboard_kpi_service", "field": "data_date", "value": m["data_date"]},
                ],
                "risk_level": "low",
                "approval_required": False,
                "review_note": U(r"\u8fd9\u662f\u6570\u636e\u57fa\u7840\u5efa\u8bae\uff0c\u4e0d\u6d89\u53ca\u4ef7\u683c\u3001\u5408\u540c\u6216\u8d22\u52a1\u6267\u884c\u3002"),
            })
        return {
            "ok": True,
            "service": "dashboard_recommendation_service",
            "scope": scope,
            "component": "ai_recommendations",
            "decoupled_from_business_data": True,
            "recommendations": suggestions,
            "rule": "business_recommendations_must_show_basis_for_manager_review",
        }

    def dashboard_service_payload(self, user, dashboard_type="ceo"):
        kpis = self.dashboard_kpi_service_payload(user, dashboard_type)
        alerts = self.dashboard_alert_service_payload(user, dashboard_type)
        recommendations = self.dashboard_recommendation_service_payload(user, dashboard_type)
        widgets = {
            "ceo": ["sales", "profit", "cash_flow_summary", "inventory_alerts", "store_ranking", "pending_approvals", "ai_recommendations", "sap_sync_health"],
            "finance": ["revenue", "margin", "receivables", "payables", "cash_trend", "exception_alerts"],
            "store": ["daily_sales", "conversion", "inventory_health", "staff_performance", "customer_activity", "suggested_replenishment"],
        }.get(dashboard_type, ["sales", "alerts", "recommendations"])
        return {
            "ok": True,
            "dashboard": dashboard_type,
            "data_service": {
                "name": "unified_dashboard_data_service",
                "sources": ["sap_summary", "local_database", "knowledge_platform", "agent_framework"],
                "kpi_endpoint": "/api/dashboard/kpis",
                "alerts_endpoint": "/api/dashboard/alerts",
                "recommendations_endpoint": "/api/dashboard/recommendations",
            },
            "widgets": widgets,
            "business_data": kpis["kpis"],
            "alerts_component": alerts,
            "recommendations_component": recommendations,
            "pending_approvals": self.os_approvals_payload(user)["approvals"][:10],
            "sync_status": self.sap_sync_status_payload(),
            "separation_rule": "ai_recommendations_and_alerts_are_independent_components_not_mixed_into_raw_business_data",
        }

    def api_dashboard_get(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if path == "/api/dashboard/service":
            return self.json_out(self.dashboard_service_payload(user, "ceo"))
        if path == "/api/dashboard/kpis":
            return self.json_out(self.dashboard_kpi_service_payload(user))
        if path == "/api/dashboard/alerts":
            return self.json_out(self.dashboard_alert_service_payload(user))
        if path == "/api/dashboard/recommendations":
            return self.json_out(self.dashboard_recommendation_service_payload(user))
        if path == "/api/dashboard/ceo":
            return self.json_out(self.dashboard_service_payload(user, "ceo"))
        if path == "/api/dashboard/finance":
            if not self.can_view_finance(user):
                return self.json_out({"ok": False, "message": "no permission"}, code=403)
            return self.json_out(self.dashboard_service_payload(user, "finance"))
        if path == "/api/dashboard/store":
            if user["role"] not in ("boss", "admin", "store_manager"):
                return self.json_out({"ok": False, "message": "no permission"}, code=403)
            return self.json_out(self.dashboard_service_payload(user, "store"))
        return self.json_out({"ok": False, "message": "unknown dashboard api"}, code=404)

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

    def can_view_finance(self, user):
        return bool(user and user["role"] in ("boss", "admin", "finance"))

    def can_manage_finance(self, user):
        return bool(user and user["role"] in ("boss", "admin", "finance"))

    def finance_empty(self):
        return U(r"\u7b49\u5f85 SAP B1 \u6216\u8d22\u52a1\u6570\u636e\u540c\u6b65\u540e\u751f\u6210\u771f\u5b9e\u5229\u6da6\u548c\u73b0\u91d1\u6d41\u5206\u6790\u3002")

    def finance_overview_payload(self):
        with db() as conn:
            profit_count = conn.execute("select count(*) c from finance_profit_records").fetchone()["c"]
            expense_total = conn.execute("select coalesce(sum(amount),0) v from finance_expenses").fetchone()["v"]
            rebate_expected = conn.execute("select coalesce(sum(expected_rebate),0) v from finance_rebates").fetchone()["v"]
            rebate_actual = conn.execute("select coalesce(sum(actual_rebate),0) v from finance_rebates").fetchone()["v"]
            recent_profit = [row_dict(r) for r in conn.execute("select * from finance_profit_records order by updated_at desc limit 10").fetchall()]
            recent_expenses = [row_dict(r) for r in conn.execute("select * from finance_expenses order by updated_at desc limit 10").fetchall()]
            recent_rebates = [row_dict(r) for r in conn.execute("select * from finance_rebates order by updated_at desc limit 10").fetchall()]
        return {
            "ok": True,
            "empty_message": self.finance_empty(),
            "summary": {
                "profit_record_count": profit_count,
                "expense_total": expense_total,
                "expected_rebate": rebate_expected,
                "actual_rebate": rebate_actual,
            },
            "profit_records": recent_profit,
            "expenses": recent_expenses,
            "rebates": recent_rebates,
            "decision_sections": ["profit", "store_profit", "brand_profit", "expenses", "cashflow", "rebates", "discount_impact", "break_even"],
        }

    def finance_center(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_view_finance(user):
            return self.dashboard(user)
        data = self.finance_overview_payload()
        s = data["summary"]
        metrics = "".join([
            self.metric(U(r"\u5229\u6da6\u8bb0\u5f55"), money(s["profit_record_count"]), U(r"\u5df2\u5efa\u7acb\u7684\u5206\u6790\u6a21\u578b")),
            self.metric(U(r"\u8d39\u7528\u5408\u8ba1"), U(r"\uffe5") + money(s["expense_total"]), U(r"\u624b\u5de5/\u540c\u6b65\u6570\u636e")),
            self.metric(U(r"\u9884\u671f\u8fd4\u70b9"), U(r"\uffe5") + money(s["expected_rebate"]), U(r"\u9700\u5ba1\u6838\u4e0d\u786e\u5b9a\u6027")),
            self.metric(U(r"\u5df2\u5230\u8fd4\u70b9"), U(r"\uffe5") + money(s["actual_rebate"]), U(r"\u4ee5\u8d22\u52a1\u786e\u8ba4\u4e3a\u51c6")),
        ])
        profit_items = [r["object_type"] + " · " + str(r["object_id"]) + " · " + money(r["net_profit"]) for r in data["profit_records"]] or [self.finance_empty()]
        expense_items = [r["expense_type"] + " · " + money(r["amount"]) + " · " + (r["period"] or "") for r in data["expenses"]] or [U(r"\u6682\u65e0\u8d39\u7528\u8bb0\u5f55\u3002")]
        rebate_items = [r["brand_id"] + " · " + money(r["expected_rebate"]) + " · " + r["status"] for r in data["rebates"]] or [U(r"\u6682\u65e0\u8fd4\u70b9\u8bb0\u5f55\u3002")]
        body = f"""
<div class="panel"><h2>{U(r'\u8d22\u52a1\u4e0e\u5229\u6da6\u51b3\u7b56\u4e2d\u5fc3')}</h2><p class="small">{U(r'\u5e2e\u8001\u677f\u770b\u6e05\u5229\u6da6\u3001\u8d39\u7528\u3001\u73b0\u91d1\u6d41\u3001\u8fd4\u70b9\u548c\u6298\u6263\u98ce\u9669\u3002\u65e0\u6570\u636e\u65f6\u53ea\u663e\u793a\u6a21\u677f\uff0c\u4e0d\u7f16\u9020\u8d22\u52a1\u7ed3\u8bba\u3002')}</p><div class="metrics">{metrics}</div></div>
<div class="grid">
  {self.card(U(r'\u95e8\u5e97\u5229\u6da6'), U(r'\u6536\u5165\u3001\u6bdb\u5229\u3001\u79df\u91d1\u3001\u5de5\u8d44\u3001\u5e93\u5b58\u5360\u7528\u548c\u51c0\u5229\u6a21\u677f\u3002'), '/finance/store-profit', 'btn green', True)}
  {self.card(U(r'\u54c1\u724c\u5229\u6da6'), U(r'\u54c1\u724c\u9500\u552e\u3001\u6bdb\u5229\u3001\u6298\u6263\u3001\u8fd4\u70b9\u3001\u5e93\u5b58\u548c\u964d\u4ef7\u98ce\u9669\u3002'), '/finance/brand-profit', 'btn', True)}
  {self.card(U(r'Osprey \u8fd4\u70b9\u98ce\u9669'), U(r'59/60/62/65 \u6298\u3001\u8fd4\u70b9\u4f9d\u8d56\u548c\u5229\u6da6\u8bd5\u7b97\u3002'), '/brands/osprey-risk', 'btn orange', True)}
</div>
<div class="split"><div class="panel"><h2>{U(r'\u5229\u6da6\u5206\u6790')}</h2>{self.bullets(profit_items)}</div><div class="panel"><h2>{U(r'\u8d39\u7528\u5206\u6790')}</h2>{self.bullets(expense_items)}</div></div>
<div class="split"><div class="panel"><h2>{U(r'\u73b0\u91d1\u6d41\u89c2\u5bdf')}</h2>{self.bullets([self.finance_empty(), U(r'\u5173\u6ce8\u5e93\u5b58\u5360\u7528\u3001\u671f\u8d27\u4ed8\u6b3e\u3001\u4f9b\u5e94\u5546\u4ed8\u6b3e\u3001\u79df\u91d1\u548c\u5de5\u8d44\u538b\u529b\u3002')])}</div><div class="panel"><h2>{U(r'\u8fd4\u70b9\u5206\u6790')}</h2>{self.bullets(rebate_items)}</div></div>
<div class="split">
  <div class="panel form"><h2>{U(r'\u65b0\u5efa\u5229\u6da6\u8bb0\u5f55')}</h2><form method="post" action="/finance/profit/save"><label>{U(r'\u5bf9\u8c61\u7c7b\u578b')}</label><input name="object_type" placeholder="company / store / brand / product"><label>{U(r'\u5bf9\u8c61 ID')}</label><input name="object_id"><label>{U(r'\u6536\u5165')}</label><input name="revenue"><label>{U(r'\u6210\u672c')}</label><input name="cost"><label>{U(r'\u8d39\u7528')}</label><input name="expenses"><label>{U(r'\u8fd4\u70b9')}</label><input name="rebate_amount"><p><button>{U(r'\u4fdd\u5b58\u5229\u6da6\u8bb0\u5f55')}</button></p></form></div>
  <div class="panel form"><h2>{U(r'\u65b0\u5efa\u8d39\u7528')}</h2><form method="post" action="/finance/expenses/save"><label>{U(r'\u8d39\u7528\u7c7b\u578b')}</label><input name="expense_type" placeholder="rent / salary / marketing"><label>{T['store']}</label><input name="store_id"><label>{U(r'\u91d1\u989d')}</label><input name="amount"><label>{U(r'\u671f\u95f4')}</label><input name="period" placeholder="2026-07"><label>{U(r'\u8bf4\u660e')}</label><textarea name="description"></textarea><p><button>{U(r'\u4fdd\u5b58\u8d39\u7528')}</button></p></form></div>
</div>"""
        self.out(layout(U(r"\u8d22\u52a1\u5229\u6da6\u51b3\u7b56"), body, user=user, wide=True))

    def finance_store_profit(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_view_finance(user):
            return self.dashboard(user)
        stores = [U(r"\u5357\u5c71\u5e97"), U(r"\u632f\u5174\u5e97"), U(r"\u822a\u82d1\u5e97"), U(r"\u91d1\u6c99\u5e97"), U(r"\u7f51\u5e97")]
        cards = "".join(self.card(store, U(r"\u6536\u5165\u3001\u6bdb\u5229\u3001\u79df\u91d1\u3001\u6c34\u7535\u3001\u5de5\u8d44\u3001\u5e93\u5b58\u5360\u7528\u548c\u51c0\u5229\u7b49\u5f85\u6570\u636e\u63a5\u5165\u3002"), "/finance", "btn green", True) for store in stores)
        body = f"<div class='panel'><h2>{U(r'\u95e8\u5e97\u5229\u6da6\u5206\u6790')}</h2>{self.empty_state(self.finance_empty())}</div><div class='grid'>{cards}</div>"
        self.out(layout(U(r"\u95e8\u5e97\u5229\u6da6"), body, user=user, wide=True))

    def finance_brand_profit(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_view_finance(user):
            return self.dashboard(user)
        brands = ["KAILAS", "Osprey", "Mammut", "Salomon", "Deuter", "Gregory", "VAFOX"]
        cards = "".join(self.card(brand, U(r"\u9500\u552e\u3001\u6bdb\u5229\u3001\u6298\u6263\u3001\u8fd4\u70b9\u3001\u5e93\u5b58\u5360\u7528\u548c\u4f9b\u5e94\u5546\u98ce\u9669\u6a21\u677f\u3002"), "/brands/osprey-risk" if brand == "Osprey" else "/finance", "btn", True) for brand in brands)
        body = f"<div class='panel'><h2>{U(r'\u54c1\u724c\u5229\u6da6\u5206\u6790')}</h2>{self.empty_state(self.finance_empty())}</div><div class='grid'>{cards}</div>"
        self.out(layout(U(r"\u54c1\u724c\u5229\u6da6"), body, user=user, wide=True))

    def finance_number(self, form, key):
        try:
            return float(str(form.get(key, "")).replace(",", "").strip() or 0)
        except Exception:
            return 0.0

    def finance_profit_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        if not self.can_manage_finance(user):
            return self.redir("/")
        form = self.form()
        revenue = self.finance_number(form, "revenue")
        cost = self.finance_number(form, "cost")
        expenses = self.finance_number(form, "expenses")
        rebate_amount = self.finance_number(form, "rebate_amount")
        cash_occupation = self.finance_number(form, "cash_occupation")
        gross_profit = revenue - cost
        gross_margin = gross_profit / revenue if revenue else 0
        net_profit = gross_profit - expenses
        net_margin = net_profit / revenue if revenue else 0
        rebate_adjusted_profit = net_profit + rebate_amount
        now = ts()
        with db() as conn:
            cur = conn.execute("insert into finance_profit_records(profit_record_id,object_type,object_id,date_range_start,date_range_end,revenue,cost,gross_profit,gross_margin,expenses,net_profit,net_margin,rebate_amount,rebate_adjusted_profit,cash_occupation,data_sources,status,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("FP-"+uuid.uuid4().hex[:10], form.get("object_type",""), form.get("object_id",""), form.get("date_range_start",""), form.get("date_range_end",""), revenue, cost, gross_profit, gross_margin, expenses, net_profit, net_margin, rebate_amount, rebate_adjusted_profit, cash_occupation, form.get("data_sources","manual"), "draft", now, now))
        self.log_action(user, "finance_profit_created", "finance_profit", cur.lastrowid, form.get("object_type", ""))
        return self.redir("/finance")

    def finance_expense_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        if not self.can_manage_finance(user):
            return self.redir("/")
        form = self.form()
        now = ts()
        with db() as conn:
            cur = conn.execute("insert into finance_expenses(expense_id,expense_type,store_id,department_id,amount,period,description,related_object_type,related_object_id,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?)", ("FE-"+uuid.uuid4().hex[:10], form.get("expense_type","other"), form.get("store_id",""), form.get("department_id",""), self.finance_number(form, "amount"), form.get("period",""), form.get("description",""), form.get("related_object_type",""), form.get("related_object_id",""), now, now))
        self.log_action(user, "finance_expense_created", "finance_expense", cur.lastrowid, form.get("expense_type", ""))
        return self.redir("/finance")

    def finance_rebate_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        if not self.can_manage_finance(user):
            return self.redir("/")
        form = self.form()
        sales_amount = self.finance_number(form, "sales_amount")
        rebate_rate = self.finance_number(form, "rebate_rate")
        expected_rebate = self.finance_number(form, "expected_rebate") or sales_amount * rebate_rate
        now = ts()
        with db() as conn:
            cur = conn.execute("insert into finance_rebates(rebate_id,supplier_id,brand_id,period,sales_amount,rebate_rate,expected_rebate,actual_rebate,status,uncertainty_level,notes,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?)", ("FR-"+uuid.uuid4().hex[:10], form.get("supplier_id",""), form.get("brand_id",""), form.get("period",""), sales_amount, rebate_rate, expected_rebate, self.finance_number(form, "actual_rebate"), form.get("status","expected"), form.get("uncertainty_level","unknown"), form.get("notes",""), now, now))
        self.log_action(user, "finance_rebate_created", "finance_rebate", cur.lastrowid, form.get("brand_id", ""))
        return self.redir("/finance")

    def finance_discount_payload(self, form):
        cost_discount = self.finance_number(form, "cost_discount")
        selling_discount = self.finance_number(form, "selling_discount")
        rebate_rate = self.finance_number(form, "rebate_rate")
        sales_amount = self.finance_number(form, "sales_amount") or self.finance_number(form, "expected_sales_amount")
        inventory_amount = self.finance_number(form, "inventory_amount")
        fixed_expense = self.finance_number(form, "fixed_expense_allocation")
        variable_rate = self.finance_number(form, "variable_expense_rate")
        margin_rate = selling_discount - cost_discount
        gross_profit = sales_amount * margin_rate
        rebate_amount = sales_amount * rebate_rate
        variable_expense = sales_amount * variable_rate
        net_contribution = gross_profit + rebate_amount - fixed_expense - variable_expense
        risk_level = "high" if net_contribution < 0 else ("medium" if margin_rate + rebate_rate < 0.08 else "review")
        return {"gross_margin": margin_rate, "gross_profit": gross_profit, "rebate_amount": rebate_amount, "rebate_adjusted_gross_profit": gross_profit + rebate_amount, "estimated_net_contribution": net_contribution, "inventory_amount": inventory_amount, "risk_level": risk_level, "note": U(r"\u8bd5\u7b97\u4ec5\u57fa\u4e8e\u8f93\u5165\u6570\u636e\uff0c\u4e0d\u4ee3\u8868\u5b9e\u9645\u8d22\u52a1\u7ed3\u8bba\u3002")}

    def finance_break_even_payload(self, form):
        fixed_expenses = self.finance_number(form, "fixed_expenses")
        gross_margin_rate = self.finance_number(form, "gross_margin_rate")
        target_profit = self.finance_number(form, "target_profit")
        sales_target = self.finance_number(form, "sales_target")
        break_even_sales = (fixed_expenses + target_profit) / gross_margin_rate if gross_margin_rate else 0
        profit_at_current_sales = sales_target * gross_margin_rate - fixed_expenses
        required_sales_increase = max(0, break_even_sales - sales_target)
        warning = "high" if gross_margin_rate <= 0 or profit_at_current_sales < 0 else "review"
        return {"break_even_sales": break_even_sales, "profit_at_current_sales": profit_at_current_sales, "required_sales_increase": required_sales_increase, "warning": warning, "note": U(r"\u76c8\u4e8f\u5e73\u8861\u8bd5\u7b97\u9700\u7ed3\u5408\u771f\u5b9e\u8d39\u7528\u548c\u6bdb\u5229\u6570\u636e\u5ba1\u6838\u3002")}

    def api_finance_get(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_view_finance(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        with db() as conn:
            if path == "/api/finance":
                return self.json_out(self.finance_overview_payload())
            if path == "/api/finance/profit":
                rows = conn.execute("select * from finance_profit_records order by updated_at desc limit 100").fetchall()
                return self.json_out({"ok": True, "profit_records": [row_dict(r) for r in rows], "empty_message": self.finance_empty()})
            if path == "/api/finance/store-profit":
                return self.json_out({"ok": True, "stores": [U(r"\u5357\u5c71\u5e97"), U(r"\u632f\u5174\u5e97"), U(r"\u822a\u82d1\u5e97"), U(r"\u91d1\u6c99\u5e97"), U(r"\u7f51\u5e97")], "empty_message": self.finance_empty()})
            if path == "/api/finance/brand-profit":
                return self.json_out({"ok": True, "brands": ["KAILAS", "Osprey", "Mammut", "Salomon", "Deuter", "Gregory", "VAFOX"], "empty_message": self.finance_empty()})
            if path == "/api/finance/expenses":
                rows = conn.execute("select * from finance_expenses order by updated_at desc limit 100").fetchall()
                return self.json_out({"ok": True, "expenses": [row_dict(r) for r in rows]})
            if path == "/api/finance/cashflow":
                return self.json_out({"ok": True, "cashflow": {"cash_balance": None, "inventory_cash_occupation": self.cockpit_data()["metrics"]["inventory_amount"], "future_order_payment_pressure": None, "supplier_payment_pressure": None}, "empty_message": self.finance_empty()})
            if path == "/api/finance/rebates":
                rows = conn.execute("select * from finance_rebates order by updated_at desc limit 100").fetchall()
                return self.json_out({"ok": True, "rebates": [row_dict(r) for r in rows]})
        return self.json_out({"ok": False, "message": "unknown finance api"}, code=404)

    def api_finance_post(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_manage_finance(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        form = self.form()
        now = ts()
        if path == "/api/finance/profit":
            revenue = self.finance_number(form, "revenue")
            cost = self.finance_number(form, "cost")
            expenses = self.finance_number(form, "expenses")
            rebate_amount = self.finance_number(form, "rebate_amount")
            cash_occupation = self.finance_number(form, "cash_occupation")
            gross_profit = revenue - cost
            gross_margin = gross_profit / revenue if revenue else 0
            net_profit = gross_profit - expenses
            net_margin = net_profit / revenue if revenue else 0
            with db() as conn:
                cur = conn.execute("insert into finance_profit_records(profit_record_id,object_type,object_id,date_range_start,date_range_end,revenue,cost,gross_profit,gross_margin,expenses,net_profit,net_margin,rebate_amount,rebate_adjusted_profit,cash_occupation,data_sources,status,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("FP-"+uuid.uuid4().hex[:10], form.get("object_type",""), form.get("object_id",""), form.get("date_range_start",""), form.get("date_range_end",""), revenue, cost, gross_profit, gross_margin, expenses, net_profit, net_margin, rebate_amount, net_profit + rebate_amount, cash_occupation, form.get("data_sources","api"), "draft", now, now))
            self.log_action(user, "finance_profit_created", "finance_profit", cur.lastrowid, form.get("object_type", ""))
            return self.json_out({"ok": True, "id": cur.lastrowid})
        if path == "/api/finance/expenses":
            with db() as conn:
                cur = conn.execute("insert into finance_expenses(expense_id,expense_type,store_id,department_id,amount,period,description,related_object_type,related_object_id,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?)", ("FE-"+uuid.uuid4().hex[:10], form.get("expense_type","other"), form.get("store_id",""), form.get("department_id",""), self.finance_number(form, "amount"), form.get("period",""), form.get("description",""), form.get("related_object_type",""), form.get("related_object_id",""), now, now))
            self.log_action(user, "finance_expense_created", "finance_expense", cur.lastrowid, form.get("expense_type", ""))
            return self.json_out({"ok": True, "id": cur.lastrowid})
        if path == "/api/finance/rebates":
            sales_amount = self.finance_number(form, "sales_amount")
            rebate_rate = self.finance_number(form, "rebate_rate")
            expected_rebate = self.finance_number(form, "expected_rebate") or sales_amount * rebate_rate
            with db() as conn:
                cur = conn.execute("insert into finance_rebates(rebate_id,supplier_id,brand_id,period,sales_amount,rebate_rate,expected_rebate,actual_rebate,status,uncertainty_level,notes,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?)", ("FR-"+uuid.uuid4().hex[:10], form.get("supplier_id",""), form.get("brand_id",""), form.get("period",""), sales_amount, rebate_rate, expected_rebate, self.finance_number(form, "actual_rebate"), form.get("status","expected"), form.get("uncertainty_level","unknown"), form.get("notes",""), now, now))
            self.log_action(user, "finance_rebate_created", "finance_rebate", cur.lastrowid, form.get("brand_id", ""))
            return self.json_out({"ok": True, "id": cur.lastrowid})
        if path == "/api/finance/discount-calculate":
            result = self.finance_discount_payload(form)
            self.log_action(user, "finance_discount_calculated", "finance_model", None, result["risk_level"])
            return self.json_out({"ok": True, "result": result})
        if path == "/api/finance/break-even-calculate":
            result = self.finance_break_even_payload(form)
            self.log_action(user, "finance_break_even_calculated", "finance_model", None, result["warning"])
            return self.json_out({"ok": True, "result": result})
        if path == "/api/finance/create-task":
            with db() as conn:
                cur = conn.execute("insert into tasks(task_id,title,description,owner,related_object_type,related_object_id,priority,status,due_date,source_type,source_id,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("TASK-" + uuid.uuid4().hex[:10], form.get("title", U(r"\u8d22\u52a1\u98ce\u9669\u590d\u6838")), form.get("description", ""), form.get("owner", user["name"]), "finance", None, form.get("priority", "high"), "todo", form.get("due_date", ""), "finance", form.get("source_id", ""), user["id"], now, now))
            self.log_action(user, "finance_task_generated", "task", cur.lastrowid, form.get("title", ""))
            return self.json_out({"ok": True, "task_id": cur.lastrowid})
        return self.json_out({"ok": False, "message": U(r"\u8bf7\u4f7f\u7528\u9875\u9762\u8868\u5355\u6216\u6307\u5b9a\u7684\u8bd5\u7b97 API\u3002")}, code=501)

    def can_view_hr(self, user):
        return bool(user and user["role"] in ("boss", "admin", "finance", "store_manager"))

    def can_manage_hr(self, user):
        return bool(user and user["role"] in ("boss", "admin", "finance", "store_manager"))

    def hr_empty(self):
        return U(r"\u7b49\u5f85 SAP B1 / \u4efb\u52a1\u4e2d\u5fc3 / \u4eba\u4e8b\u6863\u6848\u6570\u636e\u540c\u6b65\u540e\u751f\u6210\u771f\u5b9e\u7ee9\u6548\u548c\u85aa\u916c\u6fc0\u52b1\u5206\u6790\u3002")

    def hr_overview_payload(self):
        with db() as conn:
            performance = [row_dict(r) for r in conn.execute("select * from hr_performance_records order by updated_at desc limit 20").fetchall()]
            plans = [row_dict(r) for r in conn.execute("select * from hr_incentive_plans order by updated_at desc limit 20").fetchall()]
            training = [row_dict(r) for r in conn.execute("select * from hr_training_records order by created_at desc limit 20").fetchall()]
            growth = [row_dict(r) for r in conn.execute("select * from hr_growth_records order by created_at desc limit 20").fetchall()]
            candidates = [row_dict(r) for r in conn.execute("select * from hr_candidates order by created_at desc limit 20").fetchall()]
        return {"ok": True, "empty_message": self.hr_empty(), "performance": performance, "incentive_plans": plans, "training": training, "growth_records": growth, "candidate_count": len(candidates), "candidates": candidates}

    def hr_center(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_view_hr(user):
            return self.dashboard(user)
        data = self.hr_overview_payload()
        metrics = "".join([
            self.metric(U(r"\u7ee9\u6548\u8bb0\u5f55"), money(len(data["performance"])), U(r"\u9700\u771f\u5b9e\u6570\u636e\u5ba1\u6838")),
            self.metric(U(r"\u6fc0\u52b1\u65b9\u6848"), money(len(data["incentive_plans"])), U(r"\u53ef\u7f16\u8f91\u89c4\u5219")),
            self.metric(U(r"\u57f9\u8bad\u8bb0\u5f55"), money(len(data["training"])), U(r"\u5458\u5de5\u6210\u957f")),
            self.metric(U(r"\u5019\u9009\u4eba"), money(data["candidate_count"]), U(r"\u62db\u8058\u6d41\u7a0b")),
        ])
        perf_items = [r["employee_id"] + " · " + r["store_id"] + " · " + money(r["sales_amount"]) for r in data["performance"]] or [self.hr_empty()]
        plan_items = [r["plan_name"] + " · " + (r["plan_type"] or "") + " · " + r["status"] for r in data["incentive_plans"]] or [U(r"\u6682\u65e0\u6fc0\u52b1\u65b9\u6848\u3002")]
        training_items = [r["employee_id"] + " · " + r["training_title"] for r in data["training"]] or [U(r"\u6682\u65e0\u57f9\u8bad\u8bb0\u5f55\u3002")]
        body = f"""
<div class="panel"><h2>{U(r'\u4eba\u4e8b\u7ee9\u6548\u4e0e\u6fc0\u52b1\u4e2d\u5fc3')}</h2><p class="small">{U(r'\u7ba1\u7406\u5458\u5de5\u6863\u6848\u3001\u95e8\u5e97\u7ee9\u6548\u3001\u6fc0\u52b1\u65b9\u6848\u3001\u57f9\u8bad\u6210\u957f\u548c\u62db\u8058\u8ddf\u8fdb\u3002\u4e0d\u81ea\u52a8\u751f\u6210\u6700\u7ec8\u4eba\u4e8b\u51b3\u7b56\u3002')}</p><div class="metrics">{metrics}</div></div>
<div class="grid">
  {self.card(U(r'\u5458\u5de5\u7ee9\u6548'), U(r'\u9500\u552e\u3001\u6bdb\u5229\u3001\u4efb\u52a1\u3001\u57f9\u8bad\u3001\u5ba2\u6237\u53cd\u9988\u548c AI \u8bc4\u4ef7\u3002'), '#performance-form', 'btn', True)}
  {self.card(U(r'\u6fc0\u52b1\u65b9\u6848'), U(r'\u4e2a\u4eba\u5956\u91d1\u3001\u56e2\u961f\u5956\u91d1\u3001\u95e8\u5e97\u76c8\u4e8f\u5e73\u8861\u6fc0\u52b1\u6a21\u677f\u3002'), '#plan-form', 'btn green', True)}
  {self.card(U(r'\u62db\u8058\u4e0e\u5165\u804c'), U(r'\u5019\u9009\u4eba\u3001\u9762\u8bd5\u8bb0\u5f55\u3001offer \u72b6\u6001\u548c\u5165\u804c\u4efb\u52a1\u3002'), '#candidate-form', 'btn orange', True)}
</div>
<div class="split"><div class="panel"><h2>{U(r'\u5458\u5de5\u7ee9\u6548')}</h2>{self.bullets(perf_items)}</div><div class="panel"><h2>{U(r'\u6fc0\u52b1\u65b9\u6848')}</h2>{self.bullets(plan_items)}</div></div>
<div class="split"><div class="panel"><h2>{U(r'\u57f9\u8bad\u6210\u957f')}</h2>{self.bullets(training_items)}</div><div class="panel"><h2>{U(r'AI \u5458\u5de5\u8bc4\u4ef7')}</h2>{self.empty_state(U(r'\u4ec5\u751f\u6210\u53d1\u5c55\u5efa\u8bae\u548c\u98ce\u9669\u63d0\u9192\uff0c\u4e0d\u505a\u6700\u7ec8\u4eba\u4e8b\u51b3\u7b56\u3002'))}</div></div>
<div class="split">
  <div id="performance-form" class="panel form"><h2>{U(r'\u65b0\u5efa\u7ee9\u6548')}</h2><form method="post" action="/hr/performance/save"><label>{U(r'\u5458\u5de5 ID')}</label><input name="employee_id"><label>{T['store']}</label><input name="store_id"><label>{U(r'\u9500\u552e\u989d')}</label><input name="sales_amount"><label>{U(r'\u6bdb\u5229')}</label><input name="gross_profit"><label>{U(r'\u5df2\u5b8c\u6210\u4efb\u52a1')}</label><input name="tasks_completed"><label>{U(r'\u7ba1\u7406\u8005\u8bc4\u4ef7')}</label><textarea name="manager_review"></textarea><p><button>{U(r'\u4fdd\u5b58\u7ee9\u6548')}</button></p></form></div>
  <div id="plan-form" class="panel form"><h2>{U(r'\u65b0\u5efa\u6fc0\u52b1\u65b9\u6848')}</h2><form method="post" action="/hr/incentive-plans/save"><label>{U(r'\u65b9\u6848\u540d\u79f0')}</label><input name="plan_name"><label>{U(r'\u65b9\u6848\u7c7b\u578b')}</label><input name="plan_type" placeholder="team_sales_bonus"><label>{T['store']}</label><input name="store_id"><label>{U(r'\u5956\u91d1\u6c60\u6bd4\u7387')}</label><input name="bonus_pool_rate" placeholder="0.30"><label>{U(r'\u89c4\u5219\u8bf4\u660e')}</label><textarea name="rule_description"></textarea><p><button>{U(r'\u4fdd\u5b58\u65b9\u6848')}</button></p></form></div>
</div>
<div class="split">
  <div class="panel form"><h2>{U(r'\u57f9\u8bad\u8bb0\u5f55')}</h2><form method="post" action="/hr/training/save"><label>{U(r'\u5458\u5de5 ID')}</label><input name="employee_id"><label>{U(r'\u57f9\u8bad\u6807\u9898')}</label><input name="training_title"><label>{U(r'\u7ed3\u679c')}</label><input name="result"><p><button>{U(r'\u4fdd\u5b58\u57f9\u8bad')}</button></p></form></div>
  <div id="candidate-form" class="panel form"><h2>{U(r'\u5019\u9009\u4eba')}</h2><form method="post" action="/hr/candidates/save"><label>{U(r'\u59d3\u540d')}</label><input name="name"><label>{U(r'\u624b\u673a')}</label><input name="phone"><label>{U(r'\u76ee\u6807\u5c97\u4f4d')}</label><input name="target_position"><label>{U(r'\u4e0b\u4e00\u6b65')}</label><textarea name="next_step"></textarea><p><button>{U(r'\u4fdd\u5b58\u5019\u9009\u4eba')}</button></p></form></div>
</div>"""
        self.out(layout(U(r"\u4eba\u4e8b\u7ee9\u6548\u6fc0\u52b1"), body, user=user, wide=True))

    def hr_performance_score(self, form):
        sales = self.finance_number(form, "sales_amount")
        gross_profit = self.finance_number(form, "gross_profit")
        tasks = self.finance_number(form, "tasks_completed")
        training = self.finance_number(form, "training_completed")
        feedback = self.finance_number(form, "customer_feedback_score")
        score = min(100, sales / 1000 + gross_profit / 500 + tasks * 3 + training * 5 + feedback * 10)
        risk_flags = []
        if sales <= 0:
            risk_flags.append("sales_missing")
        if tasks <= 0:
            risk_flags.append("task_data_missing")
        return {"performance_score": round(score, 2), "bonus_estimate": 0, "ai_evaluation": self.hr_empty(), "risk_flags": risk_flags}

    def hr_incentive_calculate_payload(self, form):
        actual_gross_profit = self.finance_number(form, "actual_gross_profit")
        break_even_gross_profit = self.finance_number(form, "break_even_gross_profit")
        pool_rate = self.finance_number(form, "incentive_pool_rate") or self.finance_number(form, "bonus_pool_rate") or 0.30
        individual_rate = self.finance_number(form, "individual_allocation_rate") or 0.20
        team_rate = self.finance_number(form, "team_allocation_rate") or 0.10
        incremental = max(0, actual_gross_profit - break_even_gross_profit)
        pool = incremental * pool_rate
        return {"incremental_gross_profit": incremental, "incentive_pool": pool, "individual_pool": incremental * individual_rate, "team_pool": incremental * team_rate, "note": U(r"\u8bd5\u7b97\u4ec5\u4f5c\u65b9\u6848\u8ba8\u8bba\uff0c\u4e0d\u4ee3\u8868\u6700\u7ec8\u85aa\u916c\u53d1\u653e\u3002")}

    def hr_insert(self, table, cols, defaults, action, target_type):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        if not self.can_manage_hr(user):
            return self.redir("/")
        form = self.form()
        vals = [defaults.get(c, form.get(c, "")) for c in cols]
        with db() as conn:
            cur = conn.execute(f"insert into {table}({','.join(cols)}) values({','.join('?' for _ in cols)})", vals)
        self.log_action(user, action, target_type, cur.lastrowid, "")
        return self.redir("/hr")

    def hr_performance_save(self):
        form = self.form()
        now = ts()
        sales = self.finance_number(form, "sales_amount")
        gross_profit = self.finance_number(form, "gross_profit")
        gross_margin = gross_profit / sales if sales else 0
        return self.hr_insert("hr_performance_records", ["performance_id","employee_id","store_id","period_start","period_end","sales_amount","gross_profit","gross_margin","tasks_completed","customer_feedback_score","content_submissions","training_completed","attendance_status","manager_review","ai_evaluation","status","created_at","updated_at"], {"performance_id":"HP-"+uuid.uuid4().hex[:10],"sales_amount":sales,"gross_profit":gross_profit,"gross_margin":gross_margin,"tasks_completed":int(self.finance_number(form,"tasks_completed")),"customer_feedback_score":self.finance_number(form,"customer_feedback_score"),"content_submissions":int(self.finance_number(form,"content_submissions")),"training_completed":int(self.finance_number(form,"training_completed")),"ai_evaluation":self.hr_empty(),"status":"draft","created_at":now,"updated_at":now}, "hr_performance_created", "hr_performance")

    def hr_incentive_plan_save(self):
        user = self.current_user()
        now = ts()
        form = self.form()
        return self.hr_insert("hr_incentive_plans", ["incentive_plan_id","plan_name","plan_type","store_id","employee_id","start_date","end_date","rule_description","calculation_method","target_sales","target_gross_profit","target_margin_rate","bonus_pool_rate","individual_weight","team_weight","break_even_sales","break_even_gross_profit","fixed_expenses","incentive_pool_rate","individual_allocation_rate","team_allocation_rate","carry_forward_rule","notes","status","created_by","created_at","updated_at"], {"incentive_plan_id":"IP-"+uuid.uuid4().hex[:10],"target_sales":self.finance_number(form,"target_sales"),"target_gross_profit":self.finance_number(form,"target_gross_profit"),"target_margin_rate":self.finance_number(form,"target_margin_rate"),"bonus_pool_rate":self.finance_number(form,"bonus_pool_rate"),"individual_weight":self.finance_number(form,"individual_weight"),"team_weight":self.finance_number(form,"team_weight"),"break_even_sales":self.finance_number(form,"break_even_sales"),"break_even_gross_profit":self.finance_number(form,"break_even_gross_profit"),"fixed_expenses":self.finance_number(form,"fixed_expenses"),"incentive_pool_rate":self.finance_number(form,"incentive_pool_rate"),"individual_allocation_rate":self.finance_number(form,"individual_allocation_rate"),"team_allocation_rate":self.finance_number(form,"team_allocation_rate"),"status":"draft","created_by":user["id"] if user else None,"created_at":now,"updated_at":now}, "hr_incentive_plan_created", "hr_incentive_plan")

    def hr_training_save(self):
        now = ts()
        return self.hr_insert("hr_training_records", ["training_id","employee_id","training_title","training_type","date","result","certificate","notes","created_at"], {"training_id":"HT-"+uuid.uuid4().hex[:10],"created_at":now}, "hr_training_created", "hr_training")

    def hr_growth_save(self):
        now = ts()
        return self.hr_insert("hr_growth_records", ["growth_id","employee_id","title","description","date","related_store","related_task","related_performance","created_at"], {"growth_id":"HG-"+uuid.uuid4().hex[:10],"created_at":now}, "hr_growth_created", "hr_growth")

    def hr_candidate_save(self):
        now = ts()
        return self.hr_insert("hr_candidates", ["candidate_id","name","phone","target_position","resume_file","interview_status","evaluation","next_step","created_at"], {"candidate_id":"HC-"+uuid.uuid4().hex[:10],"interview_status":"new","created_at":now}, "hr_candidate_created", "hr_candidate")

    def api_hr_get(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_view_hr(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        if path == "/api/hr":
            return self.json_out(self.hr_overview_payload())
        table_map = {"/api/hr/performance": ("hr_performance_records", "performance"), "/api/hr/incentive-plans": ("hr_incentive_plans", "incentive_plans"), "/api/hr/training": ("hr_training_records", "training"), "/api/hr/growth-records": ("hr_growth_records", "growth_records"), "/api/hr/candidates": ("hr_candidates", "candidates")}
        if path in table_map:
            table, key = table_map[path]
            with db() as conn:
                rows = conn.execute(f"select * from {table} order by id desc limit 100").fetchall()
            return self.json_out({"ok": True, key: [row_dict(r) for r in rows], "empty_message": self.hr_empty()})
        if path == "/api/hr/ai-evaluation":
            return self.json_out({"ok": True, "evaluation": {"strengths": [], "risks": [], "suggested_development_path": self.hr_empty(), "human_review_required": True}})
        return self.json_out({"ok": False, "message": "unknown hr api"}, code=404)

    def api_hr_post(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_manage_hr(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        form = self.form()
        now = ts()
        if path == "/api/hr/performance":
            sales = self.finance_number(form, "sales_amount")
            gross_profit = self.finance_number(form, "gross_profit")
            gross_margin = gross_profit / sales if sales else 0
            with db() as conn:
                cur = conn.execute("insert into hr_performance_records(performance_id,employee_id,store_id,period_start,period_end,sales_amount,gross_profit,gross_margin,tasks_completed,customer_feedback_score,content_submissions,training_completed,attendance_status,manager_review,ai_evaluation,status,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("HP-"+uuid.uuid4().hex[:10], form.get("employee_id",""), form.get("store_id",""), form.get("period_start",""), form.get("period_end",""), sales, gross_profit, gross_margin, int(self.finance_number(form,"tasks_completed")), self.finance_number(form,"customer_feedback_score"), int(self.finance_number(form,"content_submissions")), int(self.finance_number(form,"training_completed")), form.get("attendance_status",""), form.get("manager_review",""), self.hr_empty(), "draft", now, now))
            self.log_action(user, "hr_performance_created", "hr_performance", cur.lastrowid, "")
            return self.json_out({"ok": True, "id": cur.lastrowid})
        if path == "/api/hr/incentive-plans":
            with db() as conn:
                cur = conn.execute("insert into hr_incentive_plans(incentive_plan_id,plan_name,plan_type,store_id,employee_id,start_date,end_date,rule_description,calculation_method,target_sales,target_gross_profit,target_margin_rate,bonus_pool_rate,individual_weight,team_weight,break_even_sales,break_even_gross_profit,fixed_expenses,incentive_pool_rate,individual_allocation_rate,team_allocation_rate,carry_forward_rule,notes,status,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("IP-"+uuid.uuid4().hex[:10], form.get("plan_name",U(r"\u672a\u547d\u540d\u6fc0\u52b1\u65b9\u6848")), form.get("plan_type",""), form.get("store_id",""), form.get("employee_id",""), form.get("start_date",""), form.get("end_date",""), form.get("rule_description",""), form.get("calculation_method",""), self.finance_number(form,"target_sales"), self.finance_number(form,"target_gross_profit"), self.finance_number(form,"target_margin_rate"), self.finance_number(form,"bonus_pool_rate"), self.finance_number(form,"individual_weight"), self.finance_number(form,"team_weight"), self.finance_number(form,"break_even_sales"), self.finance_number(form,"break_even_gross_profit"), self.finance_number(form,"fixed_expenses"), self.finance_number(form,"incentive_pool_rate"), self.finance_number(form,"individual_allocation_rate"), self.finance_number(form,"team_allocation_rate"), form.get("carry_forward_rule",""), form.get("notes",""), "draft", user["id"], now, now))
            self.log_action(user, "hr_incentive_plan_created", "hr_incentive_plan", cur.lastrowid, "")
            return self.json_out({"ok": True, "id": cur.lastrowid})
        if path == "/api/hr/training":
            with db() as conn:
                cur = conn.execute("insert into hr_training_records(training_id,employee_id,training_title,training_type,date,result,certificate,notes,created_at) values(?,?,?,?,?,?,?,?,?)", ("HT-"+uuid.uuid4().hex[:10], form.get("employee_id",""), form.get("training_title",U(r"\u672a\u547d\u540d\u57f9\u8bad")), form.get("training_type",""), form.get("date",""), form.get("result",""), form.get("certificate",""), form.get("notes",""), now))
            self.log_action(user, "hr_training_created", "hr_training", cur.lastrowid, "")
            return self.json_out({"ok": True, "id": cur.lastrowid})
        if path == "/api/hr/growth-records":
            with db() as conn:
                cur = conn.execute("insert into hr_growth_records(growth_id,employee_id,title,description,date,related_store,related_task,related_performance,created_at) values(?,?,?,?,?,?,?,?,?)", ("HG-"+uuid.uuid4().hex[:10], form.get("employee_id",""), form.get("title",U(r"\u5458\u5de5\u6210\u957f\u8bb0\u5f55")), form.get("description",""), form.get("date",""), form.get("related_store",""), form.get("related_task",""), form.get("related_performance",""), now))
            self.log_action(user, "hr_growth_created", "hr_growth", cur.lastrowid, "")
            return self.json_out({"ok": True, "id": cur.lastrowid})
        if path == "/api/hr/candidates":
            with db() as conn:
                cur = conn.execute("insert into hr_candidates(candidate_id,name,phone,target_position,resume_file,interview_status,evaluation,next_step,created_at) values(?,?,?,?,?,?,?,?,?)", ("HC-"+uuid.uuid4().hex[:10], form.get("name",U(r"\u672a\u547d\u540d\u5019\u9009\u4eba")), form.get("phone",""), form.get("target_position",""), form.get("resume_file",""), form.get("interview_status","new"), form.get("evaluation",""), form.get("next_step",""), now))
            self.log_action(user, "hr_candidate_created", "hr_candidate", cur.lastrowid, "")
            return self.json_out({"ok": True, "id": cur.lastrowid})
        if path.endswith("/calculate"):
            result = self.hr_incentive_calculate_payload(form)
            self.log_action(user, "hr_incentive_calculated", "hr_incentive", None, "")
            return self.json_out({"ok": True, "result": result})
        if path == "/api/hr/create-task":
            with db() as conn:
                cur = conn.execute("insert into tasks(task_id,title,description,owner,related_object_type,related_object_id,priority,status,due_date,source_type,source_id,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("TASK-" + uuid.uuid4().hex[:10], form.get("title", U(r"\u4eba\u4e8b\u7ee9\u6548\u8ddf\u8fdb")), form.get("description", ""), form.get("owner", user["name"]), "hr", None, form.get("priority", "normal"), "todo", form.get("due_date", ""), "hr", form.get("source_id", ""), user["id"], now, now))
            self.log_action(user, "hr_task_generated", "task", cur.lastrowid, form.get("title", ""))
            return self.json_out({"ok": True, "task_id": cur.lastrowid})
        return self.json_out({"ok": False, "message": U(r"\u8bf7\u4f7f\u7528\u9875\u9762\u8868\u5355\u586b\u5199\u8be6\u7ec6\u5b57\u6bb5\uff0cAPI \u5199\u5165\u5df2\u9884\u7559\u3002")}, code=501)

    def api_hr_put(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_manage_hr(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        if path.startswith("/api/hr/incentive-plans/"):
            return self.json_out({"ok": True, "message": U(r"\u6fc0\u52b1\u65b9\u6848\u66f4\u65b0 API \u5df2\u9884\u7559\uff0cV1 \u8bf7\u901a\u8fc7\u65b0\u5efa\u65b9\u6848\u4fdd\u7559\u7248\u672c\u3002")})
        return self.json_out({"ok": False, "message": "unknown hr update api"}, code=404)

    def can_view_customer_growth(self, user):
        return bool(user and user["role"] in ("boss", "admin", "store_manager", "employee"))

    def can_manage_customer_growth(self, user):
        return bool(user and user["role"] in ("boss", "admin", "store_manager"))

    def customer_growth_empty(self):
        return U(r"\u7b49\u5f85 SAP B1 / \u4f1a\u5458 / \u4f01\u4e1a\u5fae\u4fe1\u6570\u636e\u63a5\u5165\uff0c\u4e0d\u7f16\u9020\u771f\u5b9e\u987e\u5ba2\u8d44\u6599\u3002")

    def customer_growth_payload(self):
        with db() as conn:
            segments = [row_dict(r) for r in conn.execute("select * from customer_segments order by updated_at desc limit 30").fetchall()]
            tags = [row_dict(r) for r in conn.execute("select * from customer_tags order by updated_at desc limit 50").fetchall()]
            groups = [row_dict(r) for r in conn.execute("select * from private_domain_groups order by updated_at desc limit 30").fetchall()]
            followups = [row_dict(r) for r in conn.execute("select * from customer_followups order by updated_at desc limit 30").fetchall()]
            events = [row_dict(r) for r in conn.execute("select * from customer_events order by created_at desc limit 30").fetchall()]
        return {"ok": True, "empty_message": self.customer_growth_empty(), "segments": segments, "tags": tags, "groups": groups, "followups": followups, "events": events}

    def customer_growth_center(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_view_customer_growth(user):
            return self.dashboard(user)
        data = self.customer_growth_payload()
        metrics = "".join([
            self.metric(U(r"\u4f1a\u5458\u5206\u5c42"), money(len(data["segments"])), U(r"\u53ef\u81ea\u5b9a\u4e49\u89c4\u5219")),
            self.metric(U(r"\u987e\u5ba2\u6807\u7b7e"), money(len(data["tags"])), U(r"\u5174\u8da3/\u54c1\u724c/\u590d\u8d2d")),
            self.metric(U(r"\u79c1\u57df\u7fa4"), money(len(data["groups"])), U(r"\u4f01\u5fae\u9884\u7559")),
            self.metric(U(r"\u5f85\u8ddf\u8fdb"), money(len(data["followups"])), U(r"\u53ef\u8f6c\u4efb\u52a1")),
        ])
        segment_items = [r["segment_name"] + " · " + r["priority"] + " · " + r["status"] for r in data["segments"]] or [self.customer_growth_empty()]
        group_items = [r["group_name"] + " · " + (r["platform"] or "") + " · " + r["status"] for r in data["groups"]] or [U(r"\u6682\u65e0\u79c1\u57df\u7fa4\u3002")]
        follow_items = [r["customer_id"] + " · " + (r["followup_type"] or "") + " · " + r["status"] for r in data["followups"]] or [U(r"\u6682\u65e0\u987e\u5ba2\u8ddf\u8fdb\u3002")]
        body = f"""
<div class="panel"><h2>{U(r'\u987e\u5ba2\u4f1a\u5458\u4e0e\u79c1\u57df\u589e\u957f\u4e2d\u5fc3')}</h2><p class="small">{U(r'\u7ba1\u7406\u4f1a\u5458\u5206\u5c42\u3001\u987e\u5ba2\u6807\u7b7e\u3001\u79c1\u57df\u7fa4\u3001\u8ddf\u8fdb\u4efb\u52a1\u548c\u6d3b\u52a8\u9080\u7ea6\u3002\u987e\u5ba2\u9690\u79c1\u4f18\u5148\u3002')}</p><div class="metrics">{metrics}</div></div>
<div class="grid">
  {self.card(U(r'\u4f1a\u5458\u5206\u5c42'), U(r'\u65b0\u5ba2\u3001\u8001\u5ba2\u3001VIP\u3001\u9ad8\u4ef7\u503c\u3001\u6c89\u7761\u3001\u5174\u8da3\u7fa4\u4f53\u3002'), '#segment-form', 'btn', True)}
  {self.card(U(r'\u79c1\u57df\u7fa4'), U(r'\u95e8\u5e97\u7fa4\u3001\u54c1\u724c\u7fa4\u3001\u5f92\u6b65\u7fa4\u3001\u9732\u8425\u7fa4\u3001VIP \u7fa4\u3002'), '#group-form', 'btn green', True)}
  {self.card(U(r'\u6d3b\u52a8\u9080\u7ea6'), U(r'\u5f92\u6b65\u6d3b\u52a8\u3001\u88c5\u5907\u8bfe\u5802\u3001\u65b0\u54c1\u4f53\u9a8c\u548c\u4f1a\u5458\u65e5\u3002'), '#event-form', 'btn orange', True)}
</div>
<div class="split"><div class="panel"><h2>{U(r'\u4f1a\u5458\u5206\u5c42')}</h2>{self.bullets(segment_items)}</div><div class="panel"><h2>{U(r'\u79c1\u57df\u7fa4')}</h2>{self.bullets(group_items)}</div></div>
<div class="split"><div class="panel"><h2>{U(r'\u987e\u5ba2\u8ddf\u8fdb')}</h2>{self.bullets(follow_items)}</div><div class="panel"><h2>{U(r'AI \u987e\u5ba2\u5efa\u8bae')}</h2>{self.empty_state(U(r'\u9884\u7559\uff1a\u8ddf\u8fdb\u5ba2\u6237\u3001\u6d3b\u52a8\u9080\u8bf7\u3001\u5185\u5bb9\u63a8\u8350\u3001\u4ea7\u54c1\u63a8\u8350\u548c\u6c89\u7761\u6fc0\u6d3b\u3002'))}</div></div>
<div class="split">
  <div id="segment-form" class="panel form"><h2>{U(r'\u65b0\u5efa\u5206\u5c42')}</h2><form method="post" action="/customer-growth/segments/save"><label>{U(r'\u5206\u5c42\u540d\u79f0')}</label><input name="segment_name"><label>{U(r'\u89c4\u5219')}</label><textarea name="rules"></textarea><label>{U(r'\u4f18\u5148\u7ea7')}</label><input name="priority"><p><button>{U(r'\u4fdd\u5b58\u5206\u5c42')}</button></p></form></div>
  <div class="panel form"><h2>{U(r'\u65b0\u5efa\u6807\u7b7e')}</h2><form method="post" action="/customer-growth/tags/save"><label>{U(r'\u6807\u7b7e\u540d')}</label><input name="tag_name"><label>{U(r'\u7c7b\u578b')}</label><input name="tag_type" placeholder="interest / brand / value"><p><button>{U(r'\u4fdd\u5b58\u6807\u7b7e')}</button></p></form></div>
</div>
<div class="split">
  <div id="group-form" class="panel form"><h2>{U(r'\u65b0\u5efa\u79c1\u57df\u7fa4')}</h2><form method="post" action="/customer-growth/groups/save"><label>{U(r'\u7fa4\u540d')}</label><input name="group_name"><label>{U(r'\u5e73\u53f0')}</label><input name="platform" placeholder="enterprise_wechat_placeholder"><label>{T['store']}</label><input name="store_id"><label>{U(r'\u4e3b\u9898')}</label><input name="topic"><p><button>{U(r'\u4fdd\u5b58\u7fa4')}</button></p></form></div>
  <div class="panel form"><h2>{U(r'\u65b0\u5efa\u8ddf\u8fdb')}</h2><form method="post" action="/customer-growth/followups/save"><label>{U(r'\u987e\u5ba2 ID')}</label><input name="customer_id"><label>{U(r'\u8ddf\u8fdb\u7c7b\u578b')}</label><input name="followup_type"><label>{U(r'\u4e0b\u4e00\u6b65')}</label><textarea name="next_action"></textarea><label>{U(r'\u622a\u6b62\u65e5\u671f')}</label><input name="due_date"><p><button>{U(r'\u4fdd\u5b58\u8ddf\u8fdb')}</button></p></form></div>
</div>
<div id="event-form" class="panel form"><h2>{U(r'\u6d3b\u52a8\u9080\u7ea6')}</h2><form method="post" action="/customer-growth/events/save"><label>{U(r'\u6d3b\u52a8\u6807\u9898')}</label><input name="title"><label>{T['store']}</label><input name="store_id"><label>{U(r'\u76ee\u6807\u5206\u5c42')}</label><input name="target_segments"><label>{U(r'\u9080\u7ea6\u6587\u6848')}</label><textarea name="invitation_message"></textarea><p><button>{U(r'\u4fdd\u5b58\u6d3b\u52a8')}</button></p></form></div>"""
        self.out(layout(U(r"\u987e\u5ba2\u79c1\u57df\u589e\u957f"), body, user=user, wide=True))

    def customer_insert(self, table, cols, defaults, action, target_type):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        if not self.can_manage_customer_growth(user):
            return self.redir("/")
        form = self.form()
        vals = [defaults.get(c, form.get(c, "")) for c in cols]
        with db() as conn:
            cur = conn.execute(f"insert into {table}({','.join(cols)}) values({','.join('?' for _ in cols)})", vals)
        self.log_action(user, action, target_type, cur.lastrowid, "")
        return self.redir("/customer-growth")

    def customer_segment_save(self):
        now = ts()
        return self.customer_insert("customer_segments", ["segment_id","segment_name","description","rules","customer_count","priority","status","created_at","updated_at"], {"segment_id":"CS-"+uuid.uuid4().hex[:10],"customer_count":0,"status":"draft","created_at":now,"updated_at":now}, "customer_segment_created", "customer_segment")

    def customer_tag_save(self):
        now = ts()
        return self.customer_insert("customer_tags", ["tag_id","tag_name","tag_type","description","status","created_at","updated_at"], {"tag_id":"CT-"+uuid.uuid4().hex[:10],"status":"active","created_at":now,"updated_at":now}, "customer_tag_created", "customer_tag")

    def private_group_save(self):
        now = ts()
        return self.customer_insert("private_domain_groups", ["group_id","group_name","platform","store_id","owner_employee_id","customer_count","group_type","topic","status","created_at","updated_at"], {"group_id":"PG-"+uuid.uuid4().hex[:10],"customer_count":0,"status":"draft","created_at":now,"updated_at":now}, "private_group_created", "private_group")

    def customer_followup_save(self):
        now = ts()
        return self.customer_insert("customer_followups", ["followup_id","customer_id","employee_id","store_id","followup_type","content","next_action","due_date","status","created_at","updated_at"], {"followup_id":"CF-"+uuid.uuid4().hex[:10],"status":"todo","created_at":now,"updated_at":now}, "customer_followup_created", "customer_followup")

    def customer_event_save(self):
        now = ts()
        return self.customer_insert("customer_events", ["event_id","title","store_id","target_segments","target_tags","invitation_message","status","created_at"], {"event_id":"CE-"+uuid.uuid4().hex[:10],"status":"draft","created_at":now}, "customer_event_created", "customer_event")

    def api_customer_growth_get(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_view_customer_growth(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        if path == "/api/customer-growth":
            return self.json_out(self.customer_growth_payload())
        table_map = {"/api/customer-growth/segments": ("customer_segments","segments"), "/api/customer-growth/tags": ("customer_tags","tags"), "/api/customer-growth/groups": ("private_domain_groups","groups"), "/api/customer-growth/followups": ("customer_followups","followups"), "/api/customer-growth/events": ("customer_events","events")}
        if path in table_map:
            table, key = table_map[path]
            with db() as conn:
                rows = conn.execute(f"select * from {table} order by id desc limit 100").fetchall()
            return self.json_out({"ok": True, key: [row_dict(r) for r in rows], "empty_message": self.customer_growth_empty()})
        if path == "/api/customer-growth/value-analysis":
            return self.json_out({"ok": True, "value_analysis": {"total_spend": None, "purchase_frequency": None, "preferred_brands": [], "next_best_action": self.customer_growth_empty()}})
        return self.json_out({"ok": False, "message": "unknown customer growth api"}, code=404)

    def api_customer_growth_post(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_manage_customer_growth(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        form = self.form()
        now = ts()
        if path == "/api/customer-growth/create-task":
            with db() as conn:
                cur = conn.execute("insert into tasks(task_id,title,description,owner,related_object_type,related_object_id,priority,status,due_date,source_type,source_id,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("TASK-" + uuid.uuid4().hex[:10], form.get("title", U(r"\u987e\u5ba2\u8ddf\u8fdb")), form.get("description", ""), form.get("owner", user["name"]), "customer_growth", None, form.get("priority", "normal"), "todo", form.get("due_date", ""), "customer_growth", form.get("source_id", ""), user["id"], now, now))
            self.log_action(user, "customer_growth_task_created", "task", cur.lastrowid, form.get("title", ""))
            return self.json_out({"ok": True, "task_id": cur.lastrowid})
        table_map = {"/api/customer-growth/segments": ("customer_segments", ["segment_id","segment_name","description","rules","customer_count","priority","status","created_at","updated_at"], {"segment_id":"CS-"+uuid.uuid4().hex[:10],"customer_count":0,"status":"draft","created_at":now,"updated_at":now}, "customer_segment_created"), "/api/customer-growth/tags": ("customer_tags", ["tag_id","tag_name","tag_type","description","status","created_at","updated_at"], {"tag_id":"CT-"+uuid.uuid4().hex[:10],"status":"active","created_at":now,"updated_at":now}, "customer_tag_created"), "/api/customer-growth/groups": ("private_domain_groups", ["group_id","group_name","platform","store_id","owner_employee_id","customer_count","group_type","topic","status","created_at","updated_at"], {"group_id":"PG-"+uuid.uuid4().hex[:10],"customer_count":0,"status":"draft","created_at":now,"updated_at":now}, "private_group_created"), "/api/customer-growth/followups": ("customer_followups", ["followup_id","customer_id","employee_id","store_id","followup_type","content","next_action","due_date","status","created_at","updated_at"], {"followup_id":"CF-"+uuid.uuid4().hex[:10],"status":"todo","created_at":now,"updated_at":now}, "customer_followup_created"), "/api/customer-growth/events": ("customer_events", ["event_id","title","store_id","target_segments","target_tags","invitation_message","status","created_at"], {"event_id":"CE-"+uuid.uuid4().hex[:10],"status":"draft","created_at":now}, "customer_event_created")}
        if path in table_map:
            table, cols, defaults, action = table_map[path]
            vals = [defaults.get(c, form.get(c, "")) for c in cols]
            with db() as conn:
                cur = conn.execute(f"insert into {table}({','.join(cols)}) values({','.join('?' for _ in cols)})", vals)
            self.log_action(user, action, table, cur.lastrowid, "")
            return self.json_out({"ok": True, "id": cur.lastrowid})
        return self.json_out({"ok": False, "message": "unknown customer growth write api"}, code=404)

    def platform_modules(self):
        return [
            ("ai_ceo", "AI CEO", "/ai-ceo", "ai", "boss"),
            ("business_cockpit", U(r"\u7ecf\u8425\u9a7e\u9a76\u8231"), "/business-overview", "ai", "boss"),
            ("jarvis", "Jarvis", "/jarvis", "ai", "view_workspace"),
            ("agents", "AI Agents", "/agents", "ai", "admin"),
            ("reports", "Reports", "/reports", "ai", "boss"),
            ("store_growth", U(r"\u95e8\u5e97\u589e\u957f"), "/store-growth", "operation", "store_manager"),
            ("brand_growth", U(r"\u54c1\u724c\u589e\u957f"), "/brand-growth", "operation", "purchasing"),
            ("inventory_decision", U(r"\u5e93\u5b58\u51b3\u7b56"), "/inventory-decision", "operation", "purchasing"),
            ("finance", U(r"\u8d22\u52a1"), "/finance", "operation", "finance"),
            ("hr", U(r"\u4eba\u4e8b\u7ee9\u6548"), "/hr", "operation", "store_manager"),
            ("customer_growth", U(r"\u987e\u5ba2\u589e\u957f"), "/customer-growth", "operation", "employee"),
            ("sap_sync", "SAP Sync", "/sap-sync", "operation", "finance"),
            ("data_pipeline", U(r"\u6570\u636e\u7ba1\u9053"), "/data-pipeline", "operation", "finance"),
            ("documents", U(r"\u6587\u4ef6"), "/documents", "knowledge", "employee"),
            ("knowledge", U(r"\u77e5\u8bc6\u5e93"), "/knowledge", "knowledge", "employee"),
            ("memory", U(r"\u8bb0\u5fc6"), "/memory", "knowledge", "store_manager"),
            ("graph", U(r"\u5173\u7cfb\u56fe"), "/graph", "knowledge", "store_manager"),
            ("tasks", U(r"\u4efb\u52a1"), "/tasks", "execution", "employee"),
            ("workflow", U(r"\u5de5\u4f5c\u6d41"), "/workflow", "execution", "store_manager"),
            ("automation", U(r"\u81ea\u52a8\u5316"), "/automation", "execution", "admin"),
            ("mobile", U(r"\u79fb\u52a8\u5916\u52e4"), "/mobile", "execution", "employee"),
            ("settings", U(r"\u8bbe\u7f6e"), "/settings", "system", "admin"),
            ("boss_workspace", U(r"\u8001\u677f\u5de5\u4f5c\u53f0"), "/boss", "system", "boss"),
            ("employee_workspace", U(r"\u5458\u5de5\u5de5\u4f5c\u53f0"), "/employee-workspace", "system", "employee"),
            ("risk_center", U(r"\u98ce\u9669\u4e2d\u5fc3"), "/risks", "system", "store_manager"),
            ("decision_center", U(r"\u51b3\u7b56\u4e2d\u5fc3"), "/decisions", "system", "store_manager"),
            ("audit", U(r"\u5ba1\u8ba1"), "/timeline", "system", "admin"),
            ("health", U(r"\u5065\u5eb7"), "/system/modules", "system", "admin"),
        ]

    def platform_objects(self):
        names = ["store","employee","brand","product","supplier","customer","document","knowledge_item","memory","task","workflow","automation","report","content","finance_record","inventory_record","hr_record","customer_segment","decision","risk","agent","graph_entity"]
        return [{"object_type": n, "display_name": n.replace("_", " ").title(), "plural_name": n + "s", "route_pattern": "/", "permission_scope": "view_workspace", "searchable": True, "ai_accessible": True, "timeline_enabled": True, "audit_enabled": True} for n in names]

    def can_view_system(self, user):
        return bool(user and user["role"] in ("boss", "admin"))

    def workspace_payload(self, user):
        with db() as conn:
            tasks = [row_dict(r) for r in conn.execute("select * from tasks where status!='done' order by updated_at desc limit 10").fetchall()]
            notifications = [row_dict(r) for r in conn.execute("select * from notifications order by created_at desc limit 10").fetchall()]
            reports = [row_dict(r) for r in conn.execute("select * from reports order by updated_at desc limit 5").fetchall()] if "reports" in {x[0] for x in conn.execute("select name from sqlite_master where type='table'").fetchall()} else []
        return {"ok": True, "user": {"id": user["id"], "role": user["role"], "store": user["store"]}, "tasks": tasks, "notifications": notifications, "reports": reports, "empty_message": self.cockpit_data()["empty_message"]}

    def workspace_center(self, user):
        user = self.require_login(user)
        if not user:
            return
        data = self.workspace_payload(user)
        body = f"<div class='panel'><h2>{U(r'\u6211\u7684\u5de5\u4f5c\u53f0')}</h2><p class='small'>{U(r'\u6c47\u603b\u6211\u7684\u4efb\u52a1\u3001\u901a\u77e5\u3001\u62a5\u544a\u3001AI \u5bf9\u8bdd\u548c\u5f85\u5ba1\u4e8b\u9879\u3002')}</p></div><div class='split'><div class='panel'><h2>{U(r'\u6211\u7684\u4efb\u52a1')}</h2>{self.bullets([t['title'] for t in data['tasks']] or [data['empty_message']])}</div><div class='panel'><h2>{U(r'\u6211\u7684\u901a\u77e5')}</h2>{self.bullets([n['title'] for n in data['notifications']] or [U(r'\u6682\u65e0\u901a\u77e5\u3002')])}</div></div>"
        self.out(layout(U(r"\u5de5\u4f5c\u53f0"), body, user=user, wide=True))

    def boss_workspace(self, user):
        user = self.require_login(user)
        if not user:
            return
        if user["role"] not in ("boss", "admin", "finance"):
            return self.dashboard(user)
        data = self.cockpit_data()
        body = f"<div class='panel'><h2>{U(r'\u8001\u677f\u5de5\u4f5c\u53f0')}</h2><p class='small'>{U(r'AI CEO\u3001\u91cd\u70b9\u98ce\u9669\u3001\u5f85\u51b3\u7b56\u3001\u4eca\u65e5\u4efb\u52a1\u548c\u7814\u7a76\u7b80\u62a5\u3002')}</p></div><div class='split'><div class='panel'><h2>{U(r'AI CEO')}</h2>{self.bullets(data['ai_suggestions'][:5] or [data['empty_message']])}<p><a class='btn dark' href='/ai-ceo'>AI CEO</a></p></div><div class='panel'><h2>{U(r'\u98ce\u9669')}</h2>{self.bullets([U(r'\u5e93\u5b58\u3001\u8d22\u52a1\u3001\u54c1\u724c\u3001HR \u548c\u7cfb\u7edf\u98ce\u9669\u7edf\u4e00\u8fdb\u5165\u98ce\u9669\u4e2d\u5fc3\u3002')])}<p><a class='btn' href='/risks'>{U(r'\u98ce\u9669\u4e2d\u5fc3')}</a></p></div></div>"
        self.out(layout(U(r"\u8001\u677f\u5de5\u4f5c\u53f0"), body, user=user, wide=True))

    def employee_workspace(self, user):
        user = self.require_login(user)
        if not user:
            return
        body = f"<div class='panel'><h2>{U(r'\u5458\u5de5\u5de5\u4f5c\u53f0')}</h2>{self.bullets([U(r'\u4eca\u65e5\u4efb\u52a1'), U(r'\u79fb\u52a8\u63d0\u4ea4'), U(r'\u57f9\u8bad'), U(r'\u987e\u5ba2\u8ddf\u8fdb'), U(r'\u4e0a\u4f20\u77e5\u8bc6'), U(r'\u95ee AI')])}</div><div class='grid'>{self.card(U(r'\u4efb\u52a1'), U(r'\u67e5\u770b\u4eca\u65e5\u5f85\u529e'), '/tasks', 'btn', True)}{self.card(U(r'\u79fb\u52a8\u5916\u52e4'), U(r'\u4e0a\u4f20\u95e8\u5e97\u7b14\u8bb0\u548c\u56fe\u7247'), '/mobile', 'btn green', True)}{self.card(U(r'\u987e\u5ba2\u8ddf\u8fdb'), U(r'\u4f1a\u5458\u548c\u79c1\u57df\u8ddf\u8fdb'), '/customer-growth', 'btn orange', True)}</div>"
        self.out(layout(U(r"\u5458\u5de5\u5de5\u4f5c\u53f0"), body, user=user, wide=True))

    def settings_center(self, user):
        user = self.require_login(user)
        if not user:
            return
        if user["role"] != "admin":
            return self.dashboard(user)
        body = f"<div class='panel'><h2>{U(r'\u7cfb\u7edf\u8bbe\u7f6e')}</h2>{self.bullets([U(r'\u516c\u53f8\u8bbe\u7f6e'), U(r'\u6a21\u5757\u8bbe\u7f6e'), U(r'AI \u8bbe\u7f6e\u5360\u4f4d'), U(r'\u641c\u7d22\u8bbe\u7f6e'), U(r'\u901a\u77e5\u8bbe\u7f6e'), U(r'\u5b89\u5168\u8bbe\u7f6e'), U(r'\u96c6\u6210\u8bbe\u7f6e')])}</div>"
        self.out(layout(U(r"\u7cfb\u7edf\u8bbe\u7f6e"), body, user=user, wide=True))

    def system_modules_page(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_view_system(user):
            return self.dashboard(user)
        cards = "".join(self.card(name, key + " · healthy", route, "btn", True) for key, name, route, cat, perm in self.platform_modules())
        self.out(layout(U(r"\u6a21\u5757\u5065\u5eb7"), f"<div class='grid'>{cards}</div>", user=user, wide=True))

    def data_readiness_payload(self):
        areas = ["sap_data","store_archives","employee_archives","brand_archives","product_archives","supplier_archives","customer_archives","documents","knowledge","research","memory","tasks","reports"]
        return [{"area": a, "level": "partial" if a in ("tasks","knowledge") else "empty", "message": self.cockpit_data()["empty_message"]} for a in areas]

    def data_readiness_page(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_view_system(user):
            return self.dashboard(user)
        self.out(layout(U(r"\u6570\u636e\u5c31\u7eea\u5ea6"), "<div class='panel'>" + self.bullets([x["area"] + " · " + x["level"] for x in self.data_readiness_payload()]) + "</div>", user=user, wide=True))

    def notification_center(self, user):
        user = self.require_login(user)
        if not user:
            return
        with db() as conn:
            rows = conn.execute("select * from notifications order by created_at desc limit 80").fetchall()
        items = [r["title"] + " · " + r["status"] for r in rows] or [U(r"\u6682\u65e0\u901a\u77e5\u3002")]
        self.out(layout(U(r"\u901a\u77e5\u4e2d\u5fc3"), "<div class='panel'>" + self.bullets(items) + "</div>", user=user, wide=True))

    def risk_center(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_view_system(user) and user["role"] not in ("finance", "purchasing", "store_manager"):
            return self.dashboard(user)
        with db() as conn:
            rows = conn.execute("select * from system_risks order by updated_at desc limit 80").fetchall()
        items = [r["title"] + " · " + r["level"] + " · " + r["status"] for r in rows] or [U(r"\u6682\u65e0\u7edf\u4e00\u98ce\u9669\u8bb0\u5f55\u3002")]
        form = f"<div class='panel form'><h2>{U(r'\u65b0\u5efa\u98ce\u9669')}</h2><form method='post' action='/risks/save'><label>{U(r'\u6807\u9898')}</label><input name='title'><label>{U(r'\u7c7b\u578b')}</label><input name='risk_type'><label>{U(r'\u7b49\u7ea7')}</label><input name='level'><label>{U(r'\u5efa\u8bae')}</label><textarea name='recommended_action'></textarea><p><button>{U(r'\u4fdd\u5b58')}</button></p></form></div>"
        self.out(layout(U(r"\u98ce\u9669\u4e2d\u5fc3"), "<div class='panel'>" + self.bullets(items) + "</div>" + form, user=user, wide=True))

    def timeline_center(self, user):
        user = self.require_login(user)
        if not user:
            return
        with db() as conn:
            events = [row_dict(r) for r in conn.execute("select * from system_events order by created_at desc limit 80").fetchall()]
            logs = [row_dict(r) for r in conn.execute("select * from audit_logs order by created_at desc limit 40").fetchall()] if "audit_logs" in {x[0] for x in conn.execute("select name from sqlite_master where type='table'").fetchall()} else []
        items = [e["title"] + " · " + e["event_type"] for e in events] or [l.get("action","") + " · " + str(l.get("target_type","")) for l in logs] or [U(r"\u6682\u65e0\u5168\u5c40\u65f6\u95f4\u7ebf\u3002")]
        self.out(layout(U(r"\u5168\u5c40\u65f6\u95f4\u7ebf"), "<div class='panel'>" + self.bullets(items) + "</div>", user=user, wide=True))

    def risk_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        if not self.can_view_system(user) and user["role"] not in ("finance", "purchasing", "store_manager"):
            return self.redir("/")
        form = self.form()
        now = ts()
        with db() as conn:
            cur = conn.execute("insert into system_risks(risk_id,title,risk_type,level,object_type,object_id,evidence,recommended_action,status,owner,due_date,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?)", ("RK-"+uuid.uuid4().hex[:10], form.get("title",U(r"\u672a\u547d\u540d\u98ce\u9669")), form.get("risk_type",""), form.get("level","unknown"), form.get("object_type",""), form.get("object_id",""), form.get("evidence",""), form.get("recommended_action",""), form.get("status","new"), form.get("owner",user["name"]), form.get("due_date",""), now, now))
        self.log_action(user, "risk_created", "risk", cur.lastrowid, form.get("title",""))
        return self.redir("/risks")

    def notification_read(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        form = self.form()
        with db() as conn:
            conn.execute("update notifications set status='read', read_at=? where id=?", (ts(), form.get("id","0")))
        return self.redir("/notifications")

    def ai_context_packet(self, user, question=""):
        return {"user": {"id": user["id"], "role": user["role"], "store": user["store"]}, "permissions": [user["role"]], "question": question, "intent": "", "related_objects": [], "selected_sources": [], "knowledge_context": [], "research_context": [], "memory_context": [], "graph_context": [], "sap_context": self.cockpit_data()["metrics"], "task_context": [], "limitations": [self.cockpit_data()["empty_message"]], "timestamp": ts()}

    def api_platform_get(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if path == "/api/system/modules":
            return self.json_out({"ok": True, "modules": [{"module_key": k, "module_name": n, "route": r, "category": c, "health_status": "healthy"} for k,n,r,c,p in self.platform_modules()]})
        if path == "/api/system/objects":
            return self.json_out({"ok": True, "objects": self.platform_objects()})
        if path == "/api/system/health":
            return self.json_out(self.health_payload())
        if path == "/api/system/data-readiness":
            return self.json_out({"ok": True, "readiness": self.data_readiness_payload()})
        if path == "/api/search/global":
            q = parse_qs(urlparse(self.path).query).get("q", [""])[0]
            with db() as conn:
                rows = conn.execute("select title,summary,tags,updated_at,id from records where title like ? or summary like ? or tags like ? order by updated_at desc limit 20", (f"%{q}%", f"%{q}%", f"%{q}%")).fetchall() if q else []
            return self.json_out({"ok": True, "query": q, "results": [{"type": "record", "title": r["title"], "summary": r["summary"], "tags": r["tags"], "updated_at": r["updated_at"], "url": "/records/view?id="+str(r["id"])} for r in rows]})
        if path == "/api/workspace":
            return self.json_out(self.workspace_payload(user))
        if path == "/api/boss":
            return self.json_out({"ok": True, "cockpit": self.cockpit_data(), "workspace": "boss"})
        if path == "/api/employee-workspace":
            return self.json_out({"ok": True, "workspace": "employee", "sections": ["tasks","mobile","training","customer_followups","knowledge","ai"]})
        if path == "/api/settings":
            if user["role"] != "admin":
                return self.json_out({"ok": False, "message": "no permission"}, code=403)
            return self.json_out({"ok": True, "settings": [{"group": "ai", "status": "placeholder"}, {"group": "integration", "status": "env_only"}, {"group": "security", "status": "ready"}]})
        if path == "/api/ai/context-packet":
            q = parse_qs(urlparse(self.path).query).get("question", [""])[0]
            self.log_action(user, "ai_context_packet_generated", "ai_context", None, q)
            return self.json_out({"ok": True, "context_packet": self.ai_context_packet(user, q)})
        if path == "/api/risks":
            with db() as conn:
                rows = conn.execute("select * from system_risks order by updated_at desc limit 100").fetchall()
            return self.json_out({"ok": True, "risks": [row_dict(r) for r in rows]})
        if path == "/api/timeline/global":
            with db() as conn:
                rows = conn.execute("select * from system_events order by created_at desc limit 100").fetchall()
            return self.json_out({"ok": True, "events": [row_dict(r) for r in rows]})
        return self.json_out({"ok": False, "message": "unknown platform api"}, code=404)

    def api_platform_post(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        form = self.form()
        if path.startswith("/api/notifications/") and path.endswith("/read"):
            nid = path.strip("/").split("/")[-2]
            with db() as conn:
                conn.execute("update notifications set status='read', read_at=? where id=? or notification_id=?", (ts(), nid, nid))
            self.log_action(user, "notification_read", "notification", None, nid)
            return self.json_out({"ok": True})
        if path == "/api/risks":
            now = ts()
            with db() as conn:
                cur = conn.execute("insert into system_risks(risk_id,title,risk_type,level,object_type,object_id,evidence,recommended_action,status,owner,due_date,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?)", ("RK-"+uuid.uuid4().hex[:10], form.get("title",U(r"\u672a\u547d\u540d\u98ce\u9669")), form.get("risk_type",""), form.get("level","unknown"), form.get("object_type",""), form.get("object_id",""), form.get("evidence",""), form.get("recommended_action",""), form.get("status","new"), form.get("owner",user["name"]), form.get("due_date",""), now, now))
            self.log_action(user, "risk_created", "risk", cur.lastrowid, form.get("title",""))
            return self.json_out({"ok": True, "id": cur.lastrowid})
        return self.json_out({"ok": False, "message": "unknown platform write api"}, code=404)

    def api_platform_put(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if user["role"] != "admin":
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        return self.json_out({"ok": True, "message": U(r"\u7cfb\u7edf\u8bbe\u7f6e API \u5df2\u9884\u7559\uff0c\u5bc6\u94a5\u4ec5\u5141\u8bb8\u73af\u5883\u53d8\u91cf\u914d\u7f6e\u3002")})

    def can_manage_sap_sync(self, user):
        return bool(user and user["role"] in ("boss", "admin", "finance", "purchasing"))

    def sap_sync_config_status(self):
        required = ["SAP_HOST", "SAP_DB", "SAP_USER", "SAP_PASSWORD"]
        missing = [k for k in required if not os.environ.get(k) or os.environ.get(k) == "change-me"]
        if missing:
            return False, [U(r"\u7f3a\u5c11\u6216\u672a\u6b63\u5f0f\u914d\u7f6e\uff1a") + ", ".join(missing), U(r"\u5bc6\u7801\u4e0d\u5141\u8bb8\u5199\u5165 GitHub\uff0c\u8bf7\u5728 .env \u6216\u670d\u52a1\u5668\u73af\u5883\u53d8\u91cf\u914d\u7f6e\u3002")]
        return True, [U(r"SAP \u8fde\u63a5\u73af\u5883\u53d8\u91cf\u5df2\u914d\u7f6e\uff0cAPI \u4e0d\u8fd4\u56de\u5bc6\u94a5\u3002")]

    def sap_sync_freshness(self, last_row=None):
        now = ts()
        if not last_row:
            return "unknown", U(r"SAP \u6570\u636e\u5c1a\u672a\u540c\u6b65\uff0cAI \u7ecf\u8425\u5206\u6790\u53ef\u80fd\u4e0d\u5b8c\u6574\u3002")
        if last_row["status"] in ("failed", "partial_success"):
            return "error", U(r"SAP \u540c\u6b65\u6700\u8fd1\u5931\u8d25\u6216\u90e8\u5206\u5931\u8d25\uff0cAI \u4e0d\u5e94\u505a\u5f3a\u7ed3\u8bba\u3002")
        finished = last_row["finished_at"] or last_row["started_at"] or 0
        age = now - finished
        if age <= 24 * 3600:
            return "fresh", U(r"\u57fa\u4e8e\u6700\u65b0 SAP \u540c\u6b65\u6570\u636e\u3002")
        if age <= 48 * 3600:
            return "stale", U(r"SAP \u6570\u636e\u8d85\u8fc7 24 \u5c0f\u65f6\u672a\u66f4\u65b0\uff0cAI \u5206\u6790\u9700\u8c28\u614e\u3002")
        return "outdated", U(r"SAP \u6570\u636e\u8d85\u8fc7 48 \u5c0f\u65f6\u672a\u66f4\u65b0\uff0c\u8bf7\u68c0\u67e5\u540c\u6b65\u3002")

    def sap_sync_status_payload(self):
        with db() as conn:
            history_rows = conn.execute("select * from sap_sync_history order by started_at desc, id desc limit 30").fetchall()
            last = history_rows[0] if history_rows else None
            lock = conn.execute("select * from job_locks where job_name='sap_b1_sync'").fetchone()
        configured, config_status = self.sap_sync_config_status()
        freshness, warning = self.sap_sync_freshness(last)
        return {
            "ok": True,
            "enabled": os.environ.get("SAP_SYNC_ENABLED", "true").lower() == "true",
            "schedule_time": os.environ.get("SAP_SYNC_TIME", "22:00"),
            "timezone": os.environ.get("APP_TIMEZONE", "Asia/Shanghai"),
            "next_run_time": os.environ.get("SAP_SYNC_TIME", "22:00"),
            "last_status": last["status"] if last else "never_run",
            "last_sync_time": dt(last["finished_at"] or last["started_at"]) if last else U(r"\u4ece\u672a\u540c\u6b65"),
            "freshness": freshness,
            "warning": warning,
            "configured": configured,
            "config_status": config_status,
            "lock": row_dict(lock) if lock else {"job_name": "sap_b1_sync", "lock_status": "free"},
            "history": [row_dict(r) for r in history_rows],
        }

    def sap_connector_payload(self):
        configured, config_status = self.sap_sync_config_status()
        return {
            "ok": True,
            "system_of_record": "SAP",
            "connector": {
                "key": "sap_b1",
                "mode": os.environ.get("SAP_DB_TYPE", "sqlserver"),
                "db_direct_available": bool(os.environ.get("SAP_DB_HOST") or os.environ.get("SAP_HOST")),
                "service_layer_available": bool(os.environ.get("SAP_API_BASE_URL")),
                "configured": configured,
                "config_status": config_status,
                "write_policy": "read_only_until_explicit_business_rules",
            },
            "sync_interfaces": [
                {"object": "products", "mode": "incremental", "status": "contract_ready"},
                {"object": "inventory", "mode": "incremental", "status": "contract_ready"},
                {"object": "members", "mode": "incremental", "status": "contract_ready"},
                {"object": "sales", "mode": "incremental", "status": "contract_ready"},
                {"object": "purchasing", "mode": "incremental", "status": "contract_ready"},
            ],
            "retry_policy": {
                "safe_retry": True,
                "conflict_detection": "planned",
                "audit_log": "sap_sync_history",
            },
        }

    def run_sap_sync_stub(self, trigger_type="manual", user=None, retry_sync_id=""):
        if not self.can_manage_sap_sync(user):
            return {"ok": False, "message": "no permission"}, 403
        now = ts()
        timeout = int(os.environ.get("SAP_SYNC_LOCK_TIMEOUT_MINUTES", "120") or 120) * 60
        with db() as conn:
            lock = conn.execute("select * from job_locks where job_name='sap_b1_sync'").fetchone()
            if lock and lock["lock_status"] == "running" and (lock["expires_at"] or 0) > now:
                return {"ok": False, "message": "SAP sync is already running."}, 409
            conn.execute("insert or replace into job_locks(job_name,lock_status,locked_at,locked_by,expires_at) values(?,?,?,?,?)", ("sap_b1_sync", "running", now, str(user["id"]), now + timeout))
            sync_id = "SAP-" + uuid.uuid4().hex[:10]
            configured, config_status = self.sap_sync_config_status()
            status = "skipped" if not configured else "pending"
            error = "" if configured else U(r"SAP \u73af\u5883\u53d8\u91cf\u672a\u5b8c\u6574\uff0c\u672c\u6b21\u4e0d\u6267\u884c\u771f\u5b9e\u540c\u6b65\u3002")
            cur = conn.execute("insert into sap_sync_history(sync_id,job_name,trigger_type,status,started_at,finished_at,duration_seconds,records_read,records_written,records_updated,records_failed,error_message,log_path,created_by) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (sync_id, "sap_b1_sync", trigger_type, status, now, now, 0, 0, 0, 0, 0, error, "", user["id"]))
            conn.execute("update job_locks set lock_status='free', expires_at=? where job_name='sap_b1_sync'", (now,))
            conn.execute("insert into notifications(notification_id,channel,title,body,recipient_user_id,status,related_object_type,related_object_id,created_by,created_at) values(?,?,?,?,?,?,?,?,?,?)", ("N-"+uuid.uuid4().hex[:10], "in_app", U(r"SAP \u540c\u6b65") + " " + status, error or U(r"SAP \u540c\u6b65\u5df2\u8bb0\u5f55\uff0c\u8bf7\u5728\u670d\u52a1\u5668\u8c03\u5ea6\u4e2d\u6267\u884c\u771f\u5b9e\u540c\u6b65\u547d\u4ee4\u3002"), user["id"], "unread", "sap_sync", cur.lastrowid, user["id"], now))
        self.log_action(user, "sap_sync_triggered", "sap_sync", cur.lastrowid, trigger_type)
        return {"ok": True, "sync_id": sync_id, "status": status, "message": error or U(r"SAP \u540c\u6b65\u4efb\u52a1\u5df2\u8bb0\u5f55\u3002")}, 200

    def data_pipeline_payload(self):
        sap = self.sap_sync_status_payload()
        return {"ok": True, "pipelines": [
            {"name": "SAP B1 Sync", "status": sap["last_status"], "last_run": sap["last_sync_time"], "next_run": sap["next_run_time"], "records_processed": 0, "error_count": 0 if sap["last_status"] not in ("failed","error") else 1, "url": "/sap-sync"},
            {"name": "Document Processing", "status": "ready", "last_run": "", "next_run": "on_upload", "records_processed": 0, "error_count": 0, "url": "/documents"},
            {"name": "Knowledge Processing", "status": "ready", "last_run": "", "next_run": "on_review", "records_processed": 0, "error_count": 0, "url": "/knowledge"},
            {"name": "AI Context Processing", "status": "ready", "last_run": "", "next_run": "on_request", "records_processed": 0, "error_count": 0, "url": "/jarvis"},
            {"name": "Report Generation", "status": "ready", "last_run": "", "next_run": "manual", "records_processed": 0, "error_count": 0, "url": "/reports"},
            {"name": "Automation Jobs", "status": "ready", "last_run": "", "next_run": "manual", "records_processed": 0, "error_count": 0, "url": "/automation"},
        ]}

    def data_pipeline_page(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_manage_sap_sync(user):
            return self.dashboard(user)
        cards = "".join(self.card(p["name"], p["status"] + " · " + U(r"\u4e0b\u6b21 ") + str(p["next_run"]), p["url"], "btn", True) for p in self.data_pipeline_payload()["pipelines"])
        self.out(layout(U(r"\u6570\u636e\u7ba1\u9053"), "<div class='grid'>" + cards + "</div>", user=user, wide=True))

    def api_sap_sync_get(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_manage_sap_sync(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        if path == "/api/sap/sync/connector":
            return self.json_out(self.sap_connector_payload())
        if path == "/api/sap/sync/status":
            return self.json_out(self.sap_sync_status_payload())
        if path == "/api/sap/sync/history":
            return self.json_out({"ok": True, "history": self.sap_sync_status_payload()["history"]})
        if path == "/api/sap/sync/health":
            s = self.sap_sync_status_payload()
            return self.json_out({"ok": True, "scheduler_enabled": s["enabled"], "freshness": s["freshness"], "last_status": s["last_status"], "next_run_time": s["next_run_time"]})
        if path.startswith("/api/sap/sync/logs/"):
            return self.json_out({"ok": True, "message": U(r"\u65e5\u5fd7\u8def\u5f84\u4ec5\u663e\u793a\u5b89\u5168\u5360\u4f4d\uff0c\u4e0d\u8fd4\u56de\u8fde\u63a5\u4e32\u6216\u5bc6\u94a5\u3002"), "log": ""})
        if path == "/api/data-pipeline":
            return self.json_out(self.data_pipeline_payload())
        if path == "/api/system/data-freshness":
            s = self.sap_sync_status_payload()
            return self.json_out({"ok": True, "sap_data_freshness": s["freshness"], "warning": s["warning"]})
        return self.json_out({"ok": False, "message": "unknown sap sync api"}, code=404)

    def api_sap_sync_post(self, user, path):
        if path == "/api/sap/sync/run":
            result, code = self.run_sap_sync_stub("manual", user)
            return self.json_out(result, code=code)
        if path.startswith("/api/sap/sync/retry/"):
            sync_id = path.rsplit("/", 1)[-1]
            result, code = self.run_sap_sync_stub("retry", user, retry_sync_id=sync_id)
            return self.json_out(result, code=code)
        return self.json_out({"ok": False, "message": "unknown sap sync write api"}, code=404)

    def app_permission_status(self, user, permission_required):
        if not user:
            return "login_required"
        role = user["role"]
        if role == "admin":
            return "allowed"
        if permission_required in ("view_workspace", "employee") and role in ("boss", "finance", "purchasing", "store_manager", "employee"):
            return "allowed"
        if permission_required == "boss" and role in ("boss", "finance", "purchasing"):
            return "allowed"
        if permission_required == "store_manager" and role in ("boss", "finance", "purchasing", "store_manager"):
            return "allowed"
        if permission_required == "finance" and role in ("boss", "finance"):
            return "allowed"
        if permission_required == "purchasing" and role in ("boss", "purchasing", "finance"):
            return "allowed"
        return "disabled"

    def os_apps_payload(self, user):
        readiness = {x["area"]: x["level"] for x in self.data_readiness_payload()}
        apps = []
        category_map = {"ai": "AI Command", "operation": "Business Operations", "knowledge": "Knowledge & Data", "execution": "Execution", "system": "System"}
        for key, name, route, category, permission in self.platform_modules():
            status = self.app_permission_status(user, permission)
            apps.append({"module_key": key, "app_name": name, "route": route, "category": category_map.get(category, category), "status": "healthy", "permission_status": status, "data_readiness": readiness.get("sap_data", "partial" if category != "system" else "ready"), "description": key.replace("_", " ")})
        return {"ok": True, "apps": apps, "data_freshness": self.sap_sync_status_payload()["freshness"]}

    def apps_launcher(self, user):
        user = self.require_login(user)
        if not user:
            return
        apps = self.os_apps_payload(user)["apps"]
        cards = "".join(self.card(a["app_name"], a["category"] + " · " + a["permission_status"] + " · " + a["data_readiness"], a["route"] if a["permission_status"] == "allowed" else "/desktop", "btn" if a["permission_status"] == "allowed" else "btn gray", True) for a in apps)
        self.out(layout(U(r"\u5e94\u7528\u542f\u52a8\u5668"), "<div class='grid'>" + cards + "</div>", user=user, wide=True))

    def os_work_queue_payload(self, user):
        with db() as conn:
            tasks = [row_dict(r) for r in conn.execute("select id,task_id,title,priority,owner,due_date,status,related_object_type,source_type from tasks where status!='done' order by case priority when 'urgent' then 0 when 'high' then 1 else 2 end, updated_at desc limit 30").fetchall()]
            knowledge = [row_dict(r) for r in conn.execute("select id,title,status,updated_at from knowledge_items where status in ('draft','pending_review') order by updated_at desc limit 10").fetchall()]
            risks = [row_dict(r) for r in conn.execute("select id,risk_id,title,level,status,owner,due_date from system_risks where status!='resolved' order by updated_at desc limit 20").fetchall()]
        items = []
        for t in tasks:
            items.append({"item_id": t.get("task_id") or str(t["id"]), "item_type": "task", "title": t["title"], "priority": t["priority"], "owner": t["owner"], "due_at": t["due_date"], "related_object": t["related_object_type"], "status": t["status"], "source_module": t["source_type"], "action_url": "/tasks"})
        for k in knowledge:
            items.append({"item_id": str(k["id"]), "item_type": "knowledge_approval", "title": k["title"], "priority": "normal", "owner": "", "due_at": "", "related_object": "knowledge", "status": k["status"], "source_module": "knowledge", "action_url": "/knowledge/view?id=" + str(k["id"])})
        for r in risks:
            items.append({"item_id": r.get("risk_id") or str(r["id"]), "item_type": "risk", "title": r["title"], "priority": r["level"], "owner": r["owner"], "due_at": r["due_date"], "related_object": "risk", "status": r["status"], "source_module": "risk_center", "action_url": "/risks"})
        return {"ok": True, "items": items, "empty_message": self.cockpit_data()["empty_message"]}

    def os_approvals_payload(self, user):
        with db() as conn:
            reports = [row_dict(r) for r in conn.execute("select id,title,status,updated_at from reports where status in ('draft','pending_review','generated') order by updated_at desc limit 20").fetchall()] if "reports" in {x[0] for x in conn.execute("select name from sqlite_master where type='table'").fetchall()} else []
            content = [row_dict(r) for r in conn.execute("select id,title,status,updated_at from content_items where status in ('draft','pending_review','review') order by updated_at desc limit 20").fetchall()] if "content_items" in {x[0] for x in conn.execute("select name from sqlite_master where type='table'").fetchall()} else []
            markdowns = [row_dict(r) for r in conn.execute("select id,markdown_id,brand_id,approval_status,created_at from markdown_suggestions where approval_status='pending_review' order by created_at desc limit 20").fetchall()]
        items = []
        for r in reports:
            items.append({"approval_id": "report-" + str(r["id"]), "type": "report", "title": r["title"], "status": r["status"], "url": "/reports"})
        for c in content:
            items.append({"approval_id": "content-" + str(c["id"]), "type": "content", "title": c["title"], "status": c["status"], "url": "/content"})
        for m in markdowns:
            items.append({"approval_id": "markdown-" + str(m["id"]), "type": "markdown", "title": (m["brand_id"] or "") + " markdown", "status": m["approval_status"], "url": "/inventory-decision"})
        return {"ok": True, "approvals": items}

    def os_context_payload(self, user):
        base = self.ai_context_packet(user, "")
        base.update({"current_app": "", "current_object": {}, "current_workspace": "desktop", "user_role": user["role"], "visible_modules": [a for a in self.os_apps_payload(user)["apps"] if a["permission_status"] == "allowed"], "pending_work_items": self.os_work_queue_payload(user)["items"][:10], "data_freshness": self.sap_sync_status_payload(), "system_health": self.health_payload(), "recent_decisions": [], "active_risks": self.api_platform_get_risks_for_context()})
        return base

    def api_platform_get_risks_for_context(self):
        with db() as conn:
            return [row_dict(r) for r in conn.execute("select * from system_risks where status!='resolved' order by updated_at desc limit 10").fetchall()]

    def role_desktop(self, user):
        user = self.require_login(user)
        if not user:
            return
        role = user["role"]
        if role in ("boss", "finance", "purchasing"):
            return self.boss_workspace(user)
        if role == "admin":
            cards = [self.card(U(r"\u7cfb\u7edf\u5065\u5eb7"), U(r"\u6a21\u5757\u3001\u6570\u636e\u7ba1\u9053\u3001\u540c\u6b65\u548c\u5347\u7ea7\u72b6\u6001\u3002"), "/system/modules", "btn dark", True), self.card(U(r"SAP \u540c\u6b65"), U(r"\u6bcf\u665a 22:00 \u540c\u6b65\u72b6\u6001\u3002"), "/sap-sync", "btn", True), self.card(U(r"\u5e94\u7528\u542f\u52a8\u5668"), U(r"\u6240\u6709\u6a21\u5757\u5165\u53e3\u3002"), "/apps", "btn green", True)]
            self.out(layout(U(r"\u7ba1\u7406\u5458\u684c\u9762"), "<div class='grid'>" + "".join(cards) + "</div>", user=user, wide=True))
            return
        if role == "employee":
            return self.employee_workspace(user)
        data = self.os_work_queue_payload(user)
        body = f"<div class='panel'><h2>{U(r'\u7ecf\u7406\u684c\u9762')}</h2>{self.bullets([i['title'] for i in data['items'][:8]] or [data['empty_message']])}</div><div class='grid'>{self.card(U(r'\u95e8\u5e97\u589e\u957f'), U(r'\u95e8\u5e97\u4efb\u52a1\u3001\u987e\u5ba2\u8ddf\u8fdb\u3001\u5e93\u5b58\u95ee\u9898\u3002'), '/store-growth', 'btn green', True)}{self.card(U(r'\u5de5\u4f5c\u961f\u5217'), U(r'\u8de8\u6a21\u5757\u9700\u5904\u7406\u4e8b\u9879\u3002'), '/work-queue', 'btn', True)}{self.card(U(r'\u5ba1\u6279'), U(r'\u7edf\u4e00\u5ba1\u6279\u6536\u4ef6\u7bb1\u3002'), '/approvals', 'btn orange', True)}</div>"
        self.out(layout(U(r"\u89d2\u8272\u684c\u9762"), body, user=user, wide=True))

    def command_center(self, user):
        user = self.require_login(user)
        if not user:
            return
        queue = self.os_work_queue_payload(user)["items"]
        sap = self.sap_sync_status_payload()
        body = f"<div class='panel'><h2>{U(r'\u7edf\u4e00\u547d\u4ee4\u4e2d\u5fc3')}</h2><div class='metrics'>{self.metric(U(r'\u6570\u636e\u65b0\u9c9c\u5ea6'), sap['freshness'], sap['next_run_time'])}{self.metric(U(r'\u5f85\u5904\u7406'), money(len(queue)), U(r'\u5de5\u4f5c\u961f\u5217'))}{self.metric(U(r'\u7cfb\u7edf\u72b6\u6001'), self.health_payload()['status'], self.health_payload()['app_version'])}</div></div><div class='split'><div class='panel'><h2>{U(r'\u5efa\u8bae\u52a8\u4f5c')}</h2>{self.bullets([U(r'\u67e5\u770b\u98ce\u9669\u4e2d\u5fc3'), U(r'\u68c0\u67e5 SAP \u540c\u6b65'), U(r'\u5904\u7406\u5ba1\u6279\u6536\u4ef6\u7bb1')])}</div><div class='panel'><h2>{U(r'\u5f85\u5904\u7406')}</h2>{self.bullets([i['title'] for i in queue[:8]] or [self.cockpit_data()['empty_message']])}</div></div>"
        self.out(layout(U(r"\u547d\u4ee4\u4e2d\u5fc3"), body, user=user, wide=True))

    def work_queue_page(self, user):
        user = self.require_login(user)
        if not user:
            return
        data = self.os_work_queue_payload(user)
        self.out(layout(U(r"\u5de5\u4f5c\u961f\u5217"), "<div class='panel'>" + self.bullets([i["item_type"] + " · " + i["title"] + " · " + i["status"] for i in data["items"]] or [data["empty_message"]]) + "</div>", user=user, wide=True))

    def approvals_page(self, user):
        user = self.require_login(user)
        if not user:
            return
        data = self.os_approvals_payload(user)
        self.out(layout(U(r"\u5ba1\u6279\u6536\u4ef6\u7bb1"), "<div class='panel'>" + self.bullets([i["type"] + " · " + i["title"] + " · " + i["status"] for i in data["approvals"]] or [U(r"\u6682\u65e0\u5f85\u5ba1\u6279\u4e8b\u9879\u3002")]) + "</div>", user=user, wide=True))

    def system_upgrade_page(self, user):
        user = self.require_login(user)
        if not user:
            return
        if user["role"] != "admin":
            return self.dashboard(user)
        completed = [f"Task{n:03d}" for n in range(1, 23)]
        body = f"<div class='panel'><h2>{U(r'\u7cfb\u7edf\u72b6\u6001\u4e0e\u5347\u7ea7\u4e2d\u5fc3')}</h2>{self.bullets([self.health_payload()['app_version'], U(r'\u5df2\u5b8c\u6210\uff1a') + ', '.join(completed[-8:]), U(r'\u5efa\u8bae\u4e0b\u4e00\u6b65\uff1a\u8fde\u63a5\u771f\u5b9e SAP \u8c03\u5ea6\u548c\u751f\u4ea7\u90e8\u7f72\u9a8c\u8bc1\u3002')])}</div>"
        self.out(layout(U(r"\u5347\u7ea7\u4e2d\u5fc3"), body, user=user, wide=True))

    def object_actions_payload(self):
        actions = ["open", "edit", "add_note", "add_tag", "add_relationship", "add_timeline_event", "upload_document", "ask_jarvis", "create_task", "create_decision", "create_risk", "generate_report", "view_graph", "view_history"]
        return {"ok": True, "actions": actions}

    def context_bar_payload(self):
        tabs = ["Overview", "Sales", "Inventory", "Documents", "Knowledge", "Research", "Risks", "Decisions", "Tasks", "Reports", "Graph", "Ask Jarvis"]
        return {"ok": True, "tabs": tabs}

    def command_palette_payload(self, user):
        commands = [
            ("ask_jarvis", "Ask Jarvis", "/jarvis"),
            ("search", "Search everything", "/knowledge/query"),
            ("create_task", "Create task", "/tasks"),
            ("upload_document", "Upload document", "/upload"),
            ("create_report", "Create report", "/reports"),
            ("open_ai_ceo", "Open AI CEO", "/ai-ceo"),
            ("open_sap_sync", "Open SAP Sync", "/sap-sync"),
            ("open_risk_center", "Open Risk Center", "/risks"),
            ("open_decision_center", "Open Decision Center", "/decisions"),
            ("create_store_note", "Create store note", "/mobile"),
            ("create_customer_followup", "Create customer follow-up", "/customer-growth"),
            ("generate_content_draft", "Generate content draft", "/content"),
        ]
        return {"ok": True, "commands": [{"command": c, "title": t, "url": u, "status": "ready"} for c, t, u in commands]}

    def api_os_layer_get(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if path == "/api/apps":
            return self.json_out(self.os_apps_payload(user))
        if path == "/api/desktop":
            return self.json_out({"ok": True, "role": user["role"], "recommended_route": "/boss" if user["role"] in ("boss", "finance", "purchasing") else ("/system/modules" if user["role"] == "admin" else "/employee-workspace" if user["role"] == "employee" else "/desktop")})
        if path == "/api/command-center":
            return self.json_out({"ok": True, "work_queue": self.os_work_queue_payload(user)["items"][:10], "sap": self.sap_sync_status_payload(), "health": self.health_payload()})
        if path == "/api/command-palette":
            return self.json_out(self.command_palette_payload(user))
        if path == "/api/object-actions":
            return self.json_out(self.object_actions_payload())
        if path == "/api/context-bar":
            return self.json_out(self.context_bar_payload())
        if path == "/api/work-queue":
            return self.json_out(self.os_work_queue_payload(user))
        if path == "/api/approvals":
            return self.json_out(self.os_approvals_payload(user))
        if path == "/api/os/data-freshness":
            s = self.sap_sync_status_payload()
            return self.json_out({"ok": True, "sap": s["freshness"], "knowledge": "ready", "research": "placeholder", "health": s["last_status"], "next_sap_sync": s["next_run_time"]})
        if path == "/api/system/upgrade":
            return self.json_out({"ok": True, "version": self.health_payload()["app_version"], "completed_tasks": [f"Task{n:03d}" for n in range(1, 23)], "pending_tasks": [], "suggested_next_upgrades": ["production deployment verification", "real SAP cron/systemd activation"]})
        if path == "/api/os/context":
            return self.json_out({"ok": True, "context": self.os_context_payload(user)})
        return self.json_out({"ok": False, "message": "unknown os layer api"}, code=404)

    def api_os_layer_post(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        form = self.form()
        if path == "/api/command-palette/execute":
            command = form.get("command", "")
            self.log_action(user, "command_palette_executed", "os_command", None, command)
            return self.json_out({"ok": True, "command": command, "message": U(r"\u547d\u4ee4\u5df2\u8bb0\u5f55\uff0c\u5177\u4f53\u6267\u884c\u7531\u5bf9\u5e94\u6a21\u5757\u5904\u7406\u3002")})
        if path.startswith("/api/approvals/") and (path.endswith("/approve") or path.endswith("/reject")):
            action = "approve" if path.endswith("/approve") else "reject"
            self.log_action(user, "approval_" + action, "approval", None, path)
            return self.json_out({"ok": True, "action": action, "message": U(r"\u5ba1\u6279\u52a8\u4f5c\u5df2\u8bb0\u5f55\uff0cV1 \u4e0d\u76f4\u63a5\u6539\u52a8\u6e90\u5bf9\u8c61\u3002")})
        return self.json_out({"ok": False, "message": "unknown os layer write api"}, code=404)

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
        checks["multi_agent_engine_status"] = "ready"
        checks["jarvis_status"] = "ready"
        checks["reporting_engine_status"] = "ready"
        checks["content_engine_status"] = "ready"
        checks["mobile_field_engine_status"] = "ready"
        checks["enterprise_wechat_status"] = "placeholder"
        checks["store_growth_engine_status"] = "ready"
        checks["brand_growth_engine_status"] = "ready"
        checks["inventory_decision_engine_status"] = "ready"
        checks["finance_profit_engine_status"] = "ready"
        checks["hr_performance_engine_status"] = "ready"
        checks["customer_growth_engine_status"] = "ready"
        checks["platform_kernel_status"] = "ready"
        try:
            sap_status = self.sap_sync_status_payload()
            checks["sap_sync_scheduler_status"] = "enabled" if sap_status["enabled"] else "disabled"
            checks["sap_data_freshness"] = sap_status["freshness"]
            checks["sap_sync_next_run_time"] = sap_status["next_run_time"]
            checks["sap_sync_last_status"] = sap_status["last_status"]
        except Exception as exc:
            checks["sap_sync_scheduler_status"] = "error"
            checks["sap_sync_error"] = str(exc)
        checks["operating_system_layer_status"] = "ready"
        checks["v5_enterprise_ai_os_status"] = "framework_ready"
        checks["enterprise_pack_01_status"] = "aligned"
        checks["enterprise_pack_02_sap_ai_status"] = "framework_ready"
        checks["enterprise_pack_03_knowledge_status"] = "framework_ready"
        checks["enterprise_pack_04_ai_agents_status"] = "framework_ready"
        checks["knowledge_ingestion_pipeline_status"] = "contract_ready"
        checks["knowledge_retrieval_contract_status"] = "contract_ready"
        checks["knowledge_governance_status"] = "ready"
        checks["agent_framework_status"] = "contract_ready"
        checks["agent_approval_policy_status"] = "high_risk_requires_human_review"
        checks["agent_audit_status"] = "activity_log"
        checks["enterprise_pack_05_dashboard_status"] = "framework_ready"
        checks["dashboard_data_service_status"] = "unified"
        checks["dashboard_alert_component_status"] = "decoupled"
        checks["dashboard_recommendation_component_status"] = "evidence_required"
        checks["enterprise_pack_06_automation_status"] = "framework_ready"
        checks["automation_scheduler_status"] = "contract_ready"
        checks["automation_retry_policy_status"] = "enabled"
        checks["automation_approval_policy_status"] = "high_risk_defaults_to_approval"
        checks["automation_audit_status"] = "enabled"
        checks["v6_autonomous_worker_status"] = "scheduled" if os.environ.get("APP_ENV", "production") else "local"
        checks["worker_jobs"] = {
            "sap_sync": os.environ.get("SAP_SYNC_TIME", "22:00"),
            "knowledge_index": os.environ.get("KNOWLEDGE_INDEX_TIME", "02:00"),
            "backup": os.environ.get("BACKUP_TIME", "03:00"),
            "daily_report": os.environ.get("DAILY_REPORT_TIME", "08:00"),
            "web_research": os.environ.get("WEB_RESEARCH_TIME", "10:00"),
            "weekly_report": os.environ.get("WEEKLY_REPORT_TIME", "MON 09:00"),
            "monthly_report_day": os.environ.get("MONTHLY_REPORT_DAY", "1"),
        }
        return {"status": "ok" if checks["database_status"] == "ok" else "degraded", "app_version": "FoxBrain V6 Autonomous Cloud Framework", "environment": os.environ.get("APP_ENV", "production"), **checks, "timestamp": now}

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
        action_type = form.get("action_type", "create_task")
        description = form.get("description", "")
        is_high_risk = self.automation_is_high_risk(action_type, name, description)
        risk_level = "high" if is_high_risk else "low"
        approval_required = 1 if is_high_risk else 0
        approval_status = "pending" if is_high_risk else "not_required"
        status = "pending_approval" if is_high_risk else "active"
        with db() as conn:
            cur = conn.execute(
                "insert into automations(automation_id,name,description,trigger_type,action_type,status,owner,ai_recommendation,created_by,created_at,updated_at,risk_level,approval_required,approval_status,retry_policy,max_retries,audit_status) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("AUTO-" + uuid.uuid4().hex[:10], name, description, form.get("trigger_type", "manual"), action_type, status, form.get("owner", user["name"]), U(r"\u7b49\u5f85 AI \u63a5\u5165\u540e\u6839\u636e\u6267\u884c\u5386\u53f2\u4f18\u5316\u6d41\u7a0b\u3002"), user["id"], now, now, risk_level, approval_required, approval_status, "standard", 3, "enabled"),
            )
            run_status = "blocked_by_approval" if is_high_risk else "pending"
            run_message = U(r"\u9ad8\u98ce\u9669\u81ea\u52a8\u5316\u5df2\u8fdb\u5165\u4eba\u5de5\u5ba1\u6279\uff0c\u5ba1\u6279\u524d\u4e0d\u6267\u884c\u3002") if is_high_risk else U(r"\u81ea\u52a8\u5316\u5df2\u521b\u5efa\uff0c\u7b49\u5f85\u89e6\u53d1\u5668\u6267\u884c\u3002")
            conn.execute("insert into automation_runs(run_id,automation_id,status,message,created_at,attempt_no,audit_event_id,approval_id) values(?,?,?,?,?,?,?,?)", ("RUN-" + uuid.uuid4().hex[:10], cur.lastrowid, run_status, run_message, now, 1, "activity_log", "pending" if is_high_risk else ""))
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
        if path == "/api/automation/framework":
            return self.json_out(self.automation_framework_payload(user))
        if path == "/api/automation/scheduler":
            return self.json_out(self.automation_scheduler_payload())
        if path == "/api/automation/retry-policy":
            return self.json_out(self.automation_retry_policy_payload())
        if path == "/api/automation/approval-policy":
            return self.json_out(self.automation_approval_policy_payload())
        if path == "/api/automation/notifications":
            return self.json_out(self.automation_notification_payload(user))
        if path == "/api/automation/audit":
            return self.json_out(self.automation_audit_payload())
        if path == "/api/automation/workflow-library":
            return self.json_out(self.automation_workflow_library_payload(user))
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
            name = form.get("name", U(r"\u672a\u547d\u540d\u81ea\u52a8\u5316"))
            description = form.get("description", "")
            action_type = form.get("action_type", "create_task")
            is_high_risk = self.automation_is_high_risk(action_type, name, description)
            risk_level = "high" if is_high_risk else "low"
            approval_required = 1 if is_high_risk else 0
            approval_status = "pending" if is_high_risk else "not_required"
            status = "pending_approval" if is_high_risk else form.get("status", "draft")
            with db() as conn:
                cur = conn.execute(
                    "insert into automations(automation_id,name,description,trigger_type,action_type,status,owner,created_by,created_at,updated_at,risk_level,approval_required,approval_status,retry_policy,max_retries,audit_status) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    ("AUTO-" + uuid.uuid4().hex[:10], name, description, form.get("trigger_type", "manual"), action_type, status, form.get("owner", user["name"]), user["id"], now, now, risk_level, approval_required, approval_status, form.get("retry_policy", "standard"), int(form.get("max_retries", "3") or 3), "enabled"),
                )
                conn.execute("insert into automation_runs(run_id,automation_id,status,message,created_at,attempt_no,audit_event_id,approval_id) values(?,?,?,?,?,?,?,?)", ("RUN-" + uuid.uuid4().hex[:10], cur.lastrowid, "blocked_by_approval" if is_high_risk else "pending", U(r"\u9ad8\u98ce\u9669\u81ea\u52a8\u5316\u5ba1\u6279\u524d\u4e0d\u6267\u884c\u3002") if is_high_risk else U(r"\u81ea\u52a8\u5316\u5df2\u521b\u5efa\uff0c\u7b49\u5f85\u89e6\u53d1\u3002"), now, 1, "activity_log", "pending" if is_high_risk else ""))
            self.log_action(user, "automation_api_create", "automation", cur.lastrowid, name)
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

    def can_view_agents(self, user):
        return bool(user)

    def can_manage_agents(self, user):
        return bool(user and user["role"] in ("boss", "admin", "store_manager"))

    def seed_agent_roles(self, conn):
        now = ts()
        agents = [
            ("AI CEO", U(r"AI \u603b\u7ecf\u7406"), U(r"\u7efc\u5408\u5224\u65ad\u3001\u4efb\u52a1\u5206\u89e3\u3001\u8de8\u90e8\u95e8\u534f\u540c\u548c\u6700\u7ec8\u5efa\u8bae\u3002"), "knowledge,memory,graph,tasks,sap"),
            ("AI CFO", U(r"AI \u8d22\u52a1\u603b\u76d1"), U(r"\u5229\u6da6\u3001\u73b0\u91d1\u6d41\u3001\u8fd4\u70b9\u3001\u8d39\u7528\u548c\u98ce\u9669\u8bc4\u4f30\u3002"), "sap,finance,memory"),
            ("AI COO", U(r"AI \u8fd0\u8425\u603b\u76d1"), U(r"\u95e8\u5e97\u6267\u884c\u3001\u6d41\u7a0b\u3001\u4efb\u52a1\u548c\u81ea\u52a8\u5316\u3002"), "tasks,automation,graph"),
            ("AI Store Manager", U(r"AI \u95e8\u5e97\u7ecf\u7406"), U(r"\u95e8\u5e97\u9500\u552e\u3001\u5458\u5de5\u3001\u4f1a\u5458\u548c\u6267\u884c\u5efa\u8bae\u3002"), "stores,tasks,knowledge"),
            ("AI Brand Manager", U(r"AI \u54c1\u724c\u7ecf\u7406"), U(r"\u54c1\u724c\u7b56\u7565\u3001\u4ef7\u683c\u4f53\u7cfb\u3001\u5e93\u5b58\u548c\u6e20\u9053\u98ce\u9669\u3002"), "brands,research,memory,graph"),
            ("AI Inventory Manager", U(r"AI \u5e93\u5b58\u7ecf\u7406"), U(r"\u5e93\u5b58\u538b\u529b\u3001\u6ede\u9500\u3001\u8c03\u62e8\u548c\u6e05\u8d27\u5efa\u8bae\u3002"), "inventory,sap,tasks"),
            ("AI Purchasing Manager", U(r"AI \u91c7\u8d2d\u7ecf\u7406"), U(r"\u91c7\u8d2d\u3001\u8865\u8d27\u3001\u4f9b\u5e94\u5546\u548c\u8d26\u671f\u3002"), "suppliers,inventory,workflow"),
            ("AI Marketing Manager", U(r"AI \u8425\u9500\u7ecf\u7406"), U(r"\u5185\u5bb9\u3001\u6d3b\u52a8\u3001\u54c1\u724c\u4f20\u64ad\u548c\u7d20\u6750\u3002"), "content,knowledge,research"),
            ("AI Training Manager", U(r"AI \u57f9\u8bad\u7ecf\u7406"), U(r"\u57f9\u8bad\u8bfe\u7a0b\u3001\u5458\u5de5\u6210\u957f\u548c\u77e5\u8bc6\u590d\u7528\u3002"), "employees,knowledge,tasks"),
            ("AI Customer Service", U(r"AI \u5ba2\u670d"), U(r"\u987e\u5ba2\u95ee\u9898\u3001\u552e\u540e\u3001\u4f1a\u5458\u7ef4\u62a4\u548c\u8bdd\u672f\u3002"), "members,knowledge"),
            ("AI Supplier Manager", U(r"AI \u4f9b\u5e94\u5546\u7ecf\u7406"), U(r"\u4f9b\u5e94\u5546\u3001\u5408\u540c\u3001\u8d26\u671f\u548c\u4f9b\u8d27\u98ce\u9669\u5206\u6790\u3002"), "suppliers,contracts,purchasing,workflow"),
            ("AI Secretary", U(r"AI \u79d8\u4e66"), U(r"\u4f1a\u8bae\u7eaa\u8981\u3001\u4efb\u52a1\u62c6\u89e3\u3001\u63d0\u9192\u548c\u8bb0\u5f55\u3002"), "tasks,memory,automation"),
            ("AI Meeting Manager", U(r"AI \u4f1a\u8bae\u7ecf\u7406"), U(r"\u4f1a\u8bae\u7eaa\u8981\u3001\u51b3\u8bae\u3001\u8ddf\u8fdb\u4efb\u52a1\u548c\u77e5\u8bc6\u5f52\u6863\u3002"), "meetings,tasks,knowledge,memory"),
            ("AI Analytics Manager", U(r"AI \u5206\u6790\u7ecf\u7406"), U(r"\u9500\u552e\u3001\u5e93\u5b58\u3001\u5229\u6da6\u3001\u4f1a\u5458\u548c\u95e8\u5e97\u7efc\u5408\u5206\u6790\u3002"), "sap,reports,knowledge,graph"),
            ("AI Risk Officer", U(r"AI \u98ce\u9669\u5b98"), U(r"\u5b9a\u4ef7\u3001\u5e93\u5b58\u3001\u5408\u540c\u3001\u4f9b\u5e94\u5546\u548c\u73b0\u91d1\u6d41\u98ce\u9669\u3002"), "graph,risk,memory"),
        ]
        for name, role, desc, scope in agents:
            if not conn.execute("select id from agent_roles where agent_name=?", (name,)).fetchone():
                conn.execute(
                    "insert into agent_roles(agent_id,agent_name,agent_role,description,responsibilities,tools,knowledge_scope,memory_scope,permission_scope,status,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?)",
                    ("AG-" + uuid.uuid4().hex[:10], name, role, desc, desc, scope, scope, scope, "role_based", "active", now, now),
                )
        tools = [
            ("Search Knowledge", U(r"\u641c\u7d22\u77e5\u8bc6\u5e93"), "query", "citations", "view_knowledge"),
            ("Search Research", U(r"\u641c\u7d22\u7814\u7a76\u7ed3\u679c"), "query", "sources", "view_research"),
            ("Search Memory", U(r"\u641c\u7d22\u5df2\u5ba1\u6838\u8bb0\u5fc6"), "query", "memories", "view_memory"),
            ("Query SAP Analysis", U(r"\u67e5\u8be2 SAP \u5206\u6790\u6458\u8981"), "query", "metrics", "view_sap"),
            ("Query Graph", U(r"\u67e5\u8be2\u4f01\u4e1a\u77e5\u8bc6\u56fe\u8c31"), "query", "relations", "view_graph"),
            ("Create Task", U(r"\u521b\u5efa\u4efb\u52a1\uff0c\u9700\u4eba\u5de5\u786e\u8ba4"), "task", "task_id", "approve_agent_action"),
            ("Create Report", U(r"\u751f\u6210\u62a5\u544a\u8349\u7a3f\uff0c\u9700\u4eba\u5de5\u5ba1\u6838"), "context", "report", "approve_agent_action"),
            ("Add Timeline", U(r"\u5199\u5165\u65f6\u95f4\u8f74\uff0c\u9700\u4eba\u5de5\u5ba1\u6838"), "event", "timeline_id", "approve_agent_action"),
            ("Draft Content", U(r"\u751f\u6210\u5185\u5bb9\u8349\u7a3f"), "brief", "draft", "create_content"),
            ("Generate Summary", U(r"\u751f\u6210\u6458\u8981"), "text", "summary", "view_knowledge"),
            ("Price Decision Draft", U(r"\u751f\u6210\u4ef7\u683c\u8c03\u6574\u8349\u6848\uff0c\u5fc5\u987b\u4eba\u5de5\u5ba1\u6279"), "pricing_context", "approval_request", "approve_agent_action"),
            ("Contract Review Draft", U(r"\u5408\u540c\u5ba1\u6838\u5efa\u8bae\uff0c\u5fc5\u987b\u4eba\u5de5\u5ba1\u6279"), "contract_context", "approval_request", "approve_agent_action"),
            ("Finance Action Draft", U(r"\u8d22\u52a1\u652f\u4ed8\u6216\u8d44\u91d1\u5efa\u8bae\uff0c\u5fc5\u987b\u4eba\u5de5\u5ba1\u6279"), "finance_context", "approval_request", "approve_agent_action"),
            ("File Ingestion", U(r"\u6587\u4ef6\u4e0a\u4f20\u540e\u89e3\u6790\u5165\u5e93"), "file", "knowledge_item", "view_knowledge"),
            ("Send Notification Draft", U(r"\u751f\u6210\u901a\u77e5\u8349\u7a3f\uff0c\u53d1\u9001\u524d\u9700\u5ba1\u6838"), "message", "notification_draft", "approve_agent_action"),
        ]
        for name, desc, input_schema, output_schema, perm in tools:
            if not conn.execute("select id from agent_tools where tool_name=?", (name,)).fetchone():
                conn.execute(
                    "insert into agent_tools(tool_id,tool_name,description,input_schema,output_schema,permission_required,status,created_at,updated_at) values(?,?,?,?,?,?,?,?,?)",
                    ("TOOL-" + uuid.uuid4().hex[:10], name, desc, input_schema, output_schema, perm, "active", now, now),
                )
        categories = {
            "Search Knowledge": ("knowledge", "low", 0),
            "Search Research": ("knowledge", "medium", 0),
            "Search Memory": ("knowledge", "medium", 0),
            "Query SAP Analysis": ("sap", "medium", 0),
            "Query Graph": ("knowledge", "low", 0),
            "Create Task": ("workflow", "medium", 1),
            "Create Report": ("reporting", "medium", 1),
            "Add Timeline": ("workflow", "medium", 1),
            "Draft Content": ("files", "low", 0),
            "Generate Summary": ("knowledge", "low", 0),
            "Price Decision Draft": ("workflow", "high", 1),
            "Contract Review Draft": ("workflow", "high", 1),
            "Finance Action Draft": ("workflow", "high", 1),
            "File Ingestion": ("files", "low", 0),
            "Send Notification Draft": ("notifications", "medium", 1),
        }
        for tool_name, (category, risk, approval) in categories.items():
            conn.execute(
                "update agent_tools set tool_category=?, tool_version='v1', risk_level=?, approval_required=?, audit_event=? where tool_name=?",
                (category, risk, approval, "agent_tool_" + tool_name.lower().replace(" ", "_"), tool_name),
            )

    def agent_summary(self):
        with db() as conn:
            self.seed_agent_roles(conn)
            roles = conn.execute("select * from agent_roles order by id").fetchall()
            tasks = conn.execute("select * from agent_tasks order by updated_at desc limit 50").fetchall()
            discussions = conn.execute("select * from agent_discussions order by updated_at desc limit 30").fetchall()
            tools = conn.execute("select * from agent_tools order by id").fetchall()
        return {"roles": roles, "tasks": tasks, "discussions": discussions, "tools": tools}

    def safe_agent_output(self, agent_name, focus):
        return {
            "summary": U(r"\u7f3a\u5c11\u6570\u636e\uff0c\u65e0\u6cd5\u5f97\u51fa\u7ed3\u8bba\u3002"),
            "evidence": [],
            "assumptions": [U(r"\u5f53\u524d\u4ec5\u4f7f\u7528\u5df2\u63a5\u5165\u7684\u77e5\u8bc6\u3001\u8bb0\u5fc6\u3001\u56fe\u8c31\u548c SAP \u6458\u8981\u3002")],
            "risks": [U(r"\u4e0d\u80fd\u4f2a\u9020 SAP \u6570\u636e\u6216\u5916\u90e8\u4e8b\u5b9e\u3002")],
            "recommended_action": U(r"\u8bf7\u5148\u8865\u5145\u771f\u5b9e\u6570\u636e\u6216\u4e0a\u4f20\u76f8\u5173\u8d44\u6599\u3002"),
            "confidence": "insufficient_data",
            "related_objects": [],
            "need_human_decision": True,
            "next_task_suggestion": focus,
            "agent": agent_name,
        }

    def agent_collaboration(self, user):
        user = self.require_login(user)
        if not user:
            return
        data = self.agent_summary()
        role_cards = "".join(
            "<div class='card'><div><h2>{}</h2><p>{}</p><p class='small'>{}</p></div><span class='pill'>{}</span></div>".format(
                esc(r["agent_name"]), esc(r["description"]), esc(r["knowledge_scope"]), esc(r["status"])
            )
            for r in data["roles"]
        )
        task_cards = "".join(
            "<div class='card'><div><h2>{}</h2><p>{}</p><p class='small'>{} · {} · {}</p></div></div>".format(
                esc(t["title"]), esc(t["description"]), esc(t["status"]), esc(t["priority"]), esc(t["human_review_status"])
            )
            for t in data["tasks"][:8]
        ) or "<div class='panel'>{}</div>".format(self.empty_state(U(r"\u6682\u65e0\u667a\u80fd\u4f53\u4efb\u52a1\u3002")))
        discussion_items = [d["topic"] + " · " + d["human_review_status"] for d in data["discussions"]] or [U(r"\u6682\u65e0\u667a\u80fd\u4f53\u8ba8\u8bba\u3002")]
        tool_items = [t["tool_name"] + " · " + t["permission_required"] for t in data["tools"]]
        body = f"""
<div class="panel">
  <h2>{U(r'\u591a\u667a\u80fd\u4f53\u534f\u540c\u4e2d\u5fc3')}</h2>
  <p class="small">{U(r'AI CEO \u63a5\u6536\u95ee\u9898\uff0c\u518d\u5206\u914d CFO\u3001\u5e93\u5b58\u3001\u54c1\u724c\u3001\u7814\u7a76\u3001\u95e8\u5e97\u7b49\u667a\u80fd\u4f53\u5206\u6790\uff0c\u6700\u540e\u7531\u4eba\u5de5\u5ba1\u6838\u3002')}</p>
  <div class="metrics">{self.metric(U(r'\u667a\u80fd\u4f53'), len(data['roles']), U(r'\u89d2\u8272'))}{self.metric(U(r'\u4efb\u52a1'), len(data['tasks']), U(r'\u5f85\u5ba1\u6838'))}{self.metric(U(r'\u8ba8\u8bba'), len(data['discussions']), U(r'\u534f\u540c'))}{self.metric(U(r'\u5de5\u5177'), len(data['tools']), U(r'\u6ce8\u518c'))}</div>
</div>
<div class="split">
  <div class="panel form">
    <h2>{U(r'\u521b\u5efa\u667a\u80fd\u4f53\u4efb\u52a1')}</h2>
    <form method="post" action="/api/agents/tasks">
      <label>{U(r'\u4efb\u52a1\u6807\u9898')}</label><input name="title" required>
      <label>{U(r'\u8bf4\u660e')}</label><textarea name="description"></textarea>
      <label>{U(r'\u6307\u6d3e\u667a\u80fd\u4f53 ID')}</label><input name="assigned_agent_id" placeholder="1">
      <label>{U(r'\u671f\u671b\u8f93\u51fa')}</label><textarea name="expected_output" placeholder="Summary / Evidence / Risks / Recommended action"></textarea>
      <p><button>{U(r'\u521b\u5efa\u5f85\u5ba1\u6838\u4efb\u52a1')}</button></p>
    </form>
  </div>
  <div class="panel">
    <h2>{U(r'Osprey \u591a\u667a\u80fd\u4f53\u573a\u666f')}</h2>
    {self.bullets([U(r'AI CEO\uff1a\u7efc\u5408\u5224\u65ad'), U(r'AI CFO\uff1a\u5229\u6da6\u4e0e\u8fd4\u70b9\u98ce\u9669'), U(r'AI \u5e93\u5b58\u7ecf\u7406\uff1a\u5e93\u5b58\u538b\u529b'), U(r'AI \u54c1\u724c\u7ecf\u7406\uff1a\u54c1\u724c\u4ef7\u683c\u5f62\u8c61'), U(r'AI \u7814\u7a76\u5458\uff1a\u5916\u90e8\u5e02\u573a\u4ef7\u683c')])}
    <form method="post" action="/api/agents/scenarios/osprey-pricing"><button class="dark">{U(r'\u751f\u6210\u573a\u666f\u5360\u4f4d JSON')}</button></form>
  </div>
</div>
<div class="panel"><h2>{U(r'\u667a\u80fd\u4f53\u56e2\u961f')}</h2><div class="grid">{role_cards}</div></div>
<div class="panel"><h2>{U(r'\u667a\u80fd\u4f53\u4efb\u52a1')}</h2><div class="grid">{task_cards}</div></div>
<div class="split"><div class="panel"><h2>{U(r'\u667a\u80fd\u4f53\u8ba8\u8bba')}</h2>{self.bullets(discussion_items)}</div><div class="panel"><h2>{U(r'\u5de5\u5177\u6ce8\u518c\u8868')}</h2>{self.bullets(tool_items)}</div></div>
<div class="panel"><h2>{U(r'\u4eba\u5de5\u5ba1\u6279\u95f8\u95e8')}</h2>{self.bullets([U(r'\u521b\u5efa\u5206\u914d\u7ed9\u5458\u5de5\u7684\u4efb\u52a1\u9700\u8981\u5ba1\u6838'), U(r'\u5ba1\u6838\u5916\u90e8\u77e5\u8bc6\u9700\u8981\u4eba\u5de5\u786e\u8ba4'), U(r'\u4fee\u6539\u8bb0\u5fc6\u3001\u5b9a\u4ef7\u89c4\u5219\u3001\u53d1\u9001\u901a\u77e5\u3001\u53d1\u5e03\u5185\u5bb9\u90fd\u9700\u8981\u4eba\u5de5\u5ba1\u6838')])}</div>"""
        self.out(layout(U(r"\u591a\u667a\u80fd\u4f53\u534f\u540c"), body, user=user, wide=True))

    def agent_framework_payload(self, user):
        data = self.agent_summary()
        return {
            "ok": True,
            "platform": "enterprise_multi_agent_framework",
            "pack_alignment": ["Pack01 foundation", "Pack02 SAP AI", "Pack03 knowledge platform", "Pack04 AI agents"],
            "runtime": self.agent_runtime_contract_payload()["runtime"],
            "permissions": self.agent_permission_contract_payload(user)["permissions"],
            "tool_interface": self.agent_tool_interface_payload()["tool_interface"],
            "memory": self.agent_memory_contract_payload()["memory"],
            "approval": self.agent_approval_policy_payload()["approval"],
            "audit": self.agent_audit_contract_payload()["audit"],
            "catalog": [row_dict(r) for r in data["roles"]],
            "tools": [row_dict(t) for t in data["tools"]],
        }

    def agent_runtime_contract_payload(self):
        return {
            "ok": True,
            "runtime": {
                "steps": [
                    "agent_request",
                    "permission_check",
                    "retrieve_knowledge",
                    "query_sap_if_authorized",
                    "reason",
                    "generate_recommendation",
                    "request_approval_if_needed",
                    "execute_approved_workflow",
                    "log_result",
                ],
                "high_risk_actions_blocked_until_approved": True,
                "missing_data_rule": "return_limitation_do_not_invent",
                "source_rule": "knowledge_and_sap_outputs_need_citations_or_limitations",
            },
        }

    def agent_permission_contract_payload(self, user):
        return {
            "ok": True,
            "permissions": {
                "model": "role_based",
                "current_user": {"id": user["id"], "role": user["role"], "store": user["store"]},
                "roles": list(ROLES.keys()),
                "rule": "agent_tool_permission_must_be_checked_before_execution",
                "sensitive_scopes": ["pricing", "contract", "finance", "payment", "sap_write", "external_publish"],
                "sensitive_scope_policy": "requires_human_approval_and_admin_or_boss_review",
                "store_scope": "store_managers_only_see_authorized_store_data",
            },
        }

    def agent_tool_interface_payload(self):
        return {
            "ok": True,
            "tool_interface": {
                "version": "v1",
                "categories": ["sap", "knowledge", "workflow", "reporting", "notifications", "files"],
                "required_fields": ["tool_id", "tool_name", "tool_category", "tool_version", "input_schema", "output_schema", "permission_required", "risk_level", "approval_required"],
                "execution_contract": {
                    "input": {"request_id": "string", "agent_id": "string", "user_id": "integer", "payload": "object"},
                    "output": {"ok": "boolean", "result": "object", "citations": "array", "limitations": "array", "audit_id": "string"},
                },
                "versioning": "all_tools_expose_versioned_interfaces",
            },
        }

    def agent_memory_contract_payload(self):
        return {
            "ok": True,
            "memory": {
                "short_term": "conversation_context",
                "long_term": "enterprise_memory",
                "knowledge_retrieval": "knowledge_center",
                "audit_trail": "activity_log",
                "write_policy": "important_memory_requires_human_review",
            },
        }

    def agent_approval_policy_payload(self):
        return {
            "ok": True,
            "approval": {
                "required_for": ["price_change", "discount_policy", "contract_decision", "finance_payment", "sap_write", "external_publish", "mass_notification"],
                "default_status": "pending",
                "review_roles": ["boss", "admin", "finance"],
                "actions": ["approve", "reject", "request_more_analysis", "edit_before_approval"],
                "execution_rule": "no_high_risk_tool_execution_before_approval",
            },
        }

    def agent_audit_contract_payload(self):
        return {
            "ok": True,
            "audit": {
                "log_table": "activity_log",
                "events": ["agent_request", "permission_check", "tool_planned", "approval_requested", "approval_decided", "tool_executed", "agent_result"],
                "required_fields": ["user_id", "agent_id", "tool_id", "action", "object_type", "object_id", "timestamp", "result"],
                "retention": "standard_enterprise_audit_policy",
            },
        }

    def api_agents_get(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if path == "/api/agents/framework":
            return self.json_out(self.agent_framework_payload(user))
        if path == "/api/agents/runtime-contract":
            return self.json_out(self.agent_runtime_contract_payload())
        if path == "/api/agents/permissions":
            return self.json_out(self.agent_permission_contract_payload(user))
        if path == "/api/agents/tool-interface":
            return self.json_out(self.agent_tool_interface_payload())
        if path == "/api/agents/memory-contract":
            return self.json_out(self.agent_memory_contract_payload())
        if path == "/api/agents/approval-policy":
            return self.json_out(self.agent_approval_policy_payload())
        if path == "/api/agents/audit-contract":
            return self.json_out(self.agent_audit_contract_payload())
        if path.startswith(("/api/agents/workflows", "/api/agents/workflow-templates", "/api/agents/marketplace", "/api/agents/templates", "/api/agents/builder", "/api/agents/sandbox", "/api/agents/runtime", "/api/agents/approvals")):
            return self.api_v5_get(user, path)
        data = self.agent_summary()
        if path == "/api/agents/registry":
            return self.json_out({
                "ok": True,
                "registry": {
                    "tool_interface": "shared",
                    "permission_model": "role_based",
                    "memory_abstraction": "memory_engine",
                    "knowledge_access": "knowledge_center",
                    "audit_logging": "activity_log",
                    "runtime": "request_permission_retrieve_reason_approve_execute_log",
                    "approval_policy": "high_risk_actions_require_human_review",
                },
                "initial_agents": ["CEO Agent", "Finance Agent", "Store Agent", "Inventory Agent", "Product Agent", "Customer Agent", "Supplier Agent", "HR Agent", "Training Agent", "Content Agent", "Meeting Agent", "Analytics Agent"],
                "roles": [row_dict(r) for r in data["roles"]],
                "tools": [row_dict(r) for r in data["tools"]],
            })
        if path == "/api/agents/collaboration":
            return self.json_out({"ok": True, "summary": {"roles": len(data["roles"]), "tasks": len(data["tasks"]), "discussions": len(data["discussions"]), "tools": len(data["tools"])}})
        if path == "/api/agents/roles":
            return self.json_out({"ok": True, "roles": [row_dict(r) for r in data["roles"]]})
        if path == "/api/agents/tasks":
            return self.json_out({"ok": True, "tasks": [row_dict(r) for r in data["tasks"]]})
        if path == "/api/agents/discussions":
            return self.json_out({"ok": True, "discussions": [row_dict(r) for r in data["discussions"]]})
        if path == "/api/agents/tools":
            return self.json_out({"ok": True, "tools": [row_dict(r) for r in data["tools"]]})
        return self.json_out({"ok": False, "message": "unknown agents api"}, code=404)

    def api_agents_post(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if path.startswith(("/api/agents/workflows", "/api/agents/workflow-templates", "/api/agents/marketplace", "/api/agents/templates", "/api/agents/builder", "/api/agents/sandbox", "/api/agents/runtime", "/api/agents/approvals")):
            return self.api_v5_post(user, path)
        form = self.form()
        now = ts()
        if path == "/api/agents/roles":
            if not self.can_manage_agents(user):
                return self.json_out({"ok": False, "message": "no permission"}, code=403)
            with db() as conn:
                cur = conn.execute("insert into agent_roles(agent_id,agent_name,agent_role,description,responsibilities,tools,knowledge_scope,memory_scope,permission_scope,status,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?)", ("AG-" + uuid.uuid4().hex[:10], form.get("agent_name", "AI Agent"), form.get("agent_role", ""), form.get("description", ""), form.get("responsibilities", ""), form.get("tools", ""), form.get("knowledge_scope", ""), form.get("memory_scope", ""), form.get("permission_scope", "role_based"), form.get("status", "active"), now, now))
            self.log_action(user, "agent_role_created", "agent", cur.lastrowid, form.get("agent_name", ""))
            return self.json_out({"ok": True, "agent_id": cur.lastrowid})
        if path == "/api/agents/tasks":
            with db() as conn:
                cur = conn.execute("insert into agent_tasks(agent_task_id,title,description,assigned_agent_id,requested_by,related_object_type,related_object_id,input_context,expected_output,status,priority,due_at,result_summary,human_review_status,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("AT-" + uuid.uuid4().hex[:10], form.get("title", U(r"\u672a\u547d\u540d\u667a\u80fd\u4f53\u4efb\u52a1")), form.get("description", ""), int(form.get("assigned_agent_id")) if str(form.get("assigned_agent_id", "")).isdigit() else None, user["id"], form.get("related_object_type", ""), int(form.get("related_object_id")) if str(form.get("related_object_id", "")).isdigit() else None, form.get("input_context", ""), form.get("expected_output", ""), "queued", form.get("priority", "normal"), form.get("due_at", ""), U(r"\u7f3a\u5c11\u6570\u636e\uff0c\u65e0\u6cd5\u5f97\u51fa\u7ed3\u8bba\u3002"), "pending", now, now))
            self.log_action(user, "agent_task_created", "agent_task", cur.lastrowid, form.get("title", ""))
            return self.json_out({"ok": True, "agent_task_id": cur.lastrowid})
        m = re.match(r"^/api/agents/tasks/(\d+)/(approve|reject)$", path)
        if m:
            if not self.can_manage_agents(user):
                return self.json_out({"ok": False, "message": "no permission"}, code=403)
            status = "approved" if m.group(2) == "approve" else "rejected"
            with db() as conn:
                conn.execute("update agent_tasks set human_review_status=?, updated_at=? where id=?", (status, now, m.group(1)))
            self.log_action(user, "agent_task_" + m.group(2), "agent_task", m.group(1), "")
            return self.json_out({"ok": True})
        if path == "/api/agents/discussions":
            with db() as conn:
                cur = conn.execute("insert into agent_discussions(discussion_id,topic,initiator_agent_id,participating_agents,context_objects,messages,conclusion,recommended_actions,human_review_status,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?)", ("DISC-" + uuid.uuid4().hex[:10], form.get("topic", U(r"\u672a\u547d\u540d\u8ba8\u8bba")), int(form.get("initiator_agent_id")) if str(form.get("initiator_agent_id", "")).isdigit() else None, form.get("participating_agents", ""), form.get("context_objects", ""), "[]", U(r"\u7f3a\u5c11\u6570\u636e\uff0c\u65e0\u6cd5\u5f97\u51fa\u7ed3\u8bba\u3002"), form.get("recommended_actions", ""), "pending", user["id"], now, now))
            self.log_action(user, "agent_discussion_created", "agent_discussion", cur.lastrowid, form.get("topic", ""))
            return self.json_out({"ok": True, "discussion_id": cur.lastrowid})
        if path == "/api/agents/tools":
            if not self.can_manage_agents(user):
                return self.json_out({"ok": False, "message": "no permission"}, code=403)
            with db() as conn:
                cur = conn.execute("insert into agent_tools(tool_id,tool_name,description,input_schema,output_schema,permission_required,status,created_at,updated_at) values(?,?,?,?,?,?,?,?,?)", ("TOOL-" + uuid.uuid4().hex[:10], form.get("tool_name", "Tool"), form.get("description", ""), form.get("input_schema", ""), form.get("output_schema", ""), form.get("permission_required", ""), form.get("status", "active"), now, now))
            self.log_action(user, "agent_tool_registered", "agent_tool", cur.lastrowid, form.get("tool_name", ""))
            return self.json_out({"ok": True, "tool_id": cur.lastrowid})
        if path == "/api/agents/scenarios/osprey-pricing":
            scenario = {
                "topic": U(r"Osprey \u662f\u5426\u7ee7\u7eed 59 \u6298\u9500\u552e\uff1f"),
                "agents": {
                    "AI CEO": self.safe_agent_output("AI CEO", U(r"\u9700\u8981\u7efc\u5408\u5224\u65ad")),
                    "AI CFO": self.safe_agent_output("AI CFO", U(r"\u9700\u8981\u771f\u5b9e\u5229\u6da6\u548c\u8fd4\u70b9\u6570\u636e")),
                    "AI Inventory Manager": self.safe_agent_output("AI Inventory Manager", U(r"\u9700\u8981\u5e93\u5b58\u91d1\u989d\u548c\u5e93\u9f84\u6570\u636e")),
                    "AI Brand Manager": self.safe_agent_output("AI Brand Manager", U(r"\u9700\u8981\u54c1\u724c\u4ef7\u683c\u5f62\u8c61\u5224\u65ad")),
                    "AI Research Agent": self.safe_agent_output("AI Research Agent", U(r"\u9700\u8981\u5df2\u5ba1\u6838\u5916\u90e8\u5e02\u573a\u8d44\u6599")),
                    "AI Store Manager": self.safe_agent_output("AI Store Manager", U(r"\u9700\u8981\u95e8\u5e97\u6267\u884c\u53cd\u9988")),
                },
                "human_review_status": "pending",
                "note": U(r"\u8fd9\u662f\u591a\u667a\u80fd\u4f53\u534f\u540c\u6a21\u677f\uff0c\u4e0d\u4ee3\u8868\u771f\u5b9e\u7ecf\u8425\u7ed3\u8bba\u3002"),
            }
            self.log_action(user, "agent_recommendation_generated", "agent_scenario", None, "osprey-pricing")
            return self.json_out({"ok": True, "scenario": scenario})
        return self.json_out({"ok": False, "message": "unknown agents api"}, code=404)

    def v5_page_routes(self):
        return set(self.v5_catalog().keys())

    def v5_catalog(self):
        return {
            "/operating-loop": ("Company Operating Loop", "Daily cycle from SAP sync, briefing, risks, decisions, tasks and evening review.", ["Morning briefing", "Risk to task", "Decision to memory", "Evening review", "Loop history"], "/api/operating-loop", "Task023"),
            "/operating-loop/evening-review": ("Evening Review", "Daily review skeleton with completed tasks, unresolved risks and tomorrow focus.", ["Completed tasks", "Unresolved risks", "Field feedback", "Tomorrow focus"], "/api/operating-loop/evening-review", "Task023"),
            "/strategy": ("Strategy + OKR Engine", "Annual goals, quarterly OKRs, monthly targets and strategic initiatives.", ["Annual goals", "Quarterly OKR", "Monthly targets", "Store goals", "Brand goals", "Key initiatives"], "/api/strategy", "Task024"),
            "/agents/workflows": ("Agent Workflow Engine", "Structured multi-agent workflows with human review gates.", ["Workflow templates", "Running workflows", "Pending review", "Step results", "Workflow history"], "/api/agents/workflows", "Task026"),
            "/agents/marketplace": ("Agent Marketplace", "Internal digital employees and reusable agent templates.", ["Recommended agents", "Custom agents", "Template library", "Approval flow"], "/api/agents/marketplace", "Task027"),
            "/agents/builder": ("Custom Agent Builder", "Create agents with scope, tools, memory, permissions and approval policy.", ["Name and role", "Responsibilities", "Knowledge scope", "Tools", "Permissions", "Test prompt"], "/api/agents/builder/options", "Task027"),
            "/agents/sandbox": ("Agent Testing Sandbox", "Test an agent safely before activation.", ["Selected agent", "Planned tools", "Context scope", "Safety warning", "Placeholder answer"], "/api/agents/sandbox", "Task027"),
            "/digital-twin": ("Enterprise Digital Twin", "Decision simulation layer for stores, brands, inventory, finance and agents.", ["Company snapshot", "Scenario simulation", "Decision comparison", "Agent opinions"], "/api/digital-twin", "Task028"),
            "/decision-center": ("Decision Center", "Daily operating score, risk warning, purchase advice, clearance advice and action list.", ["Today operation", "Risk warning", "Purchase advice", "Clearance advice", "Action list", "History reports"], "/api/decisions", "V5"),
            "/ai-memory": ("AI Memory Center", "Long-term company memory for strategy, decisions, projects and boss intent.", ["Long-term memory", "Pending memory", "Approved memory", "Related objects", "Memory logs"], "/api/memory", "V5"),
            "/web-research-center": ("Web Research Center", "Public web research intake with source URL, summary and human review.", ["Search task", "Source URL", "Summary", "Review queue", "Save to knowledge"], "/api/knowledge", "V5"),
            "/system/kernel": ("FoxBrain Core Kernel", "Central kernel for modules, objects, events, permissions, tools and health.", ["Module registry", "Object registry", "Event bus", "AI context", "Tool registry", "Health"], "/api/kernel", "Task030"),
            "/system/permissions": ("Permission Matrix", "Role, module, action and sensitive data permission adapter.", ["Roles", "Modules", "Actions", "Sensitive scopes", "AI scopes"], "/api/kernel/permissions", "Task030"),
            "/data-fabric": ("AI Data Fabric", "Unified data catalog, freshness, lineage, quality and AI readiness.", ["Data sources", "Catalog", "Lineage", "Quality", "AI-ready data", "Sensitive data"], "/api/data-fabric", "Task031"),
            "/system/apps": ("App Platform", "Built-in app registry and future plugin architecture.", ["Installed apps", "Available apps", "Permissions", "Settings", "Health", "Events"], "/api/apps", "Task032"),
            "/system/apps/developer": ("App Developer Guide", "Manifest, permission, event bus and data fabric rules for future apps.", ["Manifest", "Routes", "Permissions", "Events", "Settings", "Security"], "/api/apps/developer/template", "Task032"),
            "/integrations": ("Integration Hub", "Safe connector registry for SAP, AI providers, search, messaging and webhooks.", ["Connectors", "Credential status", "Sync jobs", "Webhooks", "AI providers", "Search providers"], "/api/integrations", "Task033"),
            "/security": ("Security Governance", "Sensitive data, AI governance, agent safety and access review.", ["Permission matrix", "Sensitive data map", "AI governance", "Agent safety", "Audit logs", "Alerts"], "/api/security", "Task034"),
            "/operations": ("Operations Reliability", "Backup, restore, logs, uptime, maintenance and release operations.", ["Backup status", "Restore plan", "Logs", "Errors", "Uptime", "Maintenance"], "/api/operations", "Task035"),
            "/operations/release": ("Release Checklist", "Safe release checklist for cloud deployment.", ["Pull code", "Run tests", "Restart service", "Check health", "Check login"], "/api/operations/release-checklist", "Task035"),
            "/operations/rollback": ("Rollback Checklist", "Recovery checklist when a release fails.", ["Identify version", "Restore backup", "Restart", "Verify health", "Record incident"], "/api/operations/rollback-checklist", "Task035"),
            "/product": ("Productization Center", "Versioning, onboarding, help, feature flags and production readiness.", ["Version info", "Release notes", "Feature flags", "Onboarding", "Help center", "Feedback"], "/api/product", "Task036"),
            "/product/releases": ("Release Notes", "Task history and known issues.", ["Cloud edition", "Task023-038", "Known issues", "Upgrade notes"], "/api/product/releases", "Task036"),
            "/onboarding": ("User Onboarding", "Role-based first steps for boss, manager, employee and admin.", ["Boss", "Manager", "Employee", "Admin"], "/api/onboarding", "Task036"),
            "/onboarding/boss": ("Boss Onboarding", "Daily action review, decisions, AI CEO and operating loop.", ["Open action board", "Review decisions", "Ask Jarvis", "Approve actions"], "/api/onboarding", "Task036"),
            "/onboarding/manager": ("Manager Onboarding", "Store tasks, customer follow-up and field feedback.", ["View store actions", "Complete tasks", "Upload evidence", "Evening review"], "/api/onboarding", "Task036"),
            "/onboarding/employee": ("Employee Onboarding", "Mobile-first daily tasks and feedback submission.", ["My tasks", "Upload photo", "Customer feedback", "Ask AI"], "/api/onboarding", "Task036"),
            "/onboarding/admin": ("Admin Onboarding", "Configure cloud, users, SAP sync, backups and health.", ["Users", ".env", "SAP sync", "Backup", "Health"], "/api/onboarding", "Task036"),
            "/help": ("Help Center", "Getting started, SAP sync, Jarvis, tasks, knowledge and troubleshooting.", ["Getting started", "AI CEO", "Jarvis", "SAP", "Tasks", "Troubleshooting"], "/api/help", "Task036"),
            "/product/admin-checklist": ("Admin Checklist", "Production launch checklist.", ["Configure .env", "Check login", "Check permissions", "Check backup", "Check SAP"], "/api/product/admin-checklist", "Task036"),
            "/product/readiness": ("Production Readiness", "Production readiness dashboard.", ["Login", "Permissions", "SAP sync", "Backup", "Security", "AI provider"], "/api/product/readiness", "Task036"),
            "/feedback": ("Feedback Center", "Collect product feedback and improvement requests.", ["New feedback", "Reviewing", "Planned", "Fixed"], "/api/feedback", "Task036"),
            "/agents/runtime": ("Actionable Agent Runtime", "Agent runs, action plans, approvals, tool executions and safety blocks.", ["Agent runs", "Action plans", "Approvals", "Tool executions", "Safety blocks"], "/api/agents/runtime", "Task037"),
            "/agents/approvals": ("Agent Approval Console", "Approve, reject, edit or request more analysis for agent actions.", ["Pending plans", "Pending steps", "Rejected", "Approved"], "/api/agents/approvals", "Task037"),
            "/action/boss": ("Boss Action Console", "Top risks, pending decisions, overdue tasks and agent approvals.", ["Top risks", "Boss decisions", "Overdue tasks", "Store exceptions", "Suggested actions"], "/api/action/boss", "Task038"),
            "/action/store-manager": ("Store Manager Action Console", "Store tasks, customer follow-ups, inventory issues and AI store suggestions.", ["Store tasks", "Customer follow-up", "Inventory issues", "Content tasks"], "/api/action/store-manager", "Task038"),
            "/action/employee": ("Employee Action Console", "Mobile-first personal tasks, uploads, feedback and notifications.", ["My tasks", "Upload photo", "Customer feedback", "Training"], "/api/action/employee", "Task038"),
            "/action/brand": ("Brand Action Console", "Brand risks, content opportunities, research alerts and decisions.", ["Osprey risk", "KAILAS growth", "VAFOX content", "Research alerts"], "/api/action/brand", "Task038"),
            "/action/inventory": ("Inventory Action Console", "Inventory warnings, transfer tasks and markdown review.", ["High stock", "Slow movers", "Transfer review", "Markdown review"], "/api/action/inventory", "Task038"),
            "/action/finance": ("Finance Action Console", "Profit, rebate, cashflow and break-even warnings.", ["Profit warnings", "Rebate risks", "Cashflow", "Break-even"], "/api/action/finance", "Task038"),
            "/action/agents": ("AI Agent Action Console", "Agent plans, approvals, failed runs and safety blocks.", ["Running agents", "Pending approvals", "Safety blocks", "Next actions"], "/api/action/agents", "Task038"),
            "/action/today": ("Daily Action Board", "What to decide, execute and review today.", ["Must decide", "Must execute", "Must review", "Completed today"], "/api/action/today", "Task038"),
            "/action/rhythm": ("FireFox Operating Rhythm", "Daily, weekly and monthly operating cadence.", ["Daily", "Weekly", "Monthly"], "/api/action/rhythm", "Task038"),
        }

    def v5_page(self, user, path):
        user = self.require_login(user)
        if not user:
            return
        title, subtitle, sections, api_path, task_no = self.v5_catalog()[path]
        data = self.v5_payload(path, user)
        cards = "".join(self.card(s, "Prepared workflow section. Real conclusions wait for source data and human review.", api_path, "btn", True) for s in sections)
        status_items = [
            task_no + " framework active",
            "No fake business data: missing data is shown as limitation.",
            "Human approval required for sensitive decisions and actions.",
            "SAP nightly sync remains scheduled at 22:00.",
        ]
        body = f"""
<div class="panel">
  <h2>{esc(title)}</h2>
  <p class="small">{esc(subtitle)}</p>
  <div class="metrics">
    {self.metric("Status", data["status"], task_no)}
    {self.metric("Open items", len(data["items"]), "draft / pending")}
    {self.metric("SAP", data["sap"]["freshness"], data["sap"]["next_run_time"])}
    {self.metric("Health", data["health"]["status"], data["health"]["app_version"])}
  </div>
</div>
<div class="grid">{cards}</div>
<div class="split">
  <div class="panel"><h2>Current Limits</h2>{self.bullets(data["limitations"])}</div>
  <div class="panel"><h2>Safety Rules</h2>{self.bullets(status_items)}</div>
</div>
<div class="panel form">
  <h2>Create Draft Item</h2>
  <form method="post" action="{esc(api_path)}">
    <label>Title</label><input name="title" required>
    <label>Description</label><textarea name="description"></textarea>
    <label>Priority</label><select name="priority"><option value="normal">normal</option><option value="high">high</option><option value="urgent">urgent</option></select>
    <p><button>Save Draft</button></p>
  </form>
</div>"""
        self.out(layout(title, body, user=user, wide=True))

    def v5_item_type(self, path):
        clean = path.replace("/api/", "").strip("/")
        return clean.split("/")[0].replace("-", "_") or "v5"

    def v5_payload(self, path, user):
        item_type = self.v5_item_type(path)
        if path.startswith("/api/agents/") or path.startswith("/agents/"):
            item_type = "agents"
        with db() as conn:
            rows = conn.execute("select * from v5_items where item_type=? order by updated_at desc limit 30", (item_type,)).fetchall()
        sections = self.v5_catalog().get(path.replace("/api", "", 1), ("", "", [], "", ""))[2] if path.startswith("/api") else self.v5_catalog().get(path, ("", "", [], "", ""))[2]
        return {
            "ok": True,
            "module": item_type,
            "status": "framework_ready",
            "sections": sections,
            "items": [row_dict(r) for r in rows],
            "sap": self.sap_sync_status_payload(),
            "health": self.health_payload(),
            "data_policy": "Use real data only. If data is missing, return limitations instead of conclusions.",
            "approval_policy": "Sensitive actions require human approval. Agents can draft, plan and request approval.",
            "limitations": [
                "Real SAP business facts depend on the 22:00 sync result.",
                "AI provider calls are not forced here; this layer is safe without API keys.",
                "External publishing, price changes, purchasing, finance and HR actions are approval-only.",
            ],
        }

    def api_v5_get(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if path.startswith("/api/data-sources"):
            return self.json_out({"ok": True, "sources": self.v5_data_sources()})
        if path.startswith("/api/data-catalog"):
            return self.json_out({"ok": True, "datasets": self.v5_data_catalog()})
        if path.startswith("/api/data-quality"):
            return self.json_out({"ok": True, "quality": self.v5_data_quality()})
        if path.startswith("/api/integrations"):
            return self.json_out(self.v5_integrations_payload())
        if path.startswith("/api/security"):
            return self.json_out(self.v5_security_payload())
        if path.startswith("/api/operations"):
            return self.json_out(self.v5_operations_payload())
        if path.startswith("/api/product") or path.startswith("/api/help") or path.startswith("/api/onboarding") or path.startswith("/api/feedback"):
            return self.json_out(self.v5_product_payload(path))
        if path.startswith("/api/action"):
            return self.json_out(self.v5_action_payload(path, user))
        if path.startswith("/api/agents"):
            return self.json_out(self.v5_agent_payload(path, user))
        return self.json_out(self.v5_payload(path, user))

    def api_v5_post(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        form = self.form()
        title = form.get("title") or form.get("objective") or form.get("question") or form.get("request_text") or "Untitled draft"
        now = ts()
        item_type = self.v5_item_type(path)
        if path.startswith("/api/agents/"):
            item_type = "agents"
        if any(path.endswith(suffix) for suffix in ("/approve", "/reject", "/complete", "/cancel")):
            action = path.rsplit("/", 1)[-1]
            self.log_action(user, "v5_" + action, item_type, None, path)
            return self.json_out({"ok": True, "action": action, "message": "Action recorded. V1 does not perform unsafe business changes automatically."})
        with db() as conn:
            cur = conn.execute(
                "insert into v5_items(item_id,item_type,title,description,status,priority,owner,related_object_type,related_object_id,payload_json,approval_status,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("V5-" + uuid.uuid4().hex[:10], item_type, title, form.get("description", ""), form.get("status", "draft"), form.get("priority", "normal"), form.get("owner", ""), form.get("related_object_type", ""), form.get("related_object_id", ""), json.dumps(form, ensure_ascii=False), form.get("approval_status", "pending" if "approval" in path or "runtime" in path else "not_required"), user["id"], now, now),
            )
        self.log_action(user, "v5_item_created", item_type, cur.lastrowid, title[:120])
        return self.json_out({"ok": True, "id": cur.lastrowid, "item_type": item_type, "message": "Draft saved. Human review is still required for sensitive actions."})

    def v5_data_sources(self):
        sap = self.sap_sync_status_payload()
        return [
            {"source_key": "sap_b1", "name": "SAP B1", "type": "erp", "sync_frequency": "daily 22:00", "freshness": sap["freshness"], "configured": True},
            {"source_key": "knowledge", "name": "Knowledge Center", "type": "knowledge", "freshness": "ready", "configured": True},
            {"source_key": "uploads", "name": "Uploaded files", "type": "document", "freshness": "ready", "configured": True},
            {"source_key": "ai_provider", "name": "AI Provider", "type": "ai_provider", "freshness": "env_checked", "configured": bool(os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY"))},
        ]

    def v5_data_catalog(self):
        return [
            {"dataset_key": "stores", "name": "Store master data", "sensitivity": "internal", "ai_ready": "partial"},
            {"dataset_key": "products", "name": "Product archive data", "sensitivity": "internal", "ai_ready": "partial"},
            {"dataset_key": "sap_sales", "name": "SAP sales data", "sensitivity": "manager_only", "ai_ready": "depends_on_sync"},
            {"dataset_key": "sap_inventory", "name": "SAP inventory data", "sensitivity": "manager_only", "ai_ready": "depends_on_sync"},
            {"dataset_key": "finance", "name": "Finance data", "sensitivity": "finance_sensitive", "ai_ready": "permission_required"},
            {"dataset_key": "customer", "name": "Customer data", "sensitivity": "customer_sensitive", "ai_ready": "restricted"},
        ]

    def v5_data_quality(self):
        sap = self.sap_sync_status_payload()
        return [{"check": "sap_freshness", "status": sap["freshness"]}, {"check": "secret_exposure", "status": "no_secrets_returned"}, {"check": "ai_citation", "status": "source_required"}]

    def v5_integrations_payload(self):
        providers = ["OpenAI", "DeepSeek", "Claude", "Gemini", "Qwen"]
        connectors = ["SAP B1", "Enterprise WeChat", "WeChat Official Account", "Douyin", "Xiaohongshu", "Email SMTP", "Cloud Storage", "Bing Search", "Tavily"]
        return {"ok": True, "connectors": [{"name": c, "configured": c == "SAP B1", "secrets_visible": False} for c in connectors], "ai_providers": [{"name": p, "configured": bool(os.environ.get(p.upper() + "_API_KEY")), "secrets_visible": False} for p in providers], "sap": self.sap_sync_status_payload()}

    def v5_security_payload(self):
        return {"ok": True, "sensitive_data": self.v5_data_catalog(), "ai_governance": ["AI cannot change prices automatically", "AI cannot approve purchasing or finance actions", "AI cannot expose secrets", "External publishing requires approval"], "alerts": [{"level": "info", "title": "Security framework active"}]}

    def v5_operations_payload(self):
        return {"ok": True, "backup": {"script": "backup.sh", "status": "available"}, "restore": {"script": "restore.sh", "status": "available"}, "healthcheck": {"script": "healthcheck.sh", "status": "available"}, "cloud": {"restart_policy": "always", "pc_can_be_off": True}, "sap": self.sap_sync_status_payload()}

    def v5_product_payload(self, path):
        return {"ok": True, "version": self.health_payload()["app_version"], "completed_tasks": [f"Task{n:03d}" for n in range(23, 39)], "feature_flags": ["enable_jarvis", "enable_agent_workflows", "enable_digital_twin", "enable_sap_nightly_sync", "enable_mobile_field_operation"], "help_sections": ["Getting started", "AI CEO", "Jarvis", "SAP sync", "Tasks", "Knowledge", "Troubleshooting"], "path": path}

    def v5_agent_payload(self, path, user):
        data = self.agent_summary()
        return {"ok": True, "path": path, "roles": [row_dict(r) for r in data["roles"]], "tools": [row_dict(r) for r in data["tools"]], "runtime": {"safety_levels": ["read_only", "draft_only", "internal_state_change", "sensitive_business_action", "blocked"], "default_approval_required": True}, "templates": ["Pricing Decision", "Inventory Risk", "Purchasing Decision", "Store Growth", "Brand Strategy", "Finance Risk", "Osprey Decision"]}

    def v5_action_payload(self, path, user):
        queue = self.os_work_queue_payload(user)["items"]
        return {"ok": True, "path": path, "today": {"must_decide": [], "must_execute": queue[:10], "must_review": []}, "conversion_flows": ["suggestion_to_task", "risk_to_decision", "decision_to_execution", "submission_to_knowledge", "agent_plan_to_actions"], "approval_required": True}

    def can_use_mobile(self, user):
        return bool(user)

    def can_review_mobile(self, user):
        return bool(user and user["role"] in ("boss", "admin", "store_manager"))

    def mobile_submission_types(self):
        return [
            ("store_note", U(r"\u95e8\u5e97\u8bb0\u5f55")),
            ("product_photo", U(r"\u4ea7\u54c1\u7167\u7247")),
            ("customer_feedback", U(r"\u987e\u5ba2\u53cd\u9988")),
            ("inventory_issue", U(r"\u5e93\u5b58\u95ee\u9898")),
            ("competitor_price", U(r"\u7ade\u54c1\u89c2\u5bdf")),
            ("event_record", U(r"\u6d3b\u52a8\u8bb0\u5f55")),
            ("training_note", U(r"\u57f9\u8bad\u7b14\u8bb0")),
            ("repair_issue", U(r"\u7ef4\u4fee\u95ee\u9898")),
            ("knowledge_feed", U(r"\u5582\u77e5\u8bc6\u5e93")),
        ]

    def save_mobile_files(self, form):
        saved = []
        folder = Path(UPLOAD_DIR) / "mobile"
        folder.mkdir(parents=True, exist_ok=True)
        fields = form["photos"] if "photos" in form else []
        if not isinstance(fields, list):
            fields = [fields]
        for item in fields:
            if not getattr(item, "filename", ""):
                continue
            original = Path(item.filename).name
            safe_name = uuid.uuid4().hex + "_" + re.sub(r"[^A-Za-z0-9._-]", "_", original)
            path = folder / safe_name
            data = item.file.read()
            path.write_bytes(data)
            saved.append({"original_name": original, "saved_name": safe_name, "path": str(path), "size": len(data)})
        return saved

    def mobile_center(self, user, msg=""):
        user = self.require_login(user)
        if not user:
            return
        with db() as conn:
            my = conn.execute("select * from field_submissions where created_by=? order by created_at desc limit 8", (user["id"],)).fetchall()
            notices = conn.execute("select * from notifications where recipient_user_id is null or recipient_user_id=? order by created_at desc limit 6", (user["id"],)).fetchall()
            tasks = conn.execute("select * from tasks where status!='done' and (owner=? or owner='' or owner is null) order by updated_at desc limit 6", (user["name"],)).fetchall()
        type_options = "".join("<option value='{}'>{}</option>".format(k, esc(v)) for k, v in self.mobile_submission_types())
        quick_cards = "".join([
            self.card(U(r"\u4eca\u65e5\u4efb\u52a1"), U(r"\u67e5\u770b\u81ea\u5df1\u7684\u4efb\u52a1\uff0c\u5b8c\u6210\u540e\u4e0a\u4f20\u7ed3\u679c\u8bf4\u660e\u3002"), "/mobile/tasks", "btn", True),
            self.card(U(r"\u62cd\u7167\u4e0a\u4f20"), U(r"\u95e8\u5e97\u3001\u4ea7\u54c1\u3001\u6d3b\u52a8\u3001\u5e93\u5b58\u95ee\u9898\u90fd\u53ef\u4ee5\u76f4\u63a5\u624b\u673a\u63d0\u4ea4\u3002"), "#mobile-form", "btn green", True),
            self.card(U(r"AI \u95ee\u7b54"), U(r"\u624b\u673a\u76f4\u63a5\u95ee Jarvis\uff0c\u67e5\u77e5\u8bc6\u3001\u4efb\u52a1\u548c\u95e8\u5e97\u6267\u884c\u3002"), "/jarvis", "btn", True),
            self.card(U(r"\u6211\u7684\u63d0\u4ea4"), U(r"\u67e5\u770b\u81ea\u5df1\u63d0\u4ea4\u7684\u95e8\u5e97\u8bb0\u5f55\u3001\u987e\u5ba2\u53cd\u9988\u548c\u5e93\u5b58\u95ee\u9898\u3002"), "#my-submissions", "btn orange", True),
        ])
        task_items = [t["title"] + " · " + t["status"] for t in tasks] or [U(r"\u6682\u65e0\u672a\u5b8c\u6210\u4efb\u52a1\u3002")]
        notice_items = [n["title"] + " · " + n["status"] for n in notices] or [U(r"\u6682\u65e0\u901a\u77e5\u3002")]
        sub_cards = "".join("<div class='card'><div><h2>{}</h2><p>{}</p><p class='small'>{} · {}</p></div></div>".format(esc(s["title"]), esc(summarize_text(s["content"], 120)), esc(s["submission_type"]), esc(s["status"])) for s in my) or "<div class='panel'>{}</div>".format(self.empty_state(U(r"\u6682\u65e0\u63d0\u4ea4\u3002")))
        body = f"""
<div class="panel"><h2>{U(r'\u624b\u673a\u4e00\u7ebf\u8fd0\u8425\u4e2d\u5fc3')}</h2><p class="small">{U(r'\u7ed9\u95e8\u5e97\u5458\u5de5\u7528\uff1a\u62cd\u7167\u3001\u8bb0\u5f55\u3001\u53cd\u9988\u3001\u63d0\u4ea4\u95ee\u9898\u3001\u5b8c\u6210\u4efb\u52a1\u3002')}</p></div>
<div class="grid">{quick_cards}</div>
<div class="split">
  <div class="panel"><h2>{U(r'\u4eca\u65e5\u4efb\u52a1')}</h2>{self.bullets(task_items)}<p><a class="btn" href="/mobile/tasks">{U(r'\u6253\u5f00\u4efb\u52a1')}</a></p></div>
  <div class="panel"><h2>{U(r'\u6211\u7684\u901a\u77e5')}</h2>{self.bullets(notice_items)}</div>
</div>
<div id="mobile-form" class="panel form">
  <h2>{U(r'\u4e00\u7ebf\u63d0\u4ea4')}</h2>
  <form method="post" action="/mobile/submissions/save" enctype="multipart/form-data">
    <label>{U(r'\u7c7b\u578b')}</label><select name="submission_type">{type_options}</select>
    <label>{U(r'\u6807\u9898')}</label><input name="title" required>
    <label>{U(r'\u95e8\u5e97')}</label><input name="store_id" value="{esc(user['store'])}" placeholder="{U(r'\u5357\u5c71\u5e97 / \u632f\u5174\u5e97 / \u822a\u82d1\u5e97')}">
    <label>{U(r'\u5185\u5bb9')}</label><textarea name="content" placeholder="{U(r'\u4eca\u5929\u60c5\u51b5\u3001\u987e\u5ba2\u53cd\u9988\u3001\u5e93\u5b58\u95ee\u9898\u3001\u7ade\u54c1\u89c2\u5bdf\u7b49')}"></textarea>
    <label>{U(r'\u6807\u7b7e')}</label><input name="tags" placeholder="KAILAS,Osprey,inventory">
    <label>{U(r'\u7167\u7247')}</label><input name="photos" type="file" accept="image/*" multiple>
    <p><button>{U(r'\u63d0\u4ea4')}</button></p>
  </form>
</div>
<div id="my-submissions" class="panel"><h2>{U(r'\u6211\u7684\u63d0\u4ea4')}</h2><div class="grid">{sub_cards}</div></div>
<div class="panel"><h2>{U(r'\u4f01\u4e1a\u5fae\u4fe1')}</h2>{self.empty_state(U(r'\u4f01\u4e1a\u5fae\u4fe1\u767b\u5f55\u3001\u4efb\u52a1\u901a\u77e5\u548c\u6d88\u606f\u63a5\u6536\u5df2\u9884\u7559\uff0c\u4e0d\u5728\u4ee3\u7801\u4e2d\u5199\u5165\u5bc6\u94a5\u3002'))}</div>"""
        self.out(layout(U(r"\u624b\u673a\u4e00\u7ebf\u8fd0\u8425"), body, user=user, msg=msg, wide=True))

    def mobile_submission_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        form = self.multipart()
        submission_type = form.getfirst("submission_type", "store_note")
        title = form.getfirst("title", "").strip()
        if not title:
            return self.mobile_center(user, U(r"\u8bf7\u586b\u5199\u6807\u9898\u3002"))
        photos = self.save_mobile_files(form)
        now = ts()
        with db() as conn:
            cur = conn.execute(
                "insert into field_submissions(submission_id,submission_type,title,content,store_id,employee_id,related_object_type,related_object_id,photos,attachments,tags,status,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("FS-" + uuid.uuid4().hex[:10], submission_type, title, form.getfirst("content", ""), form.getfirst("store_id", user["store"]), user["id"], form.getfirst("related_object_type", ""), int(form.getfirst("related_object_id", "0")) if form.getfirst("related_object_id", "").isdigit() else None, json.dumps(photos, ensure_ascii=False), "[]", form.getfirst("tags", ""), "pending_review", user["id"], now, now),
            )
        self.log_action(user, "mobile_submission_created", "field_submission", cur.lastrowid, title)
        return self.redir("/mobile")

    def mobile_tasks(self, user):
        user = self.require_login(user)
        if not user:
            return
        with db() as conn:
            rows = conn.execute("select * from tasks where owner=? or owner='' or owner is null order by status='done', updated_at desc limit 80", (user["name"],)).fetchall()
        cards = ""
        for row in rows:
            done = row["status"] == "done"
            action = "" if done else f"""
<form method="post" action="/mobile/tasks/complete" enctype="multipart/form-data">
  <input type="hidden" name="id" value="{row['id']}">
  <label>{U(r'\u5b8c\u6210\u8bf4\u660e')}</label><textarea name="completion_note"></textarea>
  <label>{U(r'\u7ed3\u679c\u7167\u7247')}</label><input name="photos" type="file" accept="image/*" multiple>
  <p><button>{U(r'\u6807\u8bb0\u5b8c\u6210')}</button></p>
</form>"""
            cards += "<div class='card'><div><h2>{}</h2><p>{}</p><p class='small'>{} · {} · {}</p></div>{}</div>".format(esc(row["title"]), esc(row["description"]), esc(row["priority"]), esc(row["status"]), esc(row["due_date"]), action)
        if not cards:
            cards = "<div class='panel'>{}</div>".format(self.empty_state(U(r"\u6682\u65e0\u4efb\u52a1\u3002")))
        self.out(layout(U(r"\u624b\u673a\u4efb\u52a1"), "<div class='panel'><h2>{}</h2><p class='small'>{}</p></div><div class='grid'>{}</div>".format(U(r"\u6211\u7684\u4efb\u52a1"), U(r"\u5458\u5de5\u53ef\u4ee5\u624b\u673a\u5b8c\u6210\u4efb\u52a1\u5e76\u4e0a\u4f20\u7ed3\u679c\u7167\u7247\u3002"), cards), user=user, wide=True))

    def mobile_task_complete(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        form = self.multipart()
        tid = form.getfirst("id", "")
        note = form.getfirst("completion_note", "")
        photos = self.save_mobile_files(form)
        with db() as conn:
            conn.execute("update tasks set status='done', updated_at=? where id=?", (ts(), tid))
            conn.execute("insert into timeline_events(target_type,target_id,title,body,created_by,created_at) values(?,?,?,?,?,?)", ("task", int(tid) if str(tid).isdigit() else 0, U(r"\u624b\u673a\u5b8c\u6210\u4efb\u52a1"), note + "\n" + json.dumps(photos, ensure_ascii=False), user["id"], ts()))
        self.log_action(user, "mobile_task_completed", "task", tid, note)
        return self.redir("/mobile/tasks")

    def mobile_review(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_review_mobile(user):
            return self.dashboard(user)
        with db() as conn:
            rows = conn.execute("select * from field_submissions order by status='pending_review' desc, updated_at desc limit 100").fetchall()
        cards = ""
        for r in rows:
            cards += """
<div class="card">
  <div><h2>{}</h2><p>{}</p><p class="small">{} · {} · {}</p></div>
  <div class="inline">
    <form method="post" action="/api/mobile/submissions/{}/approve"><button class="green">{}</button></form>
    <form method="post" action="/api/mobile/submissions/{}/reject"><button class="gray">{}</button></form>
    <form method="post" action="/api/mobile/submissions/{}/convert-to-task"><button>{}</button></form>
    <form method="post" action="/api/mobile/submissions/{}/convert-to-knowledge"><button class="orange">{}</button></form>
  </div>
</div>""".format(esc(r["title"]), esc(summarize_text(r["content"], 150)), esc(r["submission_type"]), esc(r["store_id"]), esc(r["status"]), r["id"], U(r"\u901a\u8fc7"), r["id"], U(r"\u9a73\u56de"), r["id"], U(r"\u8f6c\u4efb\u52a1"), r["id"], U(r"\u8f6c\u77e5\u8bc6"))
        if not cards:
            cards = "<div class='panel'>{}</div>".format(self.empty_state(U(r"\u6682\u65e0\u5f85\u5ba1\u6838\u63d0\u4ea4\u3002")))
        self.out(layout(U(r"\u4e00\u7ebf\u63d0\u4ea4\u5ba1\u6838"), "<div class='panel'><h2>{}</h2></div><div class='grid'>{}</div>".format(U(r"\u5ba1\u6838\u4e2d\u5fc3"), cards), user=user, wide=True))

    def mobile_submission_action(self, user, sid, action, form=None):
        if not user:
            return {"ok": False, "message": "login required"}, 401
        if action in ("approve", "reject", "convert-to-task", "convert-to-knowledge") and not self.can_review_mobile(user):
            return {"ok": False, "message": "no permission"}, 403
        now = ts()
        with db() as conn:
            row = conn.execute("select * from field_submissions where id=?", (sid,)).fetchone()
            if not row:
                return {"ok": False, "message": "not found"}, 404
            if action in ("approve", "reject"):
                status = "approved" if action == "approve" else "rejected"
                conn.execute("update field_submissions set status=?, reviewed_by=?, reviewed_at=?, review_notes=?, updated_at=? where id=?", (status, user["id"], now, (form or {}).get("review_notes", ""), now, sid))
                self.log_action(user, "mobile_submission_" + action, "field_submission", sid, row["title"])
                return {"ok": True, "status": status}, 200
            if action == "convert-to-task":
                cur = conn.execute(
                    "insert into tasks(task_id,title,description,owner,related_object_type,related_object_id,priority,status,due_date,source_type,source_id,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    ("TASK-" + uuid.uuid4().hex[:10], row["title"], row["content"], "", "field_submission", row["id"], "normal", "todo", "", "mobile_submission", row["submission_id"], user["id"], now, now),
                )
                conn.execute("update field_submissions set status='converted_to_task', reviewed_by=?, reviewed_at=?, updated_at=? where id=?", (user["id"], now, now, sid))
                self.log_action(user, "mobile_submission_to_task", "task", cur.lastrowid, row["title"])
                return {"ok": True, "task_id": cur.lastrowid}, 200
            if action == "convert-to-knowledge":
                cur = conn.execute(
                    "insert into knowledge_items(title,category,tags,body,ai_summary,source_type,source_ref,approved,created_by,created_at,updated_at,summary,status,visibility) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (row["title"], classify_text(row["content"]), row["tags"], row["content"], summarize_text(row["content"]), "mobile_submission", row["submission_id"], 0, user["id"], now, now, summarize_text(row["content"]), "draft", "manager_only"),
                )
                conn.execute("update field_submissions set status='converted_to_knowledge', reviewed_by=?, reviewed_at=?, updated_at=? where id=?", (user["id"], now, now, sid))
                self.log_action(user, "mobile_submission_to_knowledge", "knowledge", cur.lastrowid, row["title"])
                return {"ok": True, "knowledge_id": cur.lastrowid}, 200
        return {"ok": False, "message": "unknown action"}, 404

    def api_mobile_get(self, user, path):
        if path == "/api/wecom/status":
            return self.json_out({"ok": True, "status": "placeholder", "configured": False, "message": U(r"\u4f01\u4e1a\u5fae\u4fe1\u96c6\u6210\u5df2\u9884\u7559\uff0c\u9700\u5728 .env \u914d\u7f6e\u5bc6\u94a5\u3002")})
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if path == "/api/mobile":
            return self.json_out({"ok": True, "routes": ["/mobile", "/mobile/tasks", "/mobile/review"], "wecom": "placeholder"})
        if path == "/api/mobile/tasks":
            with db() as conn:
                rows = conn.execute("select * from tasks where owner=? or owner='' or owner is null order by updated_at desc limit 100", (user["name"],)).fetchall()
            return self.json_out({"ok": True, "tasks": [row_dict(r) for r in rows]})
        if path == "/api/mobile/submissions":
            with db() as conn:
                if self.can_review_mobile(user):
                    rows = conn.execute("select * from field_submissions order by updated_at desc limit 100").fetchall()
                else:
                    rows = conn.execute("select * from field_submissions where created_by=? order by updated_at desc limit 100", (user["id"],)).fetchall()
            return self.json_out({"ok": True, "submissions": [row_dict(r) for r in rows]})
        m = re.match(r"^/api/mobile/submissions/(\d+)$", path)
        if m:
            with db() as conn:
                row = conn.execute("select * from field_submissions where id=?", (m.group(1),)).fetchone()
            if not row or (not self.can_review_mobile(user) and int(row["created_by"] or 0) != int(user["id"])):
                return self.json_out({"ok": False, "message": "not found"}, code=404)
            return self.json_out({"ok": True, "submission": row_dict(row)})
        if path == "/api/mobile/notifications":
            with db() as conn:
                rows = conn.execute("select * from notifications where recipient_user_id is null or recipient_user_id=? order by created_at desc limit 50", (user["id"],)).fetchall()
            return self.json_out({"ok": True, "notifications": [row_dict(r) for r in rows]})
        return self.json_out({"ok": False, "message": "unknown mobile api"}, code=404)

    def api_mobile_post(self, user, path):
        if path.startswith("/api/wecom"):
            return self.json_out({"ok": False, "message": U(r"\u4f01\u4e1a\u5fae\u4fe1\u5199\u5165\u63a5\u53e3\u5df2\u9884\u7559\uff0c\u672a\u914d\u7f6e\u5bc6\u94a5\u65f6\u4e0d\u6267\u884c\u3002")}, code=501)
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if path == "/api/mobile/submissions":
            form = self.form()
            now = ts()
            with db() as conn:
                cur = conn.execute("insert into field_submissions(submission_id,submission_type,title,content,store_id,employee_id,related_object_type,related_object_id,photos,attachments,tags,status,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("FS-" + uuid.uuid4().hex[:10], form.get("submission_type", "store_note"), form.get("title", U(r"\u672a\u547d\u540d\u63d0\u4ea4")), form.get("content", ""), form.get("store_id", user["store"]), user["id"], form.get("related_object_type", ""), int(form.get("related_object_id")) if str(form.get("related_object_id", "")).isdigit() else None, form.get("photos", "[]"), form.get("attachments", "[]"), form.get("tags", ""), "pending_review", user["id"], now, now))
            self.log_action(user, "mobile_submission_created", "field_submission", cur.lastrowid, form.get("title", ""))
            return self.json_out({"ok": True, "submission_id": cur.lastrowid})
        m = re.match(r"^/api/mobile/submissions/(\d+)/(approve|reject|convert-to-task|convert-to-knowledge)$", path)
        if m:
            result, code = self.mobile_submission_action(user, m.group(1), m.group(2), self.form())
            return self.json_out(result, code=code)
        return self.json_out({"ok": False, "message": "unknown mobile api"}, code=404)

    def api_mobile_put(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        m = re.match(r"^/api/mobile/submissions/(\d+)$", path)
        if not m:
            return self.json_out({"ok": False, "message": "unknown mobile api"}, code=404)
        form = self.form()
        with db() as conn:
            row = conn.execute("select * from field_submissions where id=?", (m.group(1),)).fetchone()
            if not row or (not self.can_review_mobile(user) and int(row["created_by"] or 0) != int(user["id"])):
                return self.json_out({"ok": False, "message": "not found"}, code=404)
            conn.execute("update field_submissions set title=coalesce(?,title), content=coalesce(?,content), tags=coalesce(?,tags), status=coalesce(?,status), updated_at=? where id=?", (form.get("title"), form.get("content"), form.get("tags"), form.get("status") if self.can_review_mobile(user) else None, ts(), m.group(1)))
        self.log_action(user, "mobile_submission_updated", "field_submission", m.group(1), "")
        return self.json_out({"ok": True})

    def can_manage_store_growth(self, user):
        return bool(user and user["role"] in ("boss", "admin", "store_manager", "finance", "purchasing"))

    def store_growth_stores(self):
        return [U(r"\u5357\u5c71\u5e97"), U(r"\u632f\u5174\u5e97"), U(r"\u822a\u82d1\u5e97"), U(r"\u91d1\u6c99\u5e97"), U(r"\u7f51\u5e97")]

    def store_growth_diagnosis_payload(self, store_id):
        data = self.cockpit_data()
        empty = data["empty_message"]
        return {
            "store_id": store_id,
            "sales_status": "waiting_for_store_data",
            "margin_status": "waiting_for_store_data",
            "traffic_status": "manual_input_needed",
            "conversion_status": "manual_input_needed",
            "inventory_status": "waiting_for_sap_detail",
            "staff_status": "waiting_for_task_execution",
            "customer_status": "waiting_for_mobile_feedback",
            "key_problems": [empty, U(r"\u95e8\u5e97\u5ba2\u6d41\u3001\u8f6c\u5316\u548c\u5458\u5de5\u6267\u884c\u9700\u901a\u8fc7\u624b\u673a\u4e00\u7ebf\u8fd0\u8425\u8865\u5145\u3002")],
            "opportunities": [U(r"\u53ef\u4ece\u4e3b\u63a8\u54c1\u724c\u3001\u4e3b\u63a8\u4ea7\u54c1\u3001\u8001\u5ba2\u6fc0\u6d3b\u548c\u95e8\u5e97\u5185\u5bb9\u5f00\u59cb\u3002")],
            "ai_suggestions": [U(r"\u5148\u5efa\u7acb 7-30 \u5929\u95e8\u5e97\u589e\u957f\u8ba1\u5212\uff0c\u518d\u628a\u52a8\u4f5c\u62c6\u6210\u4efb\u52a1\u3002")],
            "data_sources": ["sap_summary", "mobile_submissions", "tasks", "content_engine", "reporting_engine"],
        }

    def store_growth_center(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_manage_store_growth(user):
            return self.dashboard(user)
        with db() as conn:
            diagnoses = conn.execute("select * from store_diagnoses order by updated_at desc limit 20").fetchall()
            plans = conn.execute("select * from store_growth_plans order by updated_at desc limit 50").fetchall()
            activities = conn.execute("select * from store_activities order by updated_at desc limit 30").fetchall()
            focus = conn.execute("select * from store_focus_items order by updated_at desc limit 30").fetchall()
            field_counts = conn.execute("select status,count(*) c from field_submissions group by status").fetchall()
        store_options = "".join("<option value='{}'>{}</option>".format(esc(s), esc(s)) for s in self.store_growth_stores())
        plan_cards = "".join("<div class='card'><div><h2>{}</h2><p>{}</p><p class='small'>{} · {} · {}</p></div><form method='post' action='/api/store-growth/plans/{}/create-tasks'><button>{}</button></form></div>".format(esc(p["title"]), esc(p["goal"]), esc(p["store_id"]), esc(p["owner"]), esc(p["status"]), p["id"], U(r"\u751f\u6210\u4efb\u52a1")) for p in plans) or "<div class='panel'>{}</div>".format(self.empty_state(U(r"\u6682\u65e0\u589e\u957f\u8ba1\u5212\u3002")))
        activity_items = [a["store_id"] + " · " + a["title"] + " · " + a["status"] for a in activities] or [U(r"\u6682\u65e0\u95e8\u5e97\u6d3b\u52a8\u3002")]
        focus_items = [f["store_id"] + " · " + (f["brand_id"] or "") + " · " + (f["product_id"] or "") + " · " + f["status"] for f in focus] or [U(r"\u6682\u65e0\u4e3b\u63a8\u54c1\u724c/\u4ea7\u54c1\u3002")]
        field_items = [r["status"] + ": " + str(r["c"]) for r in field_counts] or [U(r"\u6682\u65e0\u4e00\u7ebf\u63d0\u4ea4\u6570\u636e\u3002")]
        diag_items = [d["store_id"] + " · " + d["status"] + " · " + dt(d["updated_at"]) for d in diagnoses] or [U(r"\u6682\u65e0\u95e8\u5e97\u8bca\u65ad\u3002")]
        body = f"""
<div class="panel">
  <h2>{U(r'\u95e8\u5e97\u589e\u957f\u5f15\u64ce')}</h2>
  <p class="small">{U(r'\u628a\u95e8\u5e97\u8bca\u65ad\u3001\u589e\u957f\u8ba1\u5212\u3001\u6d3b\u52a8\u3001\u5458\u5de5\u6267\u884c\u3001\u5185\u5bb9\u548c\u590d\u76d8\u4e32\u8d77\u6765\u3002\u6ca1\u6709\u6570\u636e\u65f6\u53ea\u663e\u793a\u7a7a\u72b6\u6001\u548c\u6a21\u677f\uff0c\u4e0d\u7f16\u9020\u7ed3\u8bba\u3002')}</p>
</div>
<div class="split">
  <div class="panel form"><h2>{U(r'\u65b0\u5efa\u95e8\u5e97\u8bca\u65ad')}</h2><form method="post" action="/store-growth/diagnosis/save"><label>{T['store']}</label><select name="store_id">{store_options}</select><label>{U(r'\u5f00\u59cb\u65e5\u671f')}</label><input name="date_range_start"><label>{U(r'\u7ed3\u675f\u65e5\u671f')}</label><input name="date_range_end"><p><button>{U(r'\u751f\u6210\u8bca\u65ad\u8349\u7a3f')}</button></p></form></div>
  <div class="panel"><h2>{U(r'\u8bca\u65ad\u8bb0\u5f55')}</h2>{self.bullets(diag_items)}</div>
</div>
<div class="split">
  <div class="panel form"><h2>{U(r'\u65b0\u5efa\u589e\u957f\u8ba1\u5212')}</h2><form method="post" action="/store-growth/plans/save"><label>{T['store']}</label><select name="store_id">{store_options}</select><label>{U(r'\u8ba1\u5212\u6807\u9898')}</label><input name="title" required><label>{U(r'\u76ee\u6807')}</label><textarea name="goal"></textarea><label>{U(r'\u5173\u952e\u52a8\u4f5c')}</label><textarea name="key_actions" placeholder="{U(r'\u6bcf\u884c\u4e00\u4e2a\u52a8\u4f5c\uff0c\u53ef\u751f\u6210\u4efb\u52a1')}"></textarea><label>{U(r'\u8d23\u4efb\u4eba')}</label><input name="owner" value="{esc(user['name'])}"><p><button>{U(r'\u4fdd\u5b58\u8ba1\u5212')}</button></p></form></div>
  <div class="panel form"><h2>{U(r'\u95e8\u5e97\u6d3b\u52a8')}</h2><form method="post" action="/store-growth/activities/save"><label>{T['store']}</label><select name="store_id">{store_options}</select><label>{U(r'\u6d3b\u52a8\u6807\u9898')}</label><input name="title" required><label>{U(r'\u6d3b\u52a8\u7c7b\u578b')}</label><input name="activity_type" placeholder="{U(r'\u4f1a\u5458\u65e5 / \u88c5\u5907\u8bfe\u5802 / \u6e05\u8d27\u6d3b\u52a8')}"><label>{U(r'\u5185\u5bb9\u8ba1\u5212')}</label><textarea name="content_plan"></textarea><label>{U(r'\u4efb\u52a1\u8ba1\u5212')}</label><textarea name="task_plan"></textarea><p><button>{U(r'\u4fdd\u5b58\u6d3b\u52a8')}</button></p></form></div>
</div>
<div class="panel"><h2>{U(r'\u589e\u957f\u8ba1\u5212')}</h2><div class="grid">{plan_cards}</div></div>
<div class="split"><div class="panel"><h2>{U(r'\u95e8\u5e97\u6d3b\u52a8')}</h2>{self.bullets(activity_items)}</div><div class="panel"><h2>{U(r'\u4e00\u7ebf\u6267\u884c')}</h2>{self.bullets(field_items)}<p><a class="btn" href="/mobile/review">{U(r'\u5ba1\u6838\u4e00\u7ebf\u63d0\u4ea4')}</a></p></div></div>
<div class="split">
  <div class="panel form"><h2>{U(r'\u4e3b\u63a8\u54c1\u724c/\u4ea7\u54c1')}</h2><form method="post" action="/store-growth/focus/save"><label>{T['store']}</label><select name="store_id">{store_options}</select><label>{U(r'\u54c1\u724c')}</label><input name="brand_id" placeholder="KAILAS / Osprey / VAFOX"><label>{U(r'\u4ea7\u54c1')}</label><input name="product_id"><label>{U(r'\u4e3b\u63a8\u7406\u7531')}</label><textarea name="focus_reason"></textarea><label>{U(r'\u5468\u671f')}</label><input name="period"><p><button>{U(r'\u4fdd\u5b58\u4e3b\u63a8')}</button></p></form></div>
  <div class="panel"><h2>{U(r'\u4e3b\u63a8\u6e05\u5355')}</h2>{self.bullets(focus_items)}</div>
</div>
<div class="panel"><h2>{U(r'\u5185\u5bb9\u4e0e\u590d\u76d8')}</h2>{self.bullets([U(r'\u53ef\u4ece\u589e\u957f\u8ba1\u5212\u751f\u6210\u95e8\u5e97\u5c0f\u7ea2\u4e66\u3001\u89c6\u9891\u53f7\u3001\u670b\u53cb\u5708\u548c\u793e\u7fa4\u901a\u77e5\u8349\u7a3f\u3002'), U(r'\u53ef\u4ece\u6d3b\u52a8\u548c\u4efb\u52a1\u751f\u6210\u95e8\u5e97\u590d\u76d8\u62a5\u544a\u8349\u7a3f\u3002')])}<p><a class="btn orange" href="/content">{U(r'\u6253\u5f00\u5185\u5bb9\u5f15\u64ce')}</a> <a class="btn dark" href="/reports">{U(r'\u6253\u5f00\u62a5\u544a\u4e2d\u5fc3')}</a></p></div>"""
        self.out(layout(U(r"\u95e8\u5e97\u589e\u957f\u5f15\u64ce"), body, user=user, wide=True))

    def store_growth_diagnosis_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        if not self.can_manage_store_growth(user):
            return self.redir("/")
        form = self.form()
        payload = self.store_growth_diagnosis_payload(form.get("store_id", ""))
        now = ts()
        with db() as conn:
            cur = conn.execute(
                "insert into store_diagnoses(diagnosis_id,store_id,date_range_start,date_range_end,sales_status,margin_status,traffic_status,conversion_status,inventory_status,staff_status,customer_status,key_problems,opportunities,ai_suggestions,data_sources,status,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("SD-" + uuid.uuid4().hex[:10], payload["store_id"], form.get("date_range_start", ""), form.get("date_range_end", ""), payload["sales_status"], payload["margin_status"], payload["traffic_status"], payload["conversion_status"], payload["inventory_status"], payload["staff_status"], payload["customer_status"], json.dumps(payload["key_problems"], ensure_ascii=False), json.dumps(payload["opportunities"], ensure_ascii=False), json.dumps(payload["ai_suggestions"], ensure_ascii=False), json.dumps(payload["data_sources"], ensure_ascii=False), "draft", user["id"], now, now),
            )
        self.log_action(user, "store_diagnosis_created", "store_diagnosis", cur.lastrowid, payload["store_id"])
        return self.redir("/store-growth")

    def store_growth_plan_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        if not self.can_manage_store_growth(user):
            return self.redir("/")
        form = self.form()
        now = ts()
        with db() as conn:
            cur = conn.execute(
                "insert into store_growth_plans(growth_plan_id,store_id,title,goal,start_date,end_date,target_sales,target_margin,target_customers,target_tasks,key_actions,related_brands,related_products,owner,status,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("SGP-" + uuid.uuid4().hex[:10], form.get("store_id", ""), form.get("title", U(r"\u672a\u547d\u540d\u589e\u957f\u8ba1\u5212")), form.get("goal", ""), form.get("start_date", ""), form.get("end_date", ""), form.get("target_sales", ""), form.get("target_margin", ""), form.get("target_customers", ""), form.get("target_tasks", ""), form.get("key_actions", ""), form.get("related_brands", ""), form.get("related_products", ""), form.get("owner", user["name"]), "draft", now, now),
            )
        self.log_action(user, "store_growth_plan_created", "store_growth_plan", cur.lastrowid, form.get("title", ""))
        return self.redir("/store-growth")

    def store_growth_activity_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        if not self.can_manage_store_growth(user):
            return self.redir("/")
        form = self.form()
        now = ts()
        with db() as conn:
            cur = conn.execute(
                "insert into store_activities(activity_id,store_id,title,activity_type,start_date,end_date,target_customer,target_brand,target_product,budget,expected_result,content_plan,task_plan,status,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("SA-" + uuid.uuid4().hex[:10], form.get("store_id", ""), form.get("title", U(r"\u672a\u547d\u540d\u6d3b\u52a8")), form.get("activity_type", ""), form.get("start_date", ""), form.get("end_date", ""), form.get("target_customer", ""), form.get("target_brand", ""), form.get("target_product", ""), form.get("budget", ""), form.get("expected_result", ""), form.get("content_plan", ""), form.get("task_plan", ""), "draft", now, now),
            )
        self.log_action(user, "store_activity_created", "store_activity", cur.lastrowid, form.get("title", ""))
        return self.redir("/store-growth")

    def store_growth_focus_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        if not self.can_manage_store_growth(user):
            return self.redir("/")
        form = self.form()
        now = ts()
        with db() as conn:
            cur = conn.execute("insert into store_focus_items(focus_id,store_id,brand_id,product_id,focus_reason,period,status,created_at,updated_at) values(?,?,?,?,?,?,?,?,?)", ("SF-" + uuid.uuid4().hex[:10], form.get("store_id", ""), form.get("brand_id", ""), form.get("product_id", ""), form.get("focus_reason", ""), form.get("period", ""), "active", now, now))
        self.log_action(user, "store_focus_created", "store_focus", cur.lastrowid, form.get("store_id", ""))
        return self.redir("/store-growth")

    def store_growth_create_tasks(self, user, plan_id):
        if not user:
            return {"ok": False, "message": "login required"}, 401
        if not self.can_manage_store_growth(user):
            return {"ok": False, "message": "no permission"}, 403
        now = ts()
        created = []
        with db() as conn:
            plan = conn.execute("select * from store_growth_plans where id=?", (plan_id,)).fetchone()
            if not plan:
                return {"ok": False, "message": "not found"}, 404
            actions = csv_values((plan["key_actions"] or "").replace("\n", ","))
            if not actions:
                actions = [U(r"\u8c03\u6574\u9648\u5217"), U(r"\u4e3b\u63a8\u54c1\u724c/\u4ea7\u54c1"), U(r"\u8054\u7cfb\u8001\u5ba2"), U(r"\u4e0a\u4f20\u95e8\u5e97\u7167\u7247"), U(r"\u590d\u76d8\u5b8c\u6210\u60c5\u51b5")]
            for action in actions[:12]:
                cur = conn.execute(
                    "insert into tasks(task_id,title,description,owner,related_object_type,related_object_id,priority,status,due_date,source_type,source_id,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    ("TASK-" + uuid.uuid4().hex[:10], action, plan["store_id"] + " · " + plan["title"], plan["owner"], "store_growth_plan", plan["id"], "normal", "todo", plan["end_date"] or "", "store_growth", plan["growth_plan_id"], user["id"], now, now),
                )
                created.append(cur.lastrowid)
            conn.execute("update store_growth_plans set status='active', updated_at=? where id=?", (now, plan_id))
        self.log_action(user, "store_growth_tasks_created", "store_growth_plan", plan_id, str(len(created)))
        return {"ok": True, "task_ids": created}, 200

    def api_store_growth_get(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_manage_store_growth(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        with db() as conn:
            if path == "/api/store-growth":
                counts = {
                    "diagnoses": conn.execute("select count(*) c from store_diagnoses").fetchone()["c"],
                    "plans": conn.execute("select count(*) c from store_growth_plans").fetchone()["c"],
                    "activities": conn.execute("select count(*) c from store_activities").fetchone()["c"],
                    "focus": conn.execute("select count(*) c from store_focus_items").fetchone()["c"],
                }
                return self.json_out({"ok": True, "counts": counts, "stores": self.store_growth_stores(), "empty_message": self.cockpit_data()["empty_message"]})
            if path == "/api/store-growth/diagnosis":
                rows = conn.execute("select * from store_diagnoses order by updated_at desc limit 100").fetchall()
                return self.json_out({"ok": True, "diagnosis": [row_dict(r) for r in rows]})
            if path == "/api/store-growth/plans":
                rows = conn.execute("select * from store_growth_plans order by updated_at desc limit 100").fetchall()
                return self.json_out({"ok": True, "plans": [row_dict(r) for r in rows]})
            m = re.match(r"^/api/store-growth/plans/(\d+)$", path)
            if m:
                row = conn.execute("select * from store_growth_plans where id=?", (m.group(1),)).fetchone()
                return self.json_out({"ok": bool(row), "plan": row_dict(row)} if row else {"ok": False, "message": "not found"}, code=200 if row else 404)
            if path == "/api/store-growth/activities":
                rows = conn.execute("select * from store_activities order by updated_at desc limit 100").fetchall()
                return self.json_out({"ok": True, "activities": [row_dict(r) for r in rows]})
            if path == "/api/store-growth/focus":
                rows = conn.execute("select * from store_focus_items order by updated_at desc limit 100").fetchall()
                return self.json_out({"ok": True, "focus": [row_dict(r) for r in rows]})
            if path == "/api/store-growth/reports":
                rows = conn.execute("select * from reports where report_type in ('store','store_growth') order by updated_at desc limit 50").fetchall()
                return self.json_out({"ok": True, "reports": [row_dict(r) for r in rows]})
        return self.json_out({"ok": False, "message": "unknown store growth api"}, code=404)

    def api_store_growth_post(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_manage_store_growth(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        form = self.form()
        now = ts()
        if path == "/api/store-growth/diagnosis":
            payload = self.store_growth_diagnosis_payload(form.get("store_id", ""))
            with db() as conn:
                cur = conn.execute("insert into store_diagnoses(diagnosis_id,store_id,date_range_start,date_range_end,sales_status,margin_status,traffic_status,conversion_status,inventory_status,staff_status,customer_status,key_problems,opportunities,ai_suggestions,data_sources,status,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("SD-" + uuid.uuid4().hex[:10], payload["store_id"], form.get("date_range_start", ""), form.get("date_range_end", ""), payload["sales_status"], payload["margin_status"], payload["traffic_status"], payload["conversion_status"], payload["inventory_status"], payload["staff_status"], payload["customer_status"], json.dumps(payload["key_problems"], ensure_ascii=False), json.dumps(payload["opportunities"], ensure_ascii=False), json.dumps(payload["ai_suggestions"], ensure_ascii=False), json.dumps(payload["data_sources"], ensure_ascii=False), "draft", user["id"], now, now))
            self.log_action(user, "store_diagnosis_created", "store_diagnosis", cur.lastrowid, payload["store_id"])
            return self.json_out({"ok": True, "diagnosis_id": cur.lastrowid, "diagnosis": payload})
        if path == "/api/store-growth/plans":
            with db() as conn:
                cur = conn.execute("insert into store_growth_plans(growth_plan_id,store_id,title,goal,start_date,end_date,target_sales,target_margin,target_customers,target_tasks,key_actions,related_brands,related_products,owner,status,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("SGP-" + uuid.uuid4().hex[:10], form.get("store_id", ""), form.get("title", U(r"\u672a\u547d\u540d\u589e\u957f\u8ba1\u5212")), form.get("goal", ""), form.get("start_date", ""), form.get("end_date", ""), form.get("target_sales", ""), form.get("target_margin", ""), form.get("target_customers", ""), form.get("target_tasks", ""), form.get("key_actions", ""), form.get("related_brands", ""), form.get("related_products", ""), form.get("owner", user["name"]), form.get("status", "draft"), now, now))
            self.log_action(user, "store_growth_plan_created", "store_growth_plan", cur.lastrowid, form.get("title", ""))
            return self.json_out({"ok": True, "plan_id": cur.lastrowid})
        m = re.match(r"^/api/store-growth/plans/(\d+)/create-tasks$", path)
        if m:
            result, code = self.store_growth_create_tasks(user, m.group(1))
            return self.json_out(result, code=code)
        if path == "/api/store-growth/activities":
            with db() as conn:
                cur = conn.execute("insert into store_activities(activity_id,store_id,title,activity_type,start_date,end_date,target_customer,target_brand,target_product,budget,expected_result,content_plan,task_plan,status,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("SA-" + uuid.uuid4().hex[:10], form.get("store_id", ""), form.get("title", U(r"\u672a\u547d\u540d\u6d3b\u52a8")), form.get("activity_type", ""), form.get("start_date", ""), form.get("end_date", ""), form.get("target_customer", ""), form.get("target_brand", ""), form.get("target_product", ""), form.get("budget", ""), form.get("expected_result", ""), form.get("content_plan", ""), form.get("task_plan", ""), form.get("status", "draft"), now, now))
            self.log_action(user, "store_activity_created", "store_activity", cur.lastrowid, form.get("title", ""))
            return self.json_out({"ok": True, "activity_id": cur.lastrowid})
        if path == "/api/store-growth/focus":
            with db() as conn:
                cur = conn.execute("insert into store_focus_items(focus_id,store_id,brand_id,product_id,focus_reason,period,status,created_at,updated_at) values(?,?,?,?,?,?,?,?,?)", ("SF-" + uuid.uuid4().hex[:10], form.get("store_id", ""), form.get("brand_id", ""), form.get("product_id", ""), form.get("focus_reason", ""), form.get("period", ""), form.get("status", "active"), now, now))
            self.log_action(user, "store_focus_created", "store_focus", cur.lastrowid, form.get("store_id", ""))
            return self.json_out({"ok": True, "focus_id": cur.lastrowid})
        if path == "/api/store-growth/reports":
            payload = self.report_draft_payload(user, "store_growth", form.get("title", U(r"\u95e8\u5e97\u589e\u957f\u590d\u76d8\u62a5\u544a")), "store", None)
            return self.json_out({"ok": True, "report": payload, "message": U(r"\u95e8\u5e97\u590d\u76d8\u62a5\u544a\u6846\u67b6\u5df2\u751f\u6210\uff0c\u9700\u4eba\u5de5\u5ba1\u6838\u3002")})
        return self.json_out({"ok": False, "message": "unknown store growth api"}, code=404)

    def api_store_growth_put(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_manage_store_growth(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        m = re.match(r"^/api/store-growth/plans/(\d+)$", path)
        if not m:
            return self.json_out({"ok": False, "message": "unknown store growth api"}, code=404)
        form = self.form()
        with db() as conn:
            conn.execute("update store_growth_plans set title=coalesce(?,title), goal=coalesce(?,goal), key_actions=coalesce(?,key_actions), owner=coalesce(?,owner), status=coalesce(?,status), updated_at=? where id=?", (form.get("title"), form.get("goal"), form.get("key_actions"), form.get("owner"), form.get("status"), ts(), m.group(1)))
        self.log_action(user, "store_growth_plan_updated", "store_growth_plan", m.group(1), "")
        return self.json_out({"ok": True})

    def can_manage_brand_growth(self, user):
        return bool(user and user["role"] in ("boss", "admin", "purchasing", "finance", "store_manager"))

    def brand_growth_brands(self):
        return ["KAILAS", "Osprey", "Mammut", "Salomon", "Deuter", "Gregory", "VAFOX"]

    def brand_roles(self):
        return ["core_growth", "profit", "traffic", "image", "strategic", "clearance", "experimental", "private_label"]

    def brand_diagnosis_payload(self, brand_id):
        empty = self.cockpit_data()["empty_message"]
        return {
            "brand_id": brand_id,
            "sales_status": "waiting_for_brand_sap_data",
            "margin_status": "waiting_for_brand_sap_data",
            "inventory_status": "waiting_for_brand_inventory_data",
            "discount_status": "manual_review_needed",
            "supplier_status": "manual_review_needed",
            "market_status": "research_pending",
            "customer_feedback": "waiting_for_mobile_feedback",
            "key_problems": [empty, U(r"\u54c1\u724c\u7ef4\u5ea6 SAP \u6570\u636e\u3001\u5916\u90e8\u7814\u7a76\u548c\u4f9b\u5e94\u5546\u4fe1\u606f\u9700\u8865\u5145\u540e\u624d\u80fd\u5f97\u51fa\u7ed3\u8bba\u3002")],
            "opportunities": [U(r"\u53ef\u5148\u6309\u54c1\u724c\u89d2\u8272\u3001\u4ea7\u54c1\u7ec4\u5408\u3001\u5e93\u5b58\u538b\u529b\u548c\u5b9a\u4ef7\u98ce\u9669\u5efa\u7acb\u7ba1\u7406\u6846\u67b6\u3002")],
            "ai_suggestions": [U(r"\u4e0d\u8981\u5148\u4e0b\u7ed3\u8bba\uff0c\u5148\u5efa\u7acb\u54c1\u724c\u89d2\u8272\u548c\u4ef7\u683c\u98ce\u9669\u6a21\u677f\u3002")],
            "data_sources": ["sap_summary", "mobile_feedback", "research", "knowledge", "pricing_strategy"],
        }

    def brand_growth_center(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_manage_brand_growth(user):
            return self.dashboard(user)
        with db() as conn:
            diagnoses = conn.execute("select * from brand_diagnoses order by updated_at desc limit 20").fetchall()
            strategies = conn.execute("select * from brand_strategies order by updated_at desc limit 50").fetchall()
            portfolios = conn.execute("select * from product_portfolios order by updated_at desc limit 50").fetchall()
            pricing = conn.execute("select * from pricing_strategies order by updated_at desc limit 30").fetchall()
            risks = conn.execute("select * from supplier_brand_risks order by updated_at desc limit 30").fetchall()
        brand_opts = "".join("<option value='{}'>{}</option>".format(esc(b), esc(b)) for b in self.brand_growth_brands())
        role_opts = "".join("<option value='{}'>{}</option>".format(esc(r), esc(r)) for r in self.brand_roles())
        strategy_cards = "".join("<div class='card'><div><h2>{}</h2><p>{}</p><p class='small'>{} · {} · {}</p></div></div>".format(esc(s["strategy_title"]), esc(s["growth_goal"]), esc(s["brand_id"]), esc(s["brand_role"]), esc(s["status"])) for s in strategies) or "<div class='panel'>{}</div>".format(self.empty_state(U(r"\u6682\u65e0\u54c1\u724c\u7b56\u7565\u3002")))
        diag_items = [d["brand_id"] + " · " + d["status"] + " · " + dt(d["updated_at"]) for d in diagnoses] or [U(r"\u6682\u65e0\u54c1\u724c\u8bca\u65ad\u3002")]
        portfolio_items = [p["brand_id"] + " · " + (p["product_id"] or "") + " · " + (p["product_role"] or "") + " · " + p["status"] for p in portfolios] or [U(r"\u6682\u65e0\u4ea7\u54c1\u7ec4\u5408\u3002")]
        pricing_items = [p["brand_id"] + " · " + (p["normal_discount"] or "") + " · " + (p["minimum_allowed_discount"] or "") + " · " + p["status"] for p in pricing] or [U(r"\u6682\u65e0\u5b9a\u4ef7\u7b56\u7565\u3002")]
        risk_items = [r["brand_id"] + " · " + (r["rebate_uncertainty"] or "") + " · " + r["status"] for r in risks] or [U(r"\u6682\u65e0\u4f9b\u5e94\u5546\u4e0e\u8fd4\u70b9\u98ce\u9669\u3002")]
        body = f"""
<div class="panel"><h2>{U(r'\u54c1\u724c\u589e\u957f + \u4ea7\u54c1\u7ec4\u5408\u5f15\u64ce')}</h2><p class="small">{U(r'\u7528\u4e8e\u533a\u5206\u54c1\u724c\u89d2\u8272\u3001\u4ea7\u54c1\u89d2\u8272\u3001\u5b9a\u4ef7\u98ce\u9669\u3001\u5e93\u5b58\u538b\u529b\u548c\u4f9b\u5e94\u5546\u98ce\u9669\u3002\u6ca1\u6709\u771f\u5b9e\u6570\u636e\u65f6\u53ea\u663e\u793a\u6846\u67b6\u3002')}</p></div>
<div class="split">
  <div class="panel form"><h2>{U(r'\u54c1\u724c\u8bca\u65ad')}</h2><form method="post" action="/brand-growth/diagnosis/save"><label>{U(r'\u54c1\u724c')}</label><select name="brand_id">{brand_opts}</select><label>{U(r'\u5f00\u59cb\u65e5\u671f')}</label><input name="date_range_start"><label>{U(r'\u7ed3\u675f\u65e5\u671f')}</label><input name="date_range_end"><p><button>{U(r'\u751f\u6210\u8bca\u65ad\u8349\u7a3f')}</button></p></form></div>
  <div class="panel"><h2>{U(r'\u8bca\u65ad\u8bb0\u5f55')}</h2>{self.bullets(diag_items)}</div>
</div>
<div class="split">
  <div class="panel form"><h2>{U(r'\u54c1\u724c\u7b56\u7565')}</h2><form method="post" action="/brand-growth/strategies/save"><label>{U(r'\u54c1\u724c')}</label><select name="brand_id">{brand_opts}</select><label>{U(r'\u7b56\u7565\u6807\u9898')}</label><input name="strategy_title" required><label>{U(r'\u54c1\u724c\u89d2\u8272')}</label><select name="brand_role">{role_opts}</select><label>{U(r'\u589e\u957f\u76ee\u6807')}</label><textarea name="growth_goal"></textarea><label>{U(r'\u98ce\u9669\u63a7\u5236')}</label><textarea name="risk_control"></textarea><label>{U(r'\u5173\u952e\u52a8\u4f5c')}</label><textarea name="key_actions"></textarea><p><button>{U(r'\u4fdd\u5b58\u7b56\u7565')}</button></p></form></div>
  <div class="panel form"><h2>{U(r'\u4ea7\u54c1\u7ec4\u5408')}</h2><form method="post" action="/brand-growth/portfolio/save"><label>{U(r'\u54c1\u724c')}</label><select name="brand_id">{brand_opts}</select><label>{U(r'\u4ea7\u54c1/SKU')}</label><input name="product_id"><label>{U(r'\u4ea7\u54c1\u89d2\u8272')}</label><input name="product_role" placeholder="hero / profit / traffic / clearance"><label>{U(r'\u63a8\u8350')}</label><textarea name="recommendation"></textarea><p><button>{U(r'\u4fdd\u5b58\u4ea7\u54c1\u7ec4\u5408')}</button></p></form></div>
</div>
<div class="panel"><h2>{U(r'\u54c1\u724c\u7b56\u7565')}</h2><div class="grid">{strategy_cards}</div></div>
<div class="split">
  <div class="panel form"><h2>{U(r'\u5b9a\u4ef7\u7b56\u7565')}</h2><form method="post" action="/brand-growth/pricing/save"><label>{U(r'\u54c1\u724c')}</label><select name="brand_id">{brand_opts}</select><label>{U(r'\u5e38\u89c4\u6298\u6263')}</label><input name="normal_discount"><label>{U(r'\u4fc3\u9500\u6298\u6263')}</label><input name="promotion_discount"><label>{U(r'\u6e05\u4ed3\u6298\u6263')}</label><input name="clearance_discount"><label>{U(r'\u6700\u4f4e\u5141\u8bb8\u6298\u6263')}</label><input name="minimum_allowed_discount"><label>{U(r'\u8bf4\u660e')}</label><textarea name="notes"></textarea><p><button>{U(r'\u4fdd\u5b58\u5b9a\u4ef7')}</button></p></form></div>
  <div class="panel"><h2>Osprey {U(r'\u6298\u6263\u8bd5\u7b97')}</h2><p class="small">{U(r'59 / 60 / 62 / 65 \u6298\u4ec5\u4f5c\u6a21\u677f\u8bd5\u7b97\uff0c\u4e0d\u4ee3\u8868\u771f\u5b9e\u7ed3\u8bba\u3002')}</p><p><a class="btn" href="/brands/osprey-risk">{U(r'\u6253\u5f00 Osprey \u98ce\u9669\u9875')}</a></p></div>
</div>
<div class="split"><div class="panel"><h2>{U(r'\u4ea7\u54c1\u7ec4\u5408')}</h2>{self.bullets(portfolio_items)}</div><div class="panel"><h2>{U(r'\u5b9a\u4ef7\u7b56\u7565')}</h2>{self.bullets(pricing_items)}</div></div>
<div class="panel"><h2>{U(r'\u4f9b\u5e94\u5546\u4e0e\u8fd4\u70b9\u98ce\u9669')}</h2>{self.bullets(risk_items)}</div>
<div class="panel"><h2>{U(r'\u5e93\u5b58\u7ec4\u5408\u77e9\u9635')}</h2>{self.bullets([U(r'\u9ad8\u9500\u552e + \u9ad8\u6bdb\u5229 = \u6838\u5fc3\u4fdd\u7559'), U(r'\u9ad8\u9500\u552e + \u4f4e\u6bdb\u5229 = \u5f15\u6d41\u63a7\u5236'), U(r'\u4f4e\u9500\u552e + \u9ad8\u6bdb\u5229 = \u7cbe\u51c6\u63a8\u8350'), U(r'\u4f4e\u9500\u552e + \u4f4e\u6bdb\u5229 = \u6e05\u4ed3\u5904\u7406'), U(r'\u9ad8\u5e93\u5b58 + \u4f4e\u6bdb\u5229 = \u9ad8\u98ce\u9669')])}</div>"""
        self.out(layout(U(r"\u54c1\u724c\u589e\u957f\u5f15\u64ce"), body, user=user, wide=True))

    def brand_growth_diagnosis_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        if not self.can_manage_brand_growth(user):
            return self.redir("/")
        form = self.form()
        payload = self.brand_diagnosis_payload(form.get("brand_id", ""))
        now = ts()
        with db() as conn:
            cur = conn.execute("insert into brand_diagnoses(diagnosis_id,brand_id,date_range_start,date_range_end,sales_status,margin_status,inventory_status,discount_status,supplier_status,market_status,customer_feedback,key_problems,opportunities,ai_suggestions,data_sources,status,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("BD-" + uuid.uuid4().hex[:10], payload["brand_id"], form.get("date_range_start", ""), form.get("date_range_end", ""), payload["sales_status"], payload["margin_status"], payload["inventory_status"], payload["discount_status"], payload["supplier_status"], payload["market_status"], payload["customer_feedback"], json.dumps(payload["key_problems"], ensure_ascii=False), json.dumps(payload["opportunities"], ensure_ascii=False), json.dumps(payload["ai_suggestions"], ensure_ascii=False), json.dumps(payload["data_sources"], ensure_ascii=False), "draft", user["id"], now, now))
        self.log_action(user, "brand_diagnosis_created", "brand_diagnosis", cur.lastrowid, payload["brand_id"])
        return self.redir("/brand-growth")

    def brand_growth_strategy_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        if not self.can_manage_brand_growth(user):
            return self.redir("/")
        form = self.form()
        now = ts()
        with db() as conn:
            cur = conn.execute("insert into brand_strategies(strategy_id,brand_id,strategy_title,brand_role,target_customer,target_stores,pricing_principle,inventory_principle,content_principle,growth_goal,risk_control,key_actions,status,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("BS-" + uuid.uuid4().hex[:10], form.get("brand_id", ""), form.get("strategy_title", U(r"\u672a\u547d\u540d\u54c1\u724c\u7b56\u7565")), form.get("brand_role", ""), form.get("target_customer", ""), form.get("target_stores", ""), form.get("pricing_principle", ""), form.get("inventory_principle", ""), form.get("content_principle", ""), form.get("growth_goal", ""), form.get("risk_control", ""), form.get("key_actions", ""), "draft", user["id"], now, now))
        self.log_action(user, "brand_strategy_created", "brand_strategy", cur.lastrowid, form.get("brand_id", ""))
        return self.redir("/brand-growth")

    def brand_growth_portfolio_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        if not self.can_manage_brand_growth(user):
            return self.redir("/")
        form = self.form()
        now = ts()
        with db() as conn:
            cur = conn.execute("insert into product_portfolios(portfolio_id,brand_id,product_id,product_role,season,status,sales_level,margin_level,inventory_level,markdown_level,recommendation,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?)", ("PF-" + uuid.uuid4().hex[:10], form.get("brand_id", ""), form.get("product_id", ""), form.get("product_role", ""), form.get("season", ""), form.get("status", "draft"), form.get("sales_level", ""), form.get("margin_level", ""), form.get("inventory_level", ""), form.get("markdown_level", ""), form.get("recommendation", ""), now, now))
        self.log_action(user, "product_portfolio_updated", "product_portfolio", cur.lastrowid, form.get("brand_id", ""))
        return self.redir("/brand-growth")

    def brand_growth_pricing_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        if not self.can_manage_brand_growth(user):
            return self.redir("/")
        form = self.form()
        now = ts()
        with db() as conn:
            cur = conn.execute("insert into pricing_strategies(pricing_strategy_id,brand_id,product_id,normal_discount,promotion_discount,clearance_discount,minimum_allowed_discount,rebate_assumption,margin_warning_line,notes,status,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?)", ("PS-" + uuid.uuid4().hex[:10], form.get("brand_id", ""), form.get("product_id", ""), form.get("normal_discount", ""), form.get("promotion_discount", ""), form.get("clearance_discount", ""), form.get("minimum_allowed_discount", ""), form.get("rebate_assumption", ""), form.get("margin_warning_line", ""), form.get("notes", ""), "draft", now, now))
        self.log_action(user, "pricing_strategy_changed", "pricing_strategy", cur.lastrowid, form.get("brand_id", ""))
        return self.redir("/brand-growth")

    def brand_growth_create_tasks(self, user):
        if not user:
            return {"ok": False, "message": "login required"}, 401
        if not self.can_manage_brand_growth(user):
            return {"ok": False, "message": "no permission"}, 403
        form = self.form()
        brand = form.get("brand_id", "Osprey")
        actions = csv_values(form.get("actions", "")) or [U(r"\u68c0\u67e5") + brand + U(r"\u5e93\u5b58"), U(r"\u6536\u96c6") + brand + U(r"\u5e02\u573a\u4ef7\u683c\u8bc1\u636e"), U(r"\u5236\u5b9a") + brand + U(r"\u4e3b\u63a8\u65b9\u6848")]
        now = ts()
        ids = []
        with db() as conn:
            for action in actions[:10]:
                cur = conn.execute("insert into tasks(task_id,title,description,owner,related_object_type,related_object_id,priority,status,due_date,source_type,source_id,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("TASK-" + uuid.uuid4().hex[:10], action, brand + " · " + U(r"\u54c1\u724c\u589e\u957f\u4efb\u52a1"), form.get("owner", user["name"]), "brand_growth", None, "normal", "todo", form.get("due_date", ""), "brand_growth", brand, user["id"], now, now))
                ids.append(cur.lastrowid)
        self.log_action(user, "brand_task_generated", "brand_growth", None, brand)
        return {"ok": True, "task_ids": ids}, 200

    def api_brand_growth_get(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_manage_brand_growth(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        with db() as conn:
            if path == "/api/brand-growth":
                return self.json_out({"ok": True, "brands": self.brand_growth_brands(), "roles": self.brand_roles(), "empty_message": self.cockpit_data()["empty_message"]})
            table_map = {"/api/brand-growth/diagnosis": ("brand_diagnoses", "diagnosis"), "/api/brand-growth/strategies": ("brand_strategies", "strategies"), "/api/brand-growth/portfolio": ("product_portfolios", "portfolio"), "/api/brand-growth/pricing": ("pricing_strategies", "pricing"), "/api/brand-growth/supplier-risk": ("supplier_brand_risks", "supplier_risk")}
            if path in table_map:
                table, key = table_map[path]
                rows = conn.execute(f"select * from {table} order by updated_at desc limit 100").fetchall()
                return self.json_out({"ok": True, key: [row_dict(r) for r in rows]})
            if path == "/api/brand-growth/inventory-matrix":
                return self.json_out({"ok": True, "matrix": [U(r"\u9ad8\u9500\u552e+\u9ad8\u6bdb\u5229=\u6838\u5fc3\u4fdd\u7559"), U(r"\u9ad8\u5e93\u5b58+\u4f4e\u6bdb\u5229=\u9ad8\u98ce\u9669")], "message": self.cockpit_data()["empty_message"]})
        return self.json_out({"ok": False, "message": "unknown brand growth api"}, code=404)

    def api_brand_growth_post(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_manage_brand_growth(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        form = self.form()
        now = ts()
        if path == "/api/brand-growth/diagnosis":
            payload = self.brand_diagnosis_payload(form.get("brand_id", ""))
            with db() as conn:
                cur = conn.execute("insert into brand_diagnoses(diagnosis_id,brand_id,sales_status,margin_status,inventory_status,discount_status,supplier_status,market_status,customer_feedback,key_problems,opportunities,ai_suggestions,data_sources,status,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("BD-" + uuid.uuid4().hex[:10], payload["brand_id"], payload["sales_status"], payload["margin_status"], payload["inventory_status"], payload["discount_status"], payload["supplier_status"], payload["market_status"], payload["customer_feedback"], json.dumps(payload["key_problems"], ensure_ascii=False), json.dumps(payload["opportunities"], ensure_ascii=False), json.dumps(payload["ai_suggestions"], ensure_ascii=False), json.dumps(payload["data_sources"], ensure_ascii=False), "draft", user["id"], now, now))
            return self.json_out({"ok": True, "diagnosis_id": cur.lastrowid, "diagnosis": payload})
        if path == "/api/brand-growth/pricing/calculate":
            return self.json_out({"ok": True, "result": self.calculate_osprey_payload(form)})
        if path == "/api/brand-growth/create-tasks":
            result, code = self.brand_growth_create_tasks(user)
            return self.json_out(result, code=code)
        if path in ("/api/brand-growth/strategies", "/api/brand-growth/portfolio", "/api/brand-growth/pricing"):
            return self.json_out({"ok": False, "message": U(r"\u8bf7\u4f7f\u7528\u9875\u9762\u8868\u5355\u6216\u540e\u7eed\u5b8c\u6574 API \u586b\u5199\u8be6\u7ec6\u5b57\u6bb5\u3002")}, code=501)
        return self.json_out({"ok": False, "message": "unknown brand growth api"}, code=404)

    def api_brand_growth_put(self, user, path):
        return self.json_out({"ok": False, "message": "brand growth update endpoint reserved"}, code=501)

    def can_manage_inventory_decision(self, user):
        return bool(user and user["role"] in ("boss", "admin", "purchasing", "finance", "store_manager"))

    def inventory_decision_empty(self):
        return self.cockpit_data()["empty_message"]

    def inventory_decision_center(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_manage_inventory_decision(user):
            return self.dashboard(user)
        with db() as conn:
            risks = conn.execute("select * from inventory_decision_risks order by updated_at desc limit 40").fetchall()
            replenishment = conn.execute("select * from replenishment_suggestions order by created_at desc limit 30").fetchall()
            transfers = conn.execute("select * from transfer_suggestions order by created_at desc limit 30").fetchall()
            markdowns = conn.execute("select * from markdown_suggestions order by created_at desc limit 30").fetchall()
            futures = conn.execute("select * from future_orders order by created_at desc limit 30").fetchall()
            purchases = conn.execute("select * from purchasing_plans order by created_at desc limit 30").fetchall()
        risk_items = [r["brand_id"] + " · " + (r["risk_type"] or "") + " · " + (r["risk_level"] or "") for r in risks] or [self.inventory_decision_empty()]
        replen_items = [r["store_id"] + " · " + r["brand_id"] + " · " + (r["suggested_quantity"] or "") + " · " + r["status"] for r in replenishment] or [U(r"\u6682\u65e0\u8865\u8d27\u5efa\u8bae\u3002")]
        transfer_items = [t["from_store_id"] + " -> " + t["to_store_id"] + " · " + t["brand_id"] + " · " + t["status"] for t in transfers] or [U(r"\u6682\u65e0\u8c03\u8d27\u5efa\u8bae\u3002")]
        markdown_items = [m["brand_id"] + " · " + (m["suggested_discount"] or "") + " · " + m["approval_status"] for m in markdowns] or [U(r"\u6682\u65e0\u964d\u4ef7/\u6e05\u8d27\u5efa\u8bae\u3002")]
        future_items = [f["brand_id"] + " · " + (f["season"] or "") + " · " + f["decision_status"] for f in futures] or [U(r"\u6682\u65e0\u671f\u8d27\u51b3\u7b56\u8bb0\u5f55\u3002")]
        purchase_items = [p["title"] + " · " + (p["brand_id"] or "") + " · " + p["status"] for p in purchases] or [U(r"\u6682\u65e0\u91c7\u8d2d\u8ba1\u5212\u3002")]
        body = f"""
<div class="panel"><h2>{U(r'\u5e93\u5b58\u91c7\u8d2d\u51b3\u7b56\u5f15\u64ce')}</h2><p class="small">{U(r'\u7528\u4e8e\u8865\u8d27\u3001\u8c03\u8d27\u3001\u964d\u4ef7\u3001\u6e05\u8d27\u3001\u671f\u8d27\u548c\u91c7\u8d2d\u51b3\u7b56\u3002\u4e0d\u81ea\u52a8\u751f\u6210\u91c7\u8d2d\u5355\u6216\u6539\u4ef7\u3002')}</p></div>
<div class="grid">
  {self.card(U(r'\u5e93\u5b58\u98ce\u9669'), U(r'\u9ad8\u5e93\u5b58\u3001\u6ede\u9500\u3001\u4f4e\u6bdb\u5229\u3001\u5b63\u8282\u3001\u73b0\u91d1\u6d41\u548c\u4f9b\u5e94\u5546\u98ce\u9669\u3002'), '#risk-form', 'btn', True)}
  {self.card(U(r'\u8865\u8d27\u5efa\u8bae'), U(r'\u6839\u636e\u95e8\u5e97\u3001\u54c1\u724c\u3001\u4ea7\u54c1\u548c\u9500\u552e\u901f\u5ea6\u5efa\u7acb\u8865\u8d27\u8349\u6848\u3002'), '#replen-form', 'btn green', True)}
  {self.card(U(r'Osprey \u5e93\u5b58\u51b3\u7b56'), U(r'\u671f\u8d27\u3001\u8fd4\u70b9\u3001\u6298\u6263\u3001\u73b0\u91d1\u5360\u7528\u548c\u4ef7\u683c\u98ce\u9669\u4e13\u9898\u3002'), '/brands/osprey-inventory-decision', 'btn orange', True)}
</div>
<div class="split"><div class="panel"><h2>{U(r'\u5e93\u5b58\u98ce\u9669')}</h2>{self.bullets(risk_items)}</div><div class="panel"><h2>{U(r'\u8865\u8d27\u5efa\u8bae')}</h2>{self.bullets(replen_items)}</div></div>
<div class="split"><div class="panel"><h2>{U(r'\u8c03\u8d27\u5efa\u8bae')}</h2>{self.bullets(transfer_items)}</div><div class="panel"><h2>{U(r'\u964d\u4ef7\u6e05\u8d27')}</h2>{self.bullets(markdown_items)}</div></div>
<div class="split"><div class="panel"><h2>{U(r'\u671f\u8d27\u51b3\u7b56')}</h2>{self.bullets(future_items)}</div><div class="panel"><h2>{U(r'\u91c7\u8d2d\u8ba1\u5212')}</h2>{self.bullets(purchase_items)}</div></div>
<div class="split">
  <div id="risk-form" class="panel form"><h2>{U(r'\u65b0\u5efa\u5e93\u5b58\u98ce\u9669')}</h2><form method="post" action="/inventory-decision/risks/save"><label>{U(r'\u54c1\u724c')}</label><input name="brand_id"><label>{U(r'\u4ea7\u54c1')}</label><input name="product_id"><label>{T['store']}</label><input name="store_id"><label>{U(r'\u98ce\u9669\u7c7b\u578b')}</label><input name="risk_type" placeholder="high_inventory / slow_moving / price_risk"><label>{U(r'\u5efa\u8bae')}</label><textarea name="recommendation"></textarea><p><button>{U(r'\u4fdd\u5b58\u98ce\u9669')}</button></p></form></div>
  <div id="replen-form" class="panel form"><h2>{U(r'\u65b0\u5efa\u8865\u8d27\u5efa\u8bae')}</h2><form method="post" action="/inventory-decision/replenishment/save"><label>{T['store']}</label><input name="store_id"><label>{U(r'\u54c1\u724c')}</label><input name="brand_id"><label>{U(r'\u4ea7\u54c1')}</label><input name="product_id"><label>{U(r'\u5efa\u8bae\u6570\u91cf')}</label><input name="suggested_quantity"><label>{U(r'\u539f\u56e0')}</label><textarea name="reason"></textarea><p><button>{U(r'\u4fdd\u5b58\u8865\u8d27\u5efa\u8bae')}</button></p></form></div>
</div>"""
        self.out(layout(U(r"\u5e93\u5b58\u91c7\u8d2d\u51b3\u7b56"), body, user=user, wide=True))

    def inventory_insert(self, table, cols, values, action, target_type):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        if not self.can_manage_inventory_decision(user):
            return self.redir("/")
        form = self.form()
        vals = [values.get(c, form.get(c, "")) for c in cols]
        with db() as conn:
            cur = conn.execute(f"insert into {table}({','.join(cols)}) values({','.join('?' for _ in cols)})", vals)
        self.log_action(user, action, target_type, cur.lastrowid, "")
        return self.redir("/inventory-decision")

    def inventory_risk_save(self):
        now = ts()
        return self.inventory_insert("inventory_decision_risks", ["inventory_risk_id","brand_id","product_id","store_id","risk_type","risk_level","recommendation","status","created_at","updated_at"], {"inventory_risk_id":"IR-"+uuid.uuid4().hex[:10],"risk_level":"unknown","status":"draft","created_at":now,"updated_at":now}, "inventory_risk_created", "inventory_risk")

    def replenishment_save(self):
        now = ts()
        return self.inventory_insert("replenishment_suggestions", ["suggestion_id","store_id","brand_id","product_id","reason","suggested_quantity","priority","status","created_at"], {"suggestion_id":"REP-"+uuid.uuid4().hex[:10],"priority":"normal","status":"draft","created_at":now}, "replenishment_created", "replenishment")

    def transfer_suggestion_save(self):
        now = ts()
        return self.inventory_insert("transfer_suggestions", ["transfer_id","from_store_id","to_store_id","brand_id","product_id","quantity","reason","urgency","status","created_at"], {"transfer_id":"TR-"+uuid.uuid4().hex[:10],"urgency":"normal","status":"draft","created_at":now}, "transfer_created", "transfer")

    def markdown_suggestion_save(self):
        now = ts()
        return self.inventory_insert("markdown_suggestions", ["markdown_id","brand_id","product_id","store_id","current_discount","suggested_discount","reason","expected_result","risk_level","approval_status","created_at"], {"markdown_id":"MD-"+uuid.uuid4().hex[:10],"risk_level":"review","approval_status":"pending_review","created_at":now}, "markdown_created", "markdown")

    def future_order_save(self):
        now = ts()
        return self.inventory_insert("future_orders", ["future_order_id","supplier_id","brand_id","season","order_amount","deposit_amount","deposit_rate","expected_delivery_date","cancellation_risk","pricing_risk","rebate_assumption","status","decision_status","created_at"], {"future_order_id":"FO-"+uuid.uuid4().hex[:10],"status":"draft","decision_status":"pending","created_at":now}, "future_order_created", "future_order")

    def purchasing_plan_save(self):
        user = self.current_user()
        now = ts()
        return self.inventory_insert("purchasing_plans", ["purchasing_plan_id","title","supplier_id","brand_id","season","budget","planned_items","expected_margin","risk_assessment","status","created_by","created_at"], {"purchasing_plan_id":"PP-"+uuid.uuid4().hex[:10],"status":"draft","created_by":user["id"] if user else None,"created_at":now}, "purchasing_plan_created", "purchasing_plan")

    def osprey_inventory_decision(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_manage_inventory_decision(user):
            return self.dashboard(user)
        body = f"""<div class="panel"><h2>Osprey {U(r'\u5e93\u5b58\u51b3\u7b56')}</h2><p class="small">{U(r'\u4e13\u9879\u5904\u7406 Osprey \u671f\u8d27\u3001\u5e93\u5b58\u3001\u6298\u6263\u3001\u8fd4\u70b9\u3001\u73b0\u91d1\u5360\u7528\u548c\u4ef7\u683c\u4f53\u7cfb\u98ce\u9669\u3002\u4e0d\u586b\u771f\u5b9e\u6570\u636e\u65f6\u4e0d\u4ea7\u751f\u7ed3\u8bba\u3002')}</p></div>
<div class="split"><div class="panel"><h2>{U(r'\u51b3\u7b56\u6846\u67b6')}</h2>{self.bullets([U(r'\u5f53\u524d\u5e93\u5b58\uff1a\u7b49\u5f85 SAP \u660e\u7ec6'), U(r'\u671f\u8d27\u98ce\u9669\uff1a\u8ba2\u91d1\u3001\u63d0\u8d27\u3001\u53d6\u6d88\u53ef\u80fd\u6027'), U(r'\u6298\u6263\u573a\u666f\uff1a59 / 60 / 62 / 65 \u6298'), U(r'\u8fd4\u70b9\u4f9d\u8d56\uff1a\u4e0d\u672a\u5ba1\u6838\u5373\u8ba4\u5b9a'), U(r'\u73b0\u91d1\u5360\u7528\uff1a\u7b49\u5f85\u8d22\u52a1\u6570\u636e')])}</div><div class="panel"><h2>{U(r'\u591a\u667a\u80fd\u4f53\u5efa\u8bae')}</h2>{self.empty_state(U(r'\u5df2\u9884\u7559 AI CEO / CFO / \u5e93\u5b58 / \u54c1\u724c / \u7814\u7a76\u5458\u534f\u540c\u5206\u6790\uff0c\u9700\u771f\u5b9e\u6570\u636e\u540e\u8f93\u51fa\u3002'))}</div></div>
<div class="panel"><h2>{U(r'\u4efb\u52a1\u751f\u6210')}</h2><form method="post" action="/api/inventory-decision/create-task"><input type="hidden" name="brand_id" value="Osprey"><label>{U(r'\u4efb\u52a1\u6807\u9898')}</label><input name="title" value="Osprey \u5e93\u5b58\u4e0e\u671f\u8d27\u98ce\u9669\u590d\u6838"><p><button>{U(r'\u751f\u6210\u5f85\u529e\u4efb\u52a1')}</button></p></form></div>"""
        self.out(layout("Osprey " + U(r"\u5e93\u5b58\u51b3\u7b56"), body, user=user, wide=True))

    def api_inventory_decision_get(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_manage_inventory_decision(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        with db() as conn:
            table_map = {"/api/inventory-decision/risks": ("inventory_decision_risks","risks"), "/api/inventory-decision/replenishment": ("replenishment_suggestions","replenishment"), "/api/inventory-decision/transfers": ("transfer_suggestions","transfers"), "/api/inventory-decision/markdowns": ("markdown_suggestions","markdowns"), "/api/inventory-decision/future-orders": ("future_orders","future_orders"), "/api/inventory-decision/purchasing-plans": ("purchasing_plans","purchasing_plans")}
            if path == "/api/inventory-decision":
                return self.json_out({"ok": True, "empty_message": self.inventory_decision_empty(), "sections": list(table_map.keys())})
            if path in table_map:
                table, key = table_map[path]
                rows = conn.execute(f"select * from {table} order by id desc limit 100").fetchall()
                return self.json_out({"ok": True, key: [row_dict(r) for r in rows]})
            if path == "/api/inventory-decision/cash-occupation":
                return self.json_out({"ok": True, "data": self.cockpit_data()["metrics"], "message": self.inventory_decision_empty()})
            if path == "/api/inventory-decision/osprey":
                return self.json_out({"ok": True, "template": "osprey inventory decision", "message": U(r"\u4ec5\u4f5c\u51b3\u7b56\u6846\u67b6\uff0c\u4e0d\u7f16\u9020 Osprey \u771f\u5b9e\u5e93\u5b58\u6216\u671f\u8d27\u6570\u636e\u3002")})
        return self.json_out({"ok": False, "message": "unknown inventory decision api"}, code=404)

    def api_inventory_decision_post(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_manage_inventory_decision(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        form = self.form()
        now = ts()
        if path == "/api/inventory-decision/create-task":
            with db() as conn:
                cur = conn.execute("insert into tasks(task_id,title,description,owner,related_object_type,related_object_id,priority,status,due_date,source_type,source_id,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("TASK-" + uuid.uuid4().hex[:10], form.get("title", U(r"\u5e93\u5b58\u51b3\u7b56\u590d\u6838")), form.get("description", ""), form.get("owner", user["name"]), "inventory_decision", None, "high", "todo", form.get("due_date", ""), "inventory_decision", form.get("brand_id", ""), user["id"], now, now))
            self.log_action(user, "inventory_task_generated", "task", cur.lastrowid, form.get("title", ""))
            return self.json_out({"ok": True, "task_id": cur.lastrowid})
        return self.json_out({"ok": False, "message": "inventory decision write endpoint reserved"}, code=501)

    def can_manage_content(self, user):
        return bool(user and user["role"] in ("boss", "admin", "store_manager", "employee", "purchasing"))

    def can_review_content(self, user):
        return bool(user and user["role"] in ("boss", "admin", "store_manager"))

    def content_platform_rules(self):
        return {
            "wechat_official": {"tone": U(r"\u5b8c\u6574\u3001\u4e13\u4e1a\u3001\u6545\u4e8b\u5316"), "length_limit": "1200-2500", "media": U(r"\u9996\u56fe\u3001\u4ea7\u54c1\u56fe\u3001\u95e8\u5e97\u56fe")},
            "xiaohongshu": {"tone": U(r"\u771f\u5b9e\u3001\u79cd\u8349\u3001\u77ed\u53e5\u3001\u6807\u7b7e"), "length_limit": "300-800", "media": U(r"6-9 \u5f20\u771f\u5b9e\u56fe\u7247")},
            "douyin": {"tone": U(r"\u77ed\u89c6\u9891\u811a\u672c\u3001\u5f00\u5934 3 \u79d2\u94a9\u5b50"), "length_limit": "15-60s", "media": U(r"\u7ad6\u7248\u89c6\u9891")},
            "wechat_channels": {"tone": U(r"\u54c1\u724c\u611f\u3001\u6d3b\u52a8\u611f\u3001\u4fe1\u4efb\u611f"), "length_limit": "30-90s", "media": U(r"\u7ad6\u7248\u89c6\u9891")},
            "website": {"tone": U(r"\u6b63\u5f0f\u3001\u54c1\u724c\u5316\u3001SEO \u53cb\u597d"), "length_limit": "800-2000", "media": U(r"\u4ea7\u54c1\u56fe\u3001\u54c1\u724c\u56fe")},
            "instagram": {"tone": U(r"\u82f1\u6587\u6216\u53cc\u8bed\u9884\u7559"), "length_limit": "150-500", "media": U(r"\u65b9\u56fe\u6216\u7ad6\u56fe")},
            "tiktok": {"tone": U(r"\u82f1\u6587\u6216\u53cc\u8bed\u77ed\u89c6\u9891\u9884\u7559"), "length_limit": "15-60s", "media": U(r"\u7ad6\u7248\u89c6\u9891")},
        }

    def content_skeleton(self, title, content_type, topic, platforms):
        title = title or U(r"AI \u5185\u5bb9\u8349\u7a3f")
        sections = [
            U(r"\u9009\u9898\uff1a") + (topic or title),
            U(r"\u6838\u5fc3\u4fe1\u606f\uff1a\u7b49\u5f85\u63a5\u5165\u771f\u5b9e\u4ea7\u54c1\u3001\u54c1\u724c\u6216\u95e8\u5e97\u8d44\u6599\u3002"),
            U(r"\u5185\u5bb9\u7ed3\u6784\uff1a\u5f00\u5934\u5438\u5f15 -> \u771f\u5b9e\u4fe1\u606f -> \u573a\u666f\u4ef7\u503c -> \u884c\u52a8\u5efa\u8bae\u3002"),
            U(r"\u5ba1\u6838\u63d0\u9192\uff1a\u53d1\u5e03\u524d\u5fc5\u987b\u6838\u5bf9\u4ef7\u683c\u3001\u5e93\u5b58\u3001\u6d3b\u52a8\u3001\u54c1\u724c\u6743\u76ca\u548c\u4ea7\u54c1\u53c2\u6570\u3002"),
        ]
        if "osprey" in (topic or title).lower():
            sections += [U(r"Osprey \u6c9f\u901a\u6a21\u677f\uff1a\u6e05\u8d27\u4f46\u4e0d\u4f24\u54c1\u724c\uff0c\u4e0d\u505a\u865a\u5047\u627f\u8bfa\u3002")]
        if "vafox" in (topic or title).lower():
            sections += [U(r"VAFOX \u6a21\u677f\uff1a\u89c1\u5c71\u89c1\u5df1\u3001\u54c1\u724c\u6545\u4e8b\u3001\u95e8\u5e97\u4f53\u9a8c\u3002")]
        return "\n".join(sections), U(r"AI \u5185\u5bb9\u751f\u6210\u6846\u67b6\u5df2\u5efa\u7acb\uff0c\u7b49\u5f85\u63a5\u5165\u5927\u6a21\u578b API\u3002")

    def create_content_versions(self, conn, content_id, title, body, platforms):
        now = ts()
        rules = self.content_platform_rules()
        created = []
        for platform in csv_values(platforms) or ["wechat_official", "xiaohongshu", "douyin"]:
            rule = rules.get(platform, {"tone": U(r"\u901a\u7528\u8349\u7a3f"), "length_limit": "", "media": ""})
            cur = conn.execute(
                "insert into content_platform_versions(version_id,content_id,platform,title,body,hashtags,media_requirements,length_limit,tone,status,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?)",
                ("VER-" + uuid.uuid4().hex[:10], content_id, platform, title, body, "#VAFOX #FireFox", rule["media"], rule["length_limit"], rule["tone"], "draft", now, now),
            )
            created.append(cur.lastrowid)
        return created

    def content_center(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_manage_content(user):
            return self.dashboard(user)
        with db() as conn:
            drafts = conn.execute("select * from content_drafts order by updated_at desc limit 80").fetchall()
            campaigns = conn.execute("select * from content_campaigns order by updated_at desc limit 30").fetchall()
            queue = conn.execute("select * from content_publish_queue order by created_at desc limit 20").fetchall()
        counts = {status: len([d for d in drafts if d["status"] == status]) for status in ("draft", "pending_review", "approved", "scheduled", "published")}
        cards = ""
        for d in drafts:
            cards += "<div class='card'><div><h2>{}</h2><p>{}</p><p class='small'>{} 路 {} 路 {}</p></div><div class='inline'><form method='post' action='/api/content/{}/generate'><button>{}</button></form><form method='post' action='/api/content/{}/submit-review'><button class='orange'>{}</button></form><form method='post' action='/api/content/{}/approve'><button class='green'>{}</button></form></div></div>".format(
                esc(d["title"]), esc(summarize_text(d["summary"] or d["body"], 130)), esc(d["content_type"]), esc(d["target_platforms"]), esc(d["status"]), d["id"], U(r"\u751f\u6210"), d["id"], U(r"\u63d0\u5ba1"), d["id"], U(r"\u901a\u8fc7")
            )
        if not cards:
            cards = "<div class='panel'>{}</div>".format(self.empty_state(U(r"\u6682\u65e0\u5185\u5bb9\u8349\u7a3f\uff0c\u53ef\u5148\u4ece\u54c1\u724c\u3001\u4ea7\u54c1\u3001\u95e8\u5e97\u6545\u4e8b\u521b\u5efa\u3002")))
        campaign_items = [c["campaign_name"] + " 路 " + (c["campaign_type"] or "") + " 路 " + c["status"] for c in campaigns] or [U(r"\u6682\u65e0\u6d3b\u52a8\u3002")]
        queue_items = [q["platform"] + " 路 " + q["status"] for q in queue] or [U(r"\u53d1\u5e03\u63a5\u53e3\u9884\u7559\uff0c\u5f53\u524d\u4ec5\u652f\u6301\u8349\u7a3f\u4e0e\u5bfc\u51fa\u3002")]
        body = f"""
<div class="panel">
  <h2>{U(r'\u5185\u5bb9\u53d1\u5e03\u5f15\u64ce')}</h2>
  <p class="small">{U(r'\u628a\u77e5\u8bc6\u3001\u54c1\u724c\u3001\u4ea7\u54c1\u3001\u95e8\u5e97\u6545\u4e8b\u548c AI \u5206\u6790\u8f6c\u6210\u591a\u5e73\u53f0\u5185\u5bb9\u8349\u7a3f\u3002\u6682\u4e0d\u81ea\u52a8\u53d1\u5e03\u3002')}</p>
  <div class="metrics">{self.metric(U(r'\u8349\u7a3f'), counts.get('draft',0), U(r'\u53ef\u7f16\u8f91'))}{self.metric(U(r'\u5f85\u5ba1'), counts.get('pending_review',0), U(r'\u9700\u5ba1\u6838'))}{self.metric(U(r'\u5df2\u901a\u8fc7'), counts.get('approved',0), U(r'\u53ef\u6392\u671f'))}{self.metric(U(r'\u5df2\u6392\u671f'), counts.get('scheduled',0), U(r'\u5f85\u53d1\u5e03'))}{self.metric(U(r'\u5df2\u53d1\u5e03'), counts.get('published',0), U(r'\u624b\u52a8\u8bb0\u5f55'))}</div>
</div>
<div class="split">
  <div class="panel form">
    <h2>{U(r'\u65b0\u5efa\u5185\u5bb9\u8349\u7a3f')}</h2>
    <form method="post" action="/content/save">
      <label>{U(r'\u6807\u9898')}</label><input name="title" required>
      <label>{U(r'\u5185\u5bb9\u7c7b\u578b')}</label><select name="content_type"><option value="article">article</option><option value="short_video_script">short_video_script</option><option value="xiaohongshu_note">xiaohongshu_note</option><option value="product_story">product_story</option><option value="store_story">store_story</option><option value="campaign_post">campaign_post</option><option value="brand_introduction">brand_introduction</option></select>
      <label>{U(r'\u9009\u9898')}</label><input name="topic">
      <label>{U(r'\u76ee\u6807\u5e73\u53f0')}</label><input name="target_platforms" value="wechat_official,xiaohongshu,douyin">
      <label>{U(r'\u4eba\u5de5\u8f93\u5165')}</label><textarea name="body"></textarea>
      <p><button>{U(r'\u4fdd\u5b58\u5e76\u751f\u6210\u5e73\u53f0\u7248\u672c')}</button></p>
    </form>
  </div>
  <div class="panel"><h2>{U(r'\u5185\u5bb9\u65e5\u5386')}</h2>{self.bullets([U(r'\u4eca\u5929\uff1a\u68c0\u67e5\u5f85\u5ba1\u6838\u8349\u7a3f'), U(r'\u672c\u5468\uff1a\u5b89\u6392\u54c1\u724c\u548c\u95e8\u5e97\u5185\u5bb9'), U(r'\u672c\u6708\uff1a\u56f4\u7ed5\u6d3b\u52a8\u548c\u65b0\u54c1\u505a\u6392\u671f')])}</div>
</div>
<div class="panel"><h2>{U(r'\u5185\u5bb9\u8349\u7a3f')}</h2><div class="grid">{cards}</div></div>
<div class="split"><div class="panel"><h2>{U(r'\u6d3b\u52a8')}</h2>{self.bullets(campaign_items)}</div><div class="panel"><h2>{U(r'\u53d1\u5e03\u961f\u5217')}</h2>{self.bullets(queue_items)}</div></div>
<div class="panel"><h2>{U(r'\u4e13\u7528\u6a21\u677f')}</h2>{self.bullets([U(r'Osprey \u6c9f\u901a\u6a21\u677f\uff1a\u987e\u5ba2\u8bdd\u672f\u3001\u95e8\u5e97\u8bdd\u672f\u3001\u5c0f\u7ea2\u4e66\u65b9\u5411\u3001\u4f1a\u5458\u6d3b\u52a8'), U(r'VAFOX \u6a21\u677f\uff1a\u54c1\u724c\u6545\u4e8b\u3001\u89c1\u5c71\u89c1\u5df1\u7406\u5ff5\u3001\u5b98\u7f51\u4ecb\u7ecd\u3001\u89c6\u9891\u53f7\u811a\u672c')])}</div>"""
        self.out(layout(U(r"\u5185\u5bb9\u53d1\u5e03\u5f15\u64ce"), body, user=user, wide=True))

    def content_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        if not self.can_manage_content(user):
            return self.redir("/")
        form = self.form()
        title = form.get("title", "").strip()
        if not title:
            return self.redir("/content")
        body, summary = self.content_skeleton(title, form.get("content_type", "article"), form.get("topic", ""), form.get("target_platforms", ""))
        if form.get("body", "").strip():
            body = form.get("body", "").strip() + "\n\n" + body
        now = ts()
        with db() as conn:
            cur = conn.execute(
                "insert into content_drafts(content_id,title,content_type,topic,body,summary,target_platforms,status,related_object_type,related_object_id,source_type,source_id,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("CNT-" + uuid.uuid4().hex[:10], title, form.get("content_type", "article"), form.get("topic", ""), body, summary, form.get("target_platforms", ""), "ai_generated", form.get("related_object_type", ""), int(form.get("related_object_id")) if str(form.get("related_object_id", "")).isdigit() else None, form.get("source_type", "manual"), form.get("source_id", ""), user["id"], now, now),
            )
            self.create_content_versions(conn, cur.lastrowid, title, body, form.get("target_platforms", ""))
        self.log_action(user, "content_created", "content", cur.lastrowid, title)
        return self.redir("/content")

    def content_to_export(self, row, fmt="markdown"):
        if fmt == "html":
            return {"format": "html", "content": "<!doctype html><meta charset='utf-8'><h1>{}</h1><p>{}</p><pre>{}</pre>".format(esc(row["title"]), esc(row["summary"]), esc(row["body"]))}
        if fmt == "text":
            return {"format": "text", "content": row["title"] + "\n\n" + (row["body"] or "")}
        return {"format": "markdown", "content": "# {}\n\n{}\n\n{}".format(row["title"], row["summary"] or "", row["body"] or "")}

    def api_content_get(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_manage_content(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        with db() as conn:
            if path == "/api/content":
                rows = conn.execute("select * from content_drafts order by updated_at desc limit 100").fetchall()
                return self.json_out({"ok": True, "content": [row_dict(r) for r in rows]})
            m = re.match(r"^/api/content/(\d+)$", path)
            if m:
                row = conn.execute("select * from content_drafts where id=?", (m.group(1),)).fetchone()
                versions = conn.execute("select * from content_platform_versions where content_id=? order by platform", (m.group(1),)).fetchall()
                return self.json_out({"ok": bool(row), "content": row_dict(row), "versions": [row_dict(v) for v in versions]} if row else {"ok": False, "message": "not found"}, code=200 if row else 404)
            if path == "/api/content/calendar":
                rows = conn.execute("select * from content_drafts where scheduled_at is not null order by scheduled_at limit 100").fetchall()
                return self.json_out({"ok": True, "calendar": [row_dict(r) for r in rows]})
            if path == "/api/content/campaigns":
                rows = conn.execute("select * from content_campaigns order by updated_at desc limit 100").fetchall()
                return self.json_out({"ok": True, "campaigns": [row_dict(r) for r in rows]})
            if path == "/api/content/platform-versions":
                rows = conn.execute("select * from content_platform_versions order by updated_at desc limit 100").fetchall()
                return self.json_out({"ok": True, "versions": [row_dict(r) for r in rows]})
            if path == "/api/content/publish-queue":
                rows = conn.execute("select * from content_publish_queue order by created_at desc limit 100").fetchall()
                return self.json_out({"ok": True, "queue": [row_dict(r) for r in rows], "message": U(r"\u53d1\u5e03\u63a5\u53e3\u9884\u7559\uff0c\u5f53\u524d\u4ec5\u652f\u6301\u8349\u7a3f\u4e0e\u5bfc\u51fa\u3002")})
        return self.json_out({"ok": False, "message": "unknown content api"}, code=404)

    def api_content_post(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_manage_content(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        form = self.form()
        now = ts()
        if path == "/api/content":
            title = form.get("title", U(r"AI \u5185\u5bb9\u8349\u7a3f"))
            body, summary = self.content_skeleton(title, form.get("content_type", "article"), form.get("topic", ""), form.get("target_platforms", ""))
            with db() as conn:
                cur = conn.execute("insert into content_drafts(content_id,title,content_type,topic,body,summary,target_platforms,status,source_type,source_id,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?)", ("CNT-" + uuid.uuid4().hex[:10], title, form.get("content_type", "article"), form.get("topic", ""), body, summary, form.get("target_platforms", ""), "ai_generated", form.get("source_type", "api"), form.get("source_id", ""), user["id"], now, now))
                self.create_content_versions(conn, cur.lastrowid, title, body, form.get("target_platforms", ""))
            self.log_action(user, "content_created", "content", cur.lastrowid, title)
            return self.json_out({"ok": True, "content_id": cur.lastrowid})
        m = re.match(r"^/api/content/(\d+)/(generate|submit-review|approve|reject|archive|schedule)$", path)
        if m:
            cid, action = m.group(1), m.group(2)
            with db() as conn:
                row = conn.execute("select * from content_drafts where id=?", (cid,)).fetchone()
                if not row:
                    return self.json_out({"ok": False, "message": "not found"}, code=404)
                if action == "generate":
                    body, summary = self.content_skeleton(row["title"], row["content_type"], row["topic"], row["target_platforms"])
                    conn.execute("update content_drafts set body=?, summary=?, status='ai_generated', updated_at=? where id=?", (body, summary, now, cid))
                    self.create_content_versions(conn, cid, row["title"], body, row["target_platforms"])
                    self.log_action(user, "content_generated", "content", cid, row["title"])
                    return self.json_out({"ok": True, "body": body, "summary": summary})
                status_map = {"submit-review": "pending_review", "approve": "approved", "reject": "rejected", "archive": "archived", "schedule": "scheduled"}
                if action in ("approve", "reject") and not self.can_review_content(user):
                    return self.json_out({"ok": False, "message": "no permission"}, code=403)
                status = status_map[action]
                conn.execute("update content_drafts set status=?, reviewed_by=?, reviewed_at=?, review_notes=?, compliance_status=?, scheduled_at=coalesce(?,scheduled_at), updated_at=? where id=?", (status, user["id"] if action in ("approve", "reject") else row["reviewed_by"], now if action in ("approve", "reject") else row["reviewed_at"], form.get("review_notes", ""), form.get("compliance_status", "pending"), int(form.get("scheduled_at")) if str(form.get("scheduled_at", "")).isdigit() else None, now, cid))
            self.log_action(user, "content_" + action, "content", cid, "")
            return self.json_out({"ok": True, "status": status})
        if path == "/api/content/campaigns":
            with db() as conn:
                cur = conn.execute("insert into content_campaigns(campaign_id,campaign_name,campaign_type,start_date,end_date,target_stores,target_brands,target_products,goal,budget,status,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?)", ("CAM-" + uuid.uuid4().hex[:10], form.get("campaign_name", U(r"\u672a\u547d\u540d\u6d3b\u52a8")), form.get("campaign_type", ""), form.get("start_date", ""), form.get("end_date", ""), form.get("target_stores", ""), form.get("target_brands", ""), form.get("target_products", ""), form.get("goal", ""), form.get("budget", ""), form.get("status", "draft"), now, now))
            self.log_action(user, "campaign_created", "campaign", cur.lastrowid, form.get("campaign_name", ""))
            return self.json_out({"ok": True, "campaign_id": cur.lastrowid})
        if path == "/api/content/platform-versions":
            with db() as conn:
                cur = conn.execute("insert into content_platform_versions(version_id,content_id,platform,title,body,hashtags,media_requirements,length_limit,tone,status,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?)", ("VER-" + uuid.uuid4().hex[:10], int(form.get("content_id")) if str(form.get("content_id", "")).isdigit() else 0, form.get("platform", "wechat_official"), form.get("title", ""), form.get("body", ""), form.get("hashtags", ""), form.get("media_requirements", ""), form.get("length_limit", ""), form.get("tone", ""), form.get("status", "draft"), now, now))
            return self.json_out({"ok": True, "version_id": cur.lastrowid})
        if path == "/api/content/export":
            with db() as conn:
                row = conn.execute("select * from content_drafts where id=?", (form.get("content_id", ""),)).fetchone()
            if not row:
                return self.json_out({"ok": False, "message": "not found"}, code=404)
            self.log_action(user, "content_exported", "content", row["id"], form.get("format", "markdown"))
            return self.json_out({"ok": True, "export": self.content_to_export(row, form.get("format", "markdown")), "copy_placeholder": True})
        return self.json_out({"ok": False, "message": "unknown content api"}, code=404)

    def api_content_put(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_manage_content(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        m = re.match(r"^/api/content/(\d+)$", path)
        if not m:
            return self.json_out({"ok": False, "message": "unknown content api"}, code=404)
        form = self.form()
        with db() as conn:
            conn.execute("update content_drafts set title=coalesce(?,title), topic=coalesce(?,topic), body=coalesce(?,body), summary=coalesce(?,summary), target_platforms=coalesce(?,target_platforms), status=coalesce(?,status), updated_at=? where id=?", (form.get("title"), form.get("topic"), form.get("body"), form.get("summary"), form.get("target_platforms"), form.get("status"), ts(), m.group(1)))
        self.log_action(user, "content_updated", "content", m.group(1), "")
        return self.json_out({"ok": True})

    def can_manage_reports(self, user):
        return bool(user and user["role"] in ("boss", "admin", "store_manager", "finance", "purchasing"))

    def seed_report_templates(self, conn):
        now = ts()
        templates = [
            ("TPL-CEO-DAILY", U(r"AI \u603b\u7ecf\u7406\u65e5\u62a5"), "ceo_daily", U(r"\u6bcf\u65e5\u7ecf\u8425\u6458\u8981\u3001\u98ce\u9669\u548c\u5efa\u8bae\u3002")),
            ("TPL-WEEKLY", U(r"\u5468\u5ea6\u7ecf\u8425\u62a5\u544a"), "weekly_business", U(r"\u9500\u552e\u3001\u6bdb\u5229\u3001\u5e93\u5b58\u3001\u4efb\u52a1\u548c\u98ce\u9669\u5468\u62a5\u3002")),
            ("TPL-MONTHLY", U(r"\u6708\u5ea6\u7ecf\u8425\u62a5\u544a"), "monthly_business", U(r"\u6708\u5ea6\u7ecf\u8425\u590d\u76d8\u548c\u4e0b\u6708\u8ba1\u5212\u3002")),
            ("TPL-STORE", U(r"\u95e8\u5e97\u62a5\u544a"), "store", U(r"\u95e8\u5e97\u9500\u552e\u3001\u4efb\u52a1\u3001\u4f1a\u5458\u548c\u5e93\u5b58\u63d0\u9192\u3002")),
            ("TPL-BRAND", U(r"\u54c1\u724c\u62a5\u544a"), "brand", U(r"\u54c1\u724c\u9500\u552e\u3001\u6bdb\u5229\u3001\u5e93\u5b58\u548c\u7b56\u7565\u3002")),
            ("TPL-INVENTORY", U(r"\u5e93\u5b58\u98ce\u9669\u62a5\u544a"), "inventory_risk", U(r"\u5e93\u5b58\u538b\u529b\u3001\u6ede\u9500\u548c\u6e05\u8d27\u5efa\u8bae\u3002")),
            ("TPL-RESEARCH", U(r"\u5916\u90e8\u7814\u7a76\u62a5\u544a"), "research", U(r"\u5916\u90e8\u7814\u7a76\u6458\u8981\u548c\u5185\u90e8\u5e94\u5bf9\u5efa\u8bae\u3002")),
            ("TPL-OSPREY", U(r"Osprey \u4ef7\u683c\u98ce\u9669\u62a5\u544a"), "osprey_pricing_risk", U(r"Osprey \u6298\u6263\u3001\u8fd4\u70b9\u3001\u6bdb\u5229\u548c\u54c1\u724c\u98ce\u9669\u4e13\u9879\u3002")),
            ("TPL-TASKS", U(r"\u4efb\u52a1\u6267\u884c\u62a5\u544a"), "task_execution", U(r"\u4efb\u52a1\u5b8c\u6210\u3001\u5ef6\u8bef\u3001\u98ce\u9669\u548c\u8d23\u4efb\u8ddf\u8fdb\u3002")),
        ]
        sections = [U(r"\u6458\u8981"), U(r"\u5173\u952e\u53d1\u73b0"), U(r"\u98ce\u9669"), U(r"\u673a\u4f1a"), U(r"\u5efa\u8bae\u52a8\u4f5c"), U(r"\u5f15\u7528\u6765\u6e90")]
        sources = ["sap_summary", "knowledge", "memory", "tasks", "graph"]
        for template_id, name, report_type, desc in templates:
            if not conn.execute("select id from report_templates where template_id=?", (template_id,)).fetchone():
                conn.execute(
                    "insert into report_templates(template_id,template_name,report_type,description,sections,required_sources,default_date_range,visibility,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?)",
                    (template_id, name, report_type, desc, json.dumps(sections, ensure_ascii=False), json.dumps(sources, ensure_ascii=False), "yesterday", "manager_only", now, now),
                )

    def report_draft_payload(self, user, report_type, title="", object_type="", object_id=None):
        cockpit = self.cockpit_data()
        m = cockpit["metrics"]
        limitations = []
        if not cockpit["has_data"]:
            limitations.append(cockpit["empty_message"])
        summary = U(r"\u8fd9\u662f AI \u751f\u6210\u7684\u62a5\u544a\u8349\u7a3f\uff0c\u9700\u8981\u4eba\u5de5\u5ba1\u6838\u540e\u624d\u80fd\u4f5c\u4e3a\u6b63\u5f0f\u62a5\u544a\u3002")
        findings = [
            U(r"\u6628\u65e5\u9500\u552e\uff1a") + money(m.get("yesterday_sales")),
            U(r"\u672c\u6708\u9500\u552e\uff1a") + money(m.get("month_sales")),
            U(r"\u5b8c\u6210\u7387\uff1a") + pct(m.get("completion_rate")),
            U(r"\u5e93\u5b58\u91d1\u989d\uff1a") + money(m.get("inventory_amount")),
        ]
        risks = cockpit["ai_suggestions"][:3] or limitations or [U(r"\u6682\u65e0\u53ef\u5f15\u7528\u98ce\u9669\uff0c\u7b49\u5f85 SAP B1 \u6216\u77e5\u8bc6\u6570\u636e\u8865\u5145\u3002")]
        actions = cockpit["todos"][:5] or [U(r"\u5efa\u8bae\u5148\u5b8c\u5584\u6570\u636e\u540c\u6b65\u548c\u4efb\u52a1\u8ddf\u8fdb\u3002")]
        return {
            "title": title or U(r"AI \u62a5\u544a\u8349\u7a3f"),
            "report_type": report_type,
            "summary": summary,
            "key_findings": findings,
            "risks": risks,
            "opportunities": [U(r"\u53ef\u7ed3\u5408\u77e5\u8bc6\u5e93\u3001\u8bb0\u5fc6\u548c\u56fe\u8c31\u7ee7\u7eed\u8865\u5f3a\u5206\u6790\u3002")],
            "recommended_actions": actions,
            "data_sources": ["sap_summary", "business_cockpit", "tasks", "memory", "knowledge_graph"],
            "cited_sap_records": [{"title": U(r"SAP B1 \u540c\u6b65\u6458\u8981"), "url": "/sap-sync"}],
            "limitations": limitations,
            "object_type": object_type,
            "object_id": object_id,
        }

    def report_center(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_manage_reports(user):
            return self.dashboard(user)
        with db() as conn:
            self.seed_report_templates(conn)
            templates = conn.execute("select * from report_templates order by id").fetchall()
            reports = conn.execute("select * from reports order by updated_at desc limit 80").fetchall()
            schedules = conn.execute("select * from report_schedules order by created_at desc limit 20").fetchall()
        template_options = "".join("<option value='{}'>{}</option>".format(esc(t["report_type"]), esc(t["template_name"])) for t in templates)
        report_cards = ""
        for r in reports:
            report_cards += "<div class='card'><div><h2>{}</h2><p>{}</p><p class='small'>{} 路 {} 路 {}</p></div><div class='inline'><form method='post' action='/api/reports/{}/generate'><button>{}</button></form><form method='post' action='/api/reports/{}/approve'><button class='green'>{}</button></form><form method='post' action='/api/reports/{}/reject'><button class='gray'>{}</button></form></div></div>".format(
                esc(r["title"]), esc(summarize_text(r["summary"], 120)), esc(r["report_type"]), esc(r["status"]), esc(dt(r["updated_at"])), r["id"], U(r"\u751f\u6210"), r["id"], U(r"\u901a\u8fc7"), r["id"], U(r"\u9a73\u56de")
            )
        if not report_cards:
            report_cards = "<div class='panel'>{}</div>".format(self.empty_state(U(r"\u6682\u65e0\u62a5\u544a\uff0c\u53ef\u5148\u751f\u6210 AI \u65e5\u62a5\u8349\u7a3f\u3002")))
        template_cards = "".join("<div class='card'><div><h2>{}</h2><p>{}</p><p class='small'>{} 路 {}</p></div></div>".format(esc(t["template_name"]), esc(t["description"]), esc(t["report_type"]), esc(t["default_date_range"])) for t in templates)
        schedule_items = [f"{s['frequency']} 路 {s['recipients']} 路 {'enabled' if s['enabled'] else 'disabled'}" for s in schedules] or [U(r"\u6682\u65e0\u5b9a\u65f6\u62a5\u544a\u3002")]
        body = f"""
<div class="panel">
  <h2>{U(r'\u62a5\u544a\u4e2d\u5fc3')}</h2>
  <p class="small">{U(r'AI \u62a5\u544a\u53ea\u662f\u8349\u7a3f\uff0c\u672a\u7ecf\u5ba1\u6838\u4e0d\u662f\u6b63\u5f0f\u62a5\u544a\u3002')}</p>
</div>
<div class="split">
  <div class="panel form">
    <h2>{U(r'\u65b0\u5efa\u62a5\u544a\u8349\u7a3f')}</h2>
    <form method="post" action="/reports/save">
      <label>{U(r'\u62a5\u544a\u6807\u9898')}</label><input name="title" required>
      <label>{U(r'\u62a5\u544a\u7c7b\u578b')}</label><select name="report_type">{template_options}</select>
      <label>{U(r'\u5f00\u59cb\u65e5\u671f')}</label><input name="date_range_start" placeholder="2026-07-01">
      <label>{U(r'\u7ed3\u675f\u65e5\u671f')}</label><input name="date_range_end" placeholder="2026-07-04">
      <label>{U(r'\u5173\u8054\u5bf9\u8c61')}</label><input name="object_type" placeholder="store / brand / inventory"><input name="object_id" placeholder="ID">
      <p><button>{U(r'\u4fdd\u5b58\u5e76\u751f\u6210\u8349\u7a3f')}</button></p>
    </form>
  </div>
  <div class="panel"><h2>{U(r'\u5b9a\u65f6\u62a5\u544a')}</h2>{self.bullets(schedule_items)}<p class="small">{U(r'\u540e\u7eed\u7531 n8n \u5728\u6bcf\u65e5 2:00 SAP \u540c\u6b65\u540e\u81ea\u52a8\u751f\u6210\u3002')}</p></div>
</div>
<div class="panel"><h2>{U(r'\u62a5\u544a\u5217\u8868')}</h2><div class="grid">{report_cards}</div></div>
<div class="panel"><h2>{U(r'\u9ed8\u8ba4\u6a21\u677f')}</h2><div class="grid">{template_cards}</div></div>"""
        self.out(layout(U(r"\u62a5\u544a\u4e2d\u5fc3"), body, user=user, wide=True))

    def report_save(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        if not self.can_manage_reports(user):
            return self.redir("/")
        form = self.form()
        title = form.get("title", "").strip()
        if not title:
            return self.redir("/reports")
        payload = self.report_draft_payload(user, form.get("report_type", "ceo_daily"), title, form.get("object_type", ""), int(form.get("object_id")) if str(form.get("object_id", "")).isdigit() else None)
        now = ts()
        with db() as conn:
            cur = conn.execute(
                "insert into reports(report_id,title,report_type,date_range_start,date_range_end,object_type,object_id,status,summary,key_findings,risks,opportunities,recommended_actions,data_sources,cited_documents,cited_research,cited_memory,cited_sap_records,generated_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("RPT-" + uuid.uuid4().hex[:10], title, payload["report_type"], form.get("date_range_start", ""), form.get("date_range_end", ""), payload["object_type"], payload["object_id"], "draft", payload["summary"], json.dumps(payload["key_findings"], ensure_ascii=False), json.dumps(payload["risks"], ensure_ascii=False), json.dumps(payload["opportunities"], ensure_ascii=False), json.dumps(payload["recommended_actions"], ensure_ascii=False), json.dumps(payload["data_sources"], ensure_ascii=False), "[]", "[]", "[]", json.dumps(payload["cited_sap_records"], ensure_ascii=False), user["id"], now, now),
            )
        self.log_action(user, "report_created", "report", cur.lastrowid, title)
        return self.redir("/reports")

    def export_report_payload(self, row, fmt):
        sections = {
            "summary": row["summary"],
            "key_findings": safe_json(row["key_findings"], []),
            "risks": safe_json(row["risks"], []),
            "opportunities": safe_json(row["opportunities"], []),
            "recommended_actions": safe_json(row["recommended_actions"], []),
        }
        if fmt == "html":
            body = "<h1>{}</h1><p>{}</p>".format(esc(row["title"]), esc(sections["summary"]))
            for key in ("key_findings", "risks", "opportunities", "recommended_actions"):
                body += "<h2>{}</h2>{}".format(esc(key), self.bullets(sections[key]))
            return {"format": "html", "content": "<!doctype html><meta charset='utf-8'>" + body}
        lines = ["# " + row["title"], "", sections["summary"], ""]
        for key in ("key_findings", "risks", "opportunities", "recommended_actions"):
            lines += ["## " + key, ""]
            lines += ["- " + str(x) for x in sections[key]]
            lines.append("")
        return {"format": "markdown", "content": "\n".join(lines)}

    def api_reports_get(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_manage_reports(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        with db() as conn:
            self.seed_report_templates(conn)
            if path == "/api/reports":
                rows = conn.execute("select * from reports order by updated_at desc limit 100").fetchall()
                return self.json_out({"ok": True, "reports": [row_dict(r) for r in rows]})
            m = re.match(r"^/api/reports/(\d+)$", path)
            if m:
                row = conn.execute("select * from reports where id=?", (m.group(1),)).fetchone()
                return self.json_out({"ok": bool(row), "report": row_dict(row)} if row else {"ok": False, "message": "not found"}, code=200 if row else 404)
            if path == "/api/report-templates":
                rows = conn.execute("select * from report_templates order by id").fetchall()
                return self.json_out({"ok": True, "templates": [row_dict(r) for r in rows]})
            if path == "/api/report-schedules":
                rows = conn.execute("select * from report_schedules order by created_at desc limit 100").fetchall()
                return self.json_out({"ok": True, "schedules": [row_dict(r) for r in rows]})
        return self.json_out({"ok": False, "message": "unknown reports api"}, code=404)

    def api_reports_post(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_manage_reports(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        form = self.form()
        now = ts()
        if path == "/api/reports":
            payload = self.report_draft_payload(user, form.get("report_type", "ceo_daily"), form.get("title", U(r"AI \u62a5\u544a\u8349\u7a3f")), form.get("object_type", ""), int(form.get("object_id")) if str(form.get("object_id", "")).isdigit() else None)
            with db() as conn:
                cur = conn.execute(
                    "insert into reports(report_id,title,report_type,date_range_start,date_range_end,object_type,object_id,status,summary,key_findings,risks,opportunities,recommended_actions,data_sources,cited_documents,cited_research,cited_memory,cited_sap_records,generated_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    ("RPT-" + uuid.uuid4().hex[:10], payload["title"], payload["report_type"], form.get("date_range_start", ""), form.get("date_range_end", ""), payload["object_type"], payload["object_id"], "draft", payload["summary"], json.dumps(payload["key_findings"], ensure_ascii=False), json.dumps(payload["risks"], ensure_ascii=False), json.dumps(payload["opportunities"], ensure_ascii=False), json.dumps(payload["recommended_actions"], ensure_ascii=False), json.dumps(payload["data_sources"], ensure_ascii=False), "[]", "[]", "[]", json.dumps(payload["cited_sap_records"], ensure_ascii=False), user["id"], now, now),
                )
            self.log_action(user, "report_created", "report", cur.lastrowid, payload["title"])
            return self.json_out({"ok": True, "report_id": cur.lastrowid, "report": payload})
        m = re.match(r"^/api/reports/(\d+)/(generate|approve|reject|archive|export)$", path)
        if m:
            rid, action = m.group(1), m.group(2)
            with db() as conn:
                row = conn.execute("select * from reports where id=?", (rid,)).fetchone()
                if not row:
                    return self.json_out({"ok": False, "message": "not found"}, code=404)
                if action == "generate":
                    payload = self.report_draft_payload(user, row["report_type"], row["title"], row["object_type"], row["object_id"])
                    conn.execute("update reports set summary=?, key_findings=?, risks=?, opportunities=?, recommended_actions=?, data_sources=?, cited_sap_records=?, status='draft', updated_at=? where id=?", (payload["summary"], json.dumps(payload["key_findings"], ensure_ascii=False), json.dumps(payload["risks"], ensure_ascii=False), json.dumps(payload["opportunities"], ensure_ascii=False), json.dumps(payload["recommended_actions"], ensure_ascii=False), json.dumps(payload["data_sources"], ensure_ascii=False), json.dumps(payload["cited_sap_records"], ensure_ascii=False), now, rid))
                    self.log_action(user, "report_generated", "report", rid, row["title"])
                    return self.json_out({"ok": True, "report": payload})
                if action in ("approve", "reject", "archive"):
                    status = {"approve": "approved", "reject": "rejected", "archive": "archived"}[action]
                    conn.execute("update reports set status=?, reviewed_by=?, reviewed_at=?, updated_at=? where id=?", (status, user["id"], now, now, rid))
                    self.log_action(user, "report_" + action, "report", rid, row["title"])
                    return self.json_out({"ok": True, "status": status})
                if action == "export":
                    fmt = form.get("format", "markdown")
                    return self.json_out({"ok": True, "export": self.export_report_payload(row, fmt)})
        if path == "/api/report-templates":
            with db() as conn:
                cur = conn.execute("insert into report_templates(template_id,template_name,report_type,description,sections,required_sources,default_date_range,visibility,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?)", ("TPL-" + uuid.uuid4().hex[:10], form.get("template_name", U(r"\u672a\u547d\u540d\u6a21\u677f")), form.get("report_type", "custom"), form.get("description", ""), json.dumps(csv_values(form.get("sections", "")), ensure_ascii=False), json.dumps(csv_values(form.get("required_sources", "")), ensure_ascii=False), form.get("default_date_range", "yesterday"), form.get("visibility", "manager_only"), now, now))
            return self.json_out({"ok": True, "template_id": cur.lastrowid})
        if path == "/api/report-schedules":
            with db() as conn:
                cur = conn.execute("insert into report_schedules(schedule_id,report_template_id,frequency,recipients,enabled,last_run_at,next_run_at,created_by,created_at) values(?,?,?,?,?,?,?,?,?)", ("SCH-" + uuid.uuid4().hex[:10], int(form.get("report_template_id")) if str(form.get("report_template_id", "")).isdigit() else None, form.get("frequency", "daily"), form.get("recipients", ""), 1 if form.get("enabled", "1") != "0" else 0, None, None, user["id"], now))
            return self.json_out({"ok": True, "schedule_id": cur.lastrowid})
        return self.json_out({"ok": False, "message": "unknown reports api"}, code=404)

    def api_reports_put(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if not self.can_manage_reports(user):
            return self.json_out({"ok": False, "message": "no permission"}, code=403)
        m = re.match(r"^/api/reports/(\d+)$", path)
        if not m:
            return self.json_out({"ok": False, "message": "unknown reports api"}, code=404)
        form = self.form()
        with db() as conn:
            conn.execute(
                "update reports set title=coalesce(?,title), summary=coalesce(?,summary), key_findings=coalesce(?,key_findings), risks=coalesce(?,risks), opportunities=coalesce(?,opportunities), recommended_actions=coalesce(?,recommended_actions), status=coalesce(?,status), updated_at=? where id=?",
                (form.get("title"), form.get("summary"), form.get("key_findings"), form.get("risks"), form.get("opportunities"), form.get("recommended_actions"), form.get("status"), ts(), m.group(1)),
            )
        self.log_action(user, "report_updated", "report", m.group(1), "")
        return self.json_out({"ok": True})

    def can_use_jarvis(self, user):
        return bool(user and user["status"] == "approved")

    def can_confirm_jarvis_action(self, user):
        return bool(user and user["role"] in ("boss", "admin", "store_manager"))

    def jarvis_suggestions(self):
        return {
            "business": [
                U(r"\u4eca\u5929\u516c\u53f8\u7ecf\u8425\u600e\u4e48\u6837\uff1f"),
                U(r"\u672c\u6708\u9500\u552e\u548c\u6bdb\u5229\u600e\u4e48\u6837\uff1f"),
                U(r"\u54ea\u4e2a\u95e8\u5e97\u9700\u8981\u5173\u6ce8\uff1f"),
                U(r"\u54ea\u4e2a\u54c1\u724c\u5e93\u5b58\u538b\u529b\u6700\u5927\uff1f"),
            ],
            "brand": [
                U(r"Osprey \u73b0\u5728\u5e94\u8be5\u600e\u4e48\u5904\u7406\uff1f"),
                U(r"KAILAS \u6700\u8fd1\u8868\u73b0\u600e\u4e48\u6837\uff1f"),
                U(r"Mammut \u662f\u5426\u9002\u5408\u52a0\u5927\u6295\u5165\uff1f"),
            ],
            "knowledge": [
                U(r"\u5357\u5c71\u5e97\u79df\u8d41\u5408\u540c\u5728\u54ea\u91cc\uff1f"),
                U(r"\u5458\u5de5\u57f9\u8bad\u8d44\u6599\u6709\u54ea\u4e9b\uff1f"),
                U(r"\u54c1\u724c\u5408\u540c\u5728\u54ea\u91cc\uff1f"),
            ],
            "task": [
                U(r"\u628a\u4eca\u5929\u7684\u98ce\u9669\u53d8\u6210\u4efb\u52a1\u3002"),
                U(r"\u7ed9\u5357\u5c71\u5e97\u751f\u6210\u4e00\u4e2a\u63d0\u5347\u8ba1\u5212\u3002"),
                U(r"\u751f\u6210 Osprey \u98ce\u9669\u5904\u7406\u4efb\u52a1\u3002"),
            ],
            "research": [
                U(r"\u6700\u8fd1\u6237\u5916\u884c\u4e1a\u6709\u4ec0\u4e48\u53d8\u5316\uff1f"),
                U(r"Osprey \u5916\u90e8\u4ef7\u683c\u6709\u4ec0\u4e48\u53d8\u5316\uff1f"),
                U(r"KAILAS \u6709\u4ec0\u4e48\u65b0\u54c1\u52a8\u6001\uff1f"),
            ],
        }

    def route_jarvis_intent(self, text):
        q = (text or "").lower()
        rules = [
            ("task_creation", ["task", U(r"\u4efb\u52a1"), U(r"\u5b89\u6392"), U(r"\u8ddf\u8fdb")]),
            ("report_generation", ["report", U(r"\u62a5\u544a"), U(r"\u65e5\u62a5"), U(r"\u5468\u62a5"), U(r"\u6708\u62a5")]),
            ("sap_query", ["sap", "b1", U(r"\u9500\u552e"), U(r"\u6bdb\u5229"), U(r"\u5e93\u5b58"), U(r"\u95e8\u5e97")]),
            ("knowledge_query", [U(r"\u77e5\u8bc6"), U(r"\u5408\u540c"), U(r"\u5236\u5ea6"), "sop", U(r"\u57f9\u8bad")]),
            ("research_query", [U(r"\u5916\u90e8"), U(r"\u884c\u4e1a"), U(r"\u5e02\u573a"), U(r"\u65b0\u95fb"), U(r"\u4ef7\u683c")]),
            ("memory_query", [U(r"\u8bb0\u5fc6"), U(r"\u539f\u5219"), U(r"\u504f\u597d"), U(r"\u51b3\u7b56")]),
            ("graph_query", [U(r"\u56fe\u8c31"), U(r"\u5173\u8054"), U(r"\u5173\u7cfb")]),
            ("agent_collaboration", [U(r"\u534f\u540c"), U(r"\u667a\u80fd\u4f53"), "agent", "cfo", "ceo"]),
            ("business_query", [U(r"\u516c\u53f8"), U(r"\u7ecf\u8425"), U(r"\u600e\u4e48\u6837"), U(r"\u98ce\u9669")]),
            ("content_generation", [U(r"\u5199"), U(r"\u6587\u6848"), U(r"\u5185\u5bb9"), U(r"\u8bdd\u672f")]),
            ("system_help", [U(r"\u5e2e\u52a9"), U(r"\u600e\u4e48\u7528"), "help"]),
        ]
        for intent, words in rules:
            if any(w.lower() in q for w in words):
                return intent
        return "general_question"

    def jarvis_tool_result(self, user, intent, question):
        result = {"success": True, "data": {}, "sources": [], "limitations": [], "next_actions": []}
        if intent in ("business_query", "sap_query"):
            data = self.cockpit_data()
            result["data"] = {"metrics": data["metrics"], "ai_suggestions": data["ai_suggestions"][:5], "todos": data["todos"][:5]}
            result["sources"].append({"type": "sap_summary", "title": U(r"SAP B1 \u540c\u6b65\u6458\u8981"), "url": "/sap-sync"})
            if not data["has_data"]:
                result["limitations"].append(data["empty_message"])
            result["next_actions"] += [{"label": U(r"\u6253\u5f00\u7ecf\u8425\u9a7e\u9a76\u8231"), "url": "/business-overview"}]
        if intent == "knowledge_query":
            terms = [w for w in re.split(r"\s+", question or "") if w][:6] or [question]
            rows = []
            with db() as conn:
                for term in terms:
                    like = "%" + term + "%"
                    rows.extend(conn.execute("select * from knowledge_items where title like ? or body like ? or summary like ? or tags like ? order by updated_at desc limit 5", (like, like, like, like)).fetchall())
            seen = set()
            items = []
            for row in rows:
                if row["id"] in seen or not self.can_view_knowledge(user, row):
                    continue
                seen.add(row["id"])
                items.append({"id": row["id"], "title": row["title"], "summary": row["summary"] or row["ai_summary"] or summarize_text(row["body"], 120), "url": f"/knowledge/view?id={row['id']}"})
            result["data"]["knowledge_items"] = items[:8]
            result["sources"] += [{"type": "knowledge", "title": item["title"], "url": item["url"]} for item in items[:5]]
            result["next_actions"].append({"label": U(r"\u6253\u5f00\u77e5\u8bc6\u4e2d\u5fc3"), "url": "/knowledge"})
        if intent == "memory_query":
            with db() as conn:
                rows = conn.execute("select * from memories where status='approved' order by updated_at desc limit 8").fetchall()
            memories = [{"id": r["id"], "title": r["title"], "content": summarize_text(r["content"], 140), "url": f"/memory/view?id={r['id']}"} for r in rows if self.can_view_memory(user, r)]
            result["data"]["memories"] = memories
            result["sources"] += [{"type": "memory", "title": m["title"], "url": m["url"]} for m in memories[:5]]
            result["next_actions"].append({"label": U(r"\u6253\u5f00 AI \u8bb0\u5fc6\u4e2d\u5fc3"), "url": "/memory"})
        if intent == "graph_query":
            with db() as conn:
                entities = conn.execute("select * from graph_entities order by updated_at desc limit 8").fetchall()
                risks = conn.execute("select * from graph_risks order by updated_at desc limit 5").fetchall()
            result["data"]["entities"] = [row_dict(r) for r in entities]
            result["data"]["risks"] = [row_dict(r) for r in risks]
            result["sources"].append({"type": "graph", "title": U(r"\u4f01\u4e1a\u77e5\u8bc6\u56fe\u8c31"), "url": "/graph"})
            result["next_actions"].append({"label": U(r"\u6253\u5f00\u77e5\u8bc6\u56fe\u8c31"), "url": "/graph"})
        if intent == "agent_collaboration":
            data = self.agent_summary()
            result["data"] = {"roles": len(data["roles"]), "tasks": len(data["tasks"]), "tools": len(data["tools"])}
            result["sources"].append({"type": "agents", "title": U(r"\u591a\u667a\u80fd\u4f53\u534f\u540c"), "url": "/agents/collaboration"})
            result["next_actions"].append({"label": U(r"\u6253\u5f00\u591a\u667a\u80fd\u4f53"), "url": "/agents/collaboration"})
        if intent == "task_creation":
            result["data"]["proposed_action"] = {
                "action_type": "create_task",
                "title": summarize_text(question, 48) or U(r"Jarvis \u5efa\u8bae\u4efb\u52a1"),
                "reason": U(r"Jarvis \u53ea\u751f\u6210\u5efa\u8bae\uff0c\u9700\u8981\u4eba\u5de5\u786e\u8ba4\u540e\u518d\u6267\u884c\u3002"),
            }
            result["next_actions"].append({"label": U(r"\u5148\u53bb\u4efb\u52a1\u4e2d\u5fc3\u624b\u52a8\u521b\u5efa"), "url": "/tasks"})
        if intent == "report_generation":
            result["data"]["report_placeholder"] = self.jarvis_report_payload(question)
            result["sources"].append({"type": "report", "title": U(r"\u62a5\u544a\u751f\u6210\u6846\u67b6"), "url": "/jarvis"})
        if intent == "research_query":
            result["success"] = False
            result["limitations"].append(U(r"\u5916\u90e8\u7814\u7a76\u5f15\u64ce\u5df2\u9884\u7559\uff0c\u672a\u914d\u7f6e\u5b9e\u65f6\u641c\u7d22 API \u65f6\u4e0d\u81ea\u52a8\u7f16\u9020\u5916\u90e8\u4e8b\u5b9e\u3002"))
            result["next_actions"].append({"label": U(r"\u6253\u5f00\u5916\u7f51\u641c\u7d22\u5b58\u77e5\u8bc6\u5e93"), "url": "/web-search"})
        if intent == "content_generation":
            body, summary = self.content_skeleton(U(r"Jarvis \u5185\u5bb9\u8349\u7a3f"), "article", question, "wechat_official,xiaohongshu,douyin")
            result["data"]["content_skeleton"] = {"body": body, "summary": summary, "platforms": ["wechat_official", "xiaohongshu", "douyin"]}
            result["sources"].append({"type": "content_engine", "title": U(r"\u5185\u5bb9\u53d1\u5e03\u5f15\u64ce"), "url": "/content"})
            result["next_actions"].append({"label": U(r"\u6253\u5f00\u5185\u5bb9\u53d1\u5e03\u5f15\u64ce"), "url": "/content"})
        if any(word in (question or "") for word in [U(r"\u5357\u5c71\u5e97"), U(r"\u822a\u82d1\u5e97"), U(r"\u632f\u5174\u5e97"), U(r"\u91d1\u6c99\u5e97"), U(r"\u95e8\u5e97\u589e\u957f"), U(r"\u63d0\u5347\u8ba1\u5212")]):
            result["data"]["store_growth"] = self.store_growth_diagnosis_payload(U(r"\u5f85\u9009\u95e8\u5e97"))
            result["sources"].append({"type": "store_growth", "title": U(r"\u95e8\u5e97\u589e\u957f\u5f15\u64ce"), "url": "/store-growth"})
            result["next_actions"].append({"label": U(r"\u6253\u5f00\u95e8\u5e97\u589e\u957f\u5f15\u64ce"), "url": "/store-growth"})
        if not result["sources"]:
            result["limitations"].append(U(r"\u6682\u65e0\u53ef\u5f15\u7528\u6765\u6e90\u3002"))
        return result

    def jarvis_answer_payload(self, user, question):
        intent = self.route_jarvis_intent(question)
        tool = self.jarvis_tool_result(user, intent, question)
        answer = U(r"Jarvis \u5bf9\u8bdd\u5165\u53e3\u5df2\u5efa\u7acb\uff0c\u5df2\u6309\u95ee\u9898\u610f\u56fe\u8fde\u63a5\u73b0\u6709\u77e5\u8bc6\u3001SAP \u6458\u8981\u3001\u8bb0\u5fc6\u3001\u56fe\u8c31\u3001\u4efb\u52a1\u548c\u667a\u80fd\u4f53\u6a21\u5757\u3002")
        if intent in ("business_query", "sap_query") and tool["data"].get("metrics"):
            m = tool["data"]["metrics"]
            answer = "{}\n\n{}: {} | {}: {} | {}: {} | {}: {}".format(
                U(r"\u5df2\u4ece SAP B1 \u6458\u8981\u548c\u7ecf\u8425\u9a7e\u9a76\u8231\u53d6\u5230\u5f53\u524d\u53ef\u7528\u6570\u636e\u3002"),
                U(r"\u6628\u65e5\u9500\u552e"), money(m.get("yesterday_sales")),
                U(r"\u672c\u6708\u9500\u552e"), money(m.get("month_sales")),
                U(r"\u5b8c\u6210\u7387"), pct(m.get("completion_rate")),
                U(r"\u5e93\u5b58\u91d1\u989d"), money(m.get("inventory_amount")),
            )
        elif intent == "knowledge_query":
            count = len(tool["data"].get("knowledge_items", []))
            answer = U(r"\u5df2\u5728\u77e5\u8bc6\u5e93\u4e2d\u68c0\u7d22\uff0c\u627e\u5230 {count} \u6761\u53ef\u53c2\u8003\u5185\u5bb9\u3002").format(count=count)
        elif intent == "task_creation":
            answer = U(r"\u6211\u5df2\u628a\u8fd9\u4e2a\u9700\u6c42\u8bc6\u522b\u4e3a\u4efb\u52a1\u521b\u5efa\u7c7b\u3002\u7cfb\u7edf\u5df2\u751f\u6210\u5f85\u786e\u8ba4\u52a8\u4f5c\uff0c\u786e\u8ba4\u540e\u518d\u8fdb\u5165\u6267\u884c\u3002")
        elif intent == "report_generation":
            answer = U(r"\u5df2\u751f\u6210\u62a5\u544a\u6846\u67b6\uff0c\u5f53\u524d\u4ec5\u4f5c\u8349\u7a3f\uff0c\u6b63\u5f0f\u62a5\u544a\u9700\u4eba\u5de5\u5ba1\u6838\u3002")
        return {
            "intent": intent,
            "answer": answer,
            "confidence": "medium" if tool["sources"] else "low",
            "tool_calls": [{"tool": "jarvis_router", "intent": intent}, {"tool": "adapter_layer", "success": tool["success"]}],
            "cited_sources": tool["sources"],
            "related_objects": tool["data"],
            "limitations": list(dict.fromkeys(tool["limitations"])),
            "next_actions": tool["next_actions"],
        }

    def jarvis_report_payload(self, prompt=""):
        return {
            "report_type": "CEO Daily Report",
            "title": summarize_text(prompt, 60) or U(r"AI \u603b\u7ecf\u7406\u65e5\u62a5\u8349\u7a3f"),
            "sections": [
                U(r"\u9500\u552e\u6458\u8981"),
                U(r"\u6bdb\u5229\u4e0e\u5e93\u5b58"),
                U(r"\u4f1a\u5458\u4e0e\u95e8\u5e97"),
                U(r"\u98ce\u9669\u4e0e\u673a\u4f1a"),
                U(r"AI \u5efa\u8bae"),
                U(r"\u5f85\u4eba\u5de5\u5ba1\u6838\u4e8b\u9879"),
            ],
            "status": "draft_placeholder",
            "note": U(r"\u672a\u63a5\u5165\u5927\u6a21\u578b\u548c\u62a5\u544a\u5ba1\u6838\u6d41\u7a0b\u524d\uff0c\u4e0d\u4ea7\u751f\u6b63\u5f0f\u62a5\u544a\u3002"),
        }

    def get_or_create_jarvis_conversation(self, conn, user, conversation_id, question):
        row = None
        if str(conversation_id or "").isdigit():
            row = conn.execute("select * from jarvis_conversations where id=? and user_id=?", (conversation_id, user["id"])).fetchone()
        elif conversation_id:
            row = conn.execute("select * from jarvis_conversations where conversation_id=? and user_id=?", (conversation_id, user["id"])).fetchone()
        if row:
            return row
        now = ts()
        cur = conn.execute(
            "insert into jarvis_conversations(conversation_id,user_id,title,status,created_at,updated_at) values(?,?,?,?,?,?)",
            ("JAR-" + uuid.uuid4().hex[:10], user["id"], summarize_text(question, 40) or U(r"Jarvis \u65b0\u5bf9\u8bdd"), "active", now, now),
        )
        self.log_action(user, "jarvis_conversation_created", "jarvis_conversation", cur.lastrowid, question[:120])
        return conn.execute("select * from jarvis_conversations where id=?", (cur.lastrowid,)).fetchone()

    def save_jarvis_message(self, conn, conversation_id, role, content, payload=None):
        now = ts()
        payload = payload or {}
        cur = conn.execute(
            "insert into jarvis_messages(message_id,conversation_id,role,content,intent,tool_calls,cited_sources,related_objects,confidence,created_at) values(?,?,?,?,?,?,?,?,?,?)",
            (
                "MSG-" + uuid.uuid4().hex[:10],
                conversation_id,
                role,
                content,
                payload.get("intent", ""),
                json.dumps(payload.get("tool_calls", []), ensure_ascii=False),
                json.dumps(payload.get("cited_sources", []), ensure_ascii=False),
                json.dumps(payload.get("related_objects", {}), ensure_ascii=False),
                payload.get("confidence", ""),
                now,
            ),
        )
        return cur.lastrowid

    def jarvis_center(self, user):
        user = self.require_login(user)
        if not user:
            return
        if not self.can_use_jarvis(user):
            return self.dashboard(user)
        qd = parse_qs(urlparse(self.path).query)
        cid = qd.get("conversation_id", [""])[0]
        with db() as conn:
            conversations = conn.execute("select * from jarvis_conversations where user_id=? order by updated_at desc limit 12", (user["id"],)).fetchall()
            current = None
            if cid:
                current = conn.execute("select * from jarvis_conversations where (id=? or conversation_id=?) and user_id=?", (cid if cid.isdigit() else -1, cid, user["id"])).fetchone()
            if not current and conversations:
                current = conversations[0]
            messages = conn.execute("select * from jarvis_messages where conversation_id=? order by created_at asc limit 80", (current["id"],)).fetchall() if current else []
            actions = conn.execute("select * from jarvis_action_confirmations where created_by=? and status='pending' order by created_at desc limit 8", (user["id"],)).fetchall()
        suggestions = self.jarvis_suggestions()
        chips = "".join(
            "<button type='button' onclick=\"document.getElementById('jarvis-question').value='{}'\">{}</button>".format(esc(q), esc(q))
            for group in suggestions.values()
            for q in group[:2]
        )
        message_html = ""
        for msg in messages:
            source_html = ""
            if msg["role"] == "assistant":
                sources = safe_json(msg["cited_sources"], [])
                if sources:
                    source_html = "<div class='small'>" + " ".join("<a class='pill' href='{}'>{}</a>".format(esc(s.get("url", "#")), esc(s.get("title", s.get("type", "source")))) for s in sources[:5]) + "</div>"
            message_html += "<div class='chat-message {}'><strong>{}</strong><p>{}</p>{}</div>".format(esc(msg["role"]), esc(msg["role"]), esc(msg["content"]), source_html)
        if not message_html:
            message_html = "<div class='chat-message assistant'><strong>Jarvis</strong><p>{}</p></div>".format(U(r"\u4f60\u53ef\u4ee5\u76f4\u63a5\u95ee\u7ecf\u8425\u3001\u77e5\u8bc6\u5e93\u3001SAP\u3001\u8bb0\u5fc6\u3001\u56fe\u8c31\u548c\u4efb\u52a1\u3002\u6211\u4f1a\u5148\u627e\u5df2\u6709\u6765\u6e90\uff0c\u6ca1\u6709\u6765\u6e90\u65f6\u660e\u786e\u8bf4\u7b49\u5f85\u63a5\u5165\u3002"))
        conversation_links = "".join("<a class='pill' href='/jarvis?conversation_id={}'>{}</a>".format(c["id"], esc(c["title"])) for c in conversations) or self.empty_state(U(r"\u6682\u65e0\u5386\u53f2\u5bf9\u8bdd\u3002"))
        action_rows = ""
        for action in actions:
            action_rows += """
<div class="source-item">
  <strong>{}</strong><p class="small">{}</p>
  <form class="inline" method="post" action="/jarvis/action">
    <input type="hidden" name="action_id" value="{}">
    <button name="decision" value="confirm">{}</button>
    <button class="gray" name="decision" value="cancel">{}</button>
  </form>
</div>""".format(esc(action["title"]), esc(action["reason"]), esc(action["action_id"]), U(r"\u786e\u8ba4"), U(r"\u53d6\u6d88"))
        if not action_rows:
            action_rows = self.empty_state(U(r"\u6682\u65e0\u5f85\u786e\u8ba4\u52a8\u4f5c\u3002"))
        body = f"""
<div class="chat-shell">
  <div>
    <div class="panel">
      <h2>FoxBrain Jarvis</h2>
      <p class="small">{U(r'\u7edf\u4e00 AI \u52a9\u7406\u5165\u53e3\uff1a\u4e1a\u52a1\u67e5\u8be2\u3001\u77e5\u8bc6\u68c0\u7d22\u3001\u8bb0\u5fc6\u3001\u56fe\u8c31\u3001\u667a\u80fd\u4f53\u534f\u540c\u548c\u4efb\u52a1\u751f\u6210\u3002')}</p>
      <div class="chipbar">{chips}</div>
    </div>
    <div class="panel">{message_html}</div>
    <div class="chat-input">
      <form method="post" action="/jarvis/message">
        <input type="hidden" name="conversation_id" value="{esc(current['id'] if current else '')}">
        <label>{U(r'\u95ee Jarvis')}</label>
        <textarea id="jarvis-question" name="question" placeholder="{U(r'\u4f8b\uff1a\u4eca\u5929\u516c\u53f8\u7ecf\u8425\u600e\u4e48\u6837\uff1f')}" required></textarea>
        <p><button>{U(r'\u53d1\u9001')}</button></p>
      </form>
    </div>
  </div>
  <div>
    <div class="panel"><h2>{U(r'\u5bf9\u8bdd\u5386\u53f2')}</h2>{conversation_links}<p><a class="btn gray" href="/jarvis">{U(r'\u65b0\u5bf9\u8bdd')}</a></p></div>
    <div class="panel"><h2>{U(r'\u5f85\u786e\u8ba4\u52a8\u4f5c')}</h2>{action_rows}</div>
    <div class="panel"><h2>{U(r'\u6765\u6e90\u4e0e\u9650\u5236')}</h2>{self.bullets([U(r'\u56de\u7b54\u5c3d\u91cf\u5f15\u7528\u5df2\u6709\u77e5\u8bc6\u3001SAP \u6458\u8981\u3001\u8bb0\u5fc6\u548c\u56fe\u8c31\u3002'), U(r'\u6ca1\u6709\u6765\u6e90\u65f6\u4e0d\u7f16\u9020\u7ecf\u8425\u7ed3\u8bba\u3002'), U(r'\u91cd\u8981\u52a8\u4f5c\u9700\u4eba\u5de5\u786e\u8ba4\u3002')])}</div>
    <div class="panel"><h2>{U(r'\u8bed\u97f3\u8f93\u5165')}</h2>{self.empty_state(U(r'\u8bed\u97f3\u8f93\u5165\u80fd\u529b\u9884\u7559\uff0c\u7b49\u5f85\u63a5\u5165\u8bed\u97f3\u8bc6\u522b\u670d\u52a1\u3002'))}</div>
  </div>
</div>"""
        self.out(layout(U(r"FoxBrain Jarvis"), body, user=user, wide=True))

    def jarvis_message_post(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        form = self.form()
        question = form.get("question", "").strip()
        if not question:
            return self.redir("/jarvis")
        payload = self.jarvis_answer_payload(user, question)
        now = ts()
        with db() as conn:
            conv = self.get_or_create_jarvis_conversation(conn, user, form.get("conversation_id", ""), question)
            self.save_jarvis_message(conn, conv["id"], "user", question, {"intent": payload["intent"]})
            self.save_jarvis_message(conn, conv["id"], "assistant", payload["answer"], payload)
            conn.execute("update jarvis_conversations set updated_at=? where id=?", (now, conv["id"]))
            proposed = payload["related_objects"].get("proposed_action") if isinstance(payload["related_objects"], dict) else None
            if proposed:
                conn.execute(
                    "insert into jarvis_action_confirmations(action_id,conversation_id,action_type,title,reason,payload_json,status,created_by,created_at) values(?,?,?,?,?,?,?,?,?)",
                    ("ACT-" + uuid.uuid4().hex[:10], conv["id"], proposed["action_type"], proposed["title"], proposed["reason"], json.dumps(proposed, ensure_ascii=False), "pending", user["id"], now),
                )
        self.log_action(user, "jarvis_question_asked", "jarvis_conversation", conv["id"], payload["intent"])
        return self.redir(f"/jarvis?conversation_id={conv['id']}")

    def jarvis_action_post(self):
        user = self.current_user()
        if not user:
            return self.redir("/login")
        if not self.can_confirm_jarvis_action(user):
            return self.redir("/jarvis")
        form = self.form()
        action_id = form.get("action_id", "")
        decision = form.get("decision", "confirm")
        status = "confirmed" if decision == "confirm" else "cancelled"
        with db() as conn:
            conn.execute("update jarvis_action_confirmations set status=?, decided_by=?, decided_at=? where action_id=? and status='pending'", (status, user["id"], ts(), action_id))
        self.log_action(user, "jarvis_action_" + status, "jarvis_action", None, action_id)
        return self.redir("/jarvis")

    def api_jarvis_get(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        if path == "/api/jarvis/status":
            return self.json_out({"ok": True, "status": "ready", "intents": ["general_question", "business_query", "sap_query", "knowledge_query", "research_query", "memory_query", "graph_query", "agent_collaboration", "task_creation", "report_generation", "content_generation", "system_help"], "ai_api": "not_required_for_v1"})
        if path == "/api/jarvis/suggestions":
            return self.json_out({"ok": True, "suggestions": self.jarvis_suggestions()})
        if path == "/api/jarvis/conversations":
            with db() as conn:
                rows = conn.execute("select * from jarvis_conversations where user_id=? order by updated_at desc limit 50", (user["id"],)).fetchall()
            return self.json_out({"ok": True, "conversations": [row_dict(r) for r in rows]})
        m = re.match(r"^/api/jarvis/conversations/([^/]+)$", path)
        if m:
            cid = m.group(1)
            with db() as conn:
                conv = conn.execute("select * from jarvis_conversations where (id=? or conversation_id=?) and user_id=?", (cid if cid.isdigit() else -1, cid, user["id"])).fetchone()
                if not conv:
                    return self.json_out({"ok": False, "message": "not found"}, code=404)
                msgs = conn.execute("select * from jarvis_messages where conversation_id=? order by created_at", (conv["id"],)).fetchall()
            return self.json_out({"ok": True, "conversation": row_dict(conv), "messages": [row_dict(r) for r in msgs]})
        return self.json_out({"ok": False, "message": "unknown jarvis api"}, code=404)

    def api_jarvis_post(self, user, path):
        if not user:
            return self.json_out({"ok": False, "message": "login required"}, code=401)
        form = self.form()
        if path == "/api/jarvis/conversations":
            title = form.get("title", U(r"Jarvis \u65b0\u5bf9\u8bdd"))
            now = ts()
            with db() as conn:
                cur = conn.execute("insert into jarvis_conversations(conversation_id,user_id,title,status,created_at,updated_at) values(?,?,?,?,?,?)", ("JAR-" + uuid.uuid4().hex[:10], user["id"], title, "active", now, now))
            self.log_action(user, "jarvis_conversation_created", "jarvis_conversation", cur.lastrowid, title)
            return self.json_out({"ok": True, "conversation_id": cur.lastrowid})
        if path == "/api/jarvis/route-intent":
            question = form.get("question", "")
            intent = self.route_jarvis_intent(question)
            self.log_action(user, "jarvis_intent_routed", "jarvis", None, intent)
            return self.json_out({"ok": True, "intent": intent})
        if path == "/api/jarvis/message":
            question = form.get("question", "").strip()
            if not question:
                return self.json_out({"ok": False, "message": "question required"}, code=400)
            payload = self.jarvis_answer_payload(user, question)
            now = ts()
            with db() as conn:
                conv = self.get_or_create_jarvis_conversation(conn, user, form.get("conversation_id", ""), question)
                user_mid = self.save_jarvis_message(conn, conv["id"], "user", question, {"intent": payload["intent"]})
                assistant_mid = self.save_jarvis_message(conn, conv["id"], "assistant", payload["answer"], payload)
                conn.execute("update jarvis_conversations set updated_at=? where id=?", (now, conv["id"]))
            self.log_action(user, "jarvis_question_asked", "jarvis_conversation", conv["id"], payload["intent"])
            return self.json_out({"ok": True, "conversation_id": conv["id"], "user_message_id": user_mid, "assistant_message_id": assistant_mid, "result": payload})
        if path == "/api/jarvis/action/confirm":
            if not self.can_confirm_jarvis_action(user):
                return self.json_out({"ok": False, "message": "no permission"}, code=403)
            action_id = form.get("action_id", "")
            decision = form.get("decision", "confirm")
            status = "confirmed" if decision == "confirm" else "cancelled"
            with db() as conn:
                conn.execute("update jarvis_action_confirmations set status=?, decided_by=?, decided_at=? where action_id=? and status='pending'", (status, user["id"], ts(), action_id))
            self.log_action(user, "jarvis_action_" + status, "jarvis_action", None, action_id)
            return self.json_out({"ok": True, "status": status})
        if path == "/api/jarvis/report":
            payload = self.jarvis_report_payload(form.get("prompt", ""))
            self.log_action(user, "jarvis_report_generated", "report", None, payload["title"])
            return self.json_out({"ok": True, "report": payload})
        return self.json_out({"ok": False, "message": "unknown jarvis api"}, code=404)


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), App).serve_forever()
