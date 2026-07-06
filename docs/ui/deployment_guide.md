# Deployment Guide — Nginx Subdomains + Frontend

## Prerequisites

- Ubuntu 22.04+
- Nginx 1.24+
- Node.js 20+
- PM2 or systemd
- Certbot (Let's Encrypt)

## Step 1: SSL Certificates

```bash
# Wildcard cert for all subdomains
sudo certbot certonly --manual --preferred-challenges dns \
  -d spcnn.ru \
  -d *.spcnn.ru
```

## Step 2: Build Frontend Apps

```bash
cd frontend/crm
npm ci
npm run build    # outputs to out/
cd ../executive
npm ci
npm run build
cd ../analytics
npm ci
npm run build
cd ../admin
npm ci
npm run build
```

## Step 3: Deploy Static Files

```bash
sudo mkdir -p /var/www/realtor/frontend/{crm,executive,analytics,admin}/out
sudo cp -r frontend/crm/out/* /var/www/realtor/frontend/crm/out/
sudo cp -r frontend/executive/out/* /var/www/realtor/frontend/executive/out/
sudo cp -r frontend/analytics/out/* /var/www/realtor/frontend/analytics/out/
sudo cp -r frontend/admin/out/* /var/www/realtor/frontend/admin/out/
sudo chown -R www-data:www-data /var/www/realtor/frontend
```

## Step 4: Deploy Backend

```bash
cd backend
source venv/bin/activate
pip install -r requirements-prod.txt

# Create systemd service
sudo tee /etc/systemd/system/realtor-api.service <<EOF
[Unit]
Description=RealtorOS API
After=network.target postgresql.service

[Service]
Type=simple
User=xiag
WorkingDirectory=/home/xiag/real-estate-os/backend
ExecStart=/home/xiag/real-estate-os/venv/bin/uvicorn main:create_app --host 127.0.0.1 --port 8000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable realtor-api
sudo systemctl start realtor-api
```

## Step 5: Configure Nginx

```bash
sudo cp docs/ui/nginx_subdomains.conf /etc/nginx/sites-available/realtor
sudo ln -sf /etc/nginx/sites-available/realtor /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## Step 6: Environment Variables

Each frontend app needs `.env.local`:

```env
NEXT_PUBLIC_API_URL=https://api.spcnn.ru
NEXT_PUBLIC_WS_URL=wss://api.spcnn.ru/ws
NEXT_PUBLIC_SITE_TITLE=RealtorOS
```

## Step 7: Verify

```bash
curl -I https://api.spcnn.ru/health
curl -I https://crm.spcnn.ru/
curl -I https://admin.spcnn.ru/
curl -I https://executive.spcnn.ru/
curl -I https://analytics.spcnn.ru/
```

All should return HTTP 200.
