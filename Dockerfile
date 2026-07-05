FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_DIR=/data/firefox-portal
ENV SAP_SYNC_BASE=/data/firefox-sap-sync
ENV SAP_SUMMARY_FILE=/data/firefox-sap-sync/latest_summary.json
ENV HOST=0.0.0.0
ENV PORT=8088

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY portal_v2.py sync_sap_b1.py sap_b1_sync_page.md wiki_ai_plan_content.json README.md /app/
COPY infra/scripts /app/infra/scripts
COPY docs /app/docs

RUN mkdir -p /data/firefox-portal/uploads /data/firefox-sap-sync /app/logs

EXPOSE 3000 8000 8088

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD-SHELL curl -fsS "http://127.0.0.1:${PORT:-8088}/api/health" || exit 1

CMD ["python", "portal_v2.py"]
