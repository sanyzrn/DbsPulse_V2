FROM python:3.11-slim

# وابستگی‌های سیستمی مورد نیاز WeasyPrint برای رندر PDF (Pango/Cairo/GDK-Pixbuf).
# libpangoft2 و libharfbuzz برای شکل‌دهی درست متن فارسی/عربی (اتصال حروف) ضروری‌اند.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
