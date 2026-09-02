#!/bin/bash
# ============================================
# SMM Bot — Serverga avtomatik o'rnatish skripti
# Ubuntu 20.04 / 22.04 / 24.04 uchun
# ============================================

set -e

echo "🚀 SMM Bot Server Deploy boshlandi..."

# 1. Tizimni yangilash va Docker o'rnatish
if ! command -v docker &> /dev/null; then
    echo "📦 Docker o'rnatilmoqda..."
    sudo apt update
    sudo apt install -y ca-certificates curl gnupg lsb-release
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt update
    sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi

# 2. .env faylini tekshirish
if [ ! -f .env ]; then
    echo "⚠️ .env fayli topilmadi! .env.example dan nusxa olinmoqda..."
    cp .env.example .env
    echo "❗ .env faylini ochib, BOT_TOKEN va ADMIN_IDS ni kiriting:"
    echo "nano .env"
    exit 1
fi

# 3. Docker compose bilan ishga tushirish
echo "🐳 Docker konteynerlar ishga tushirilmoqda..."
docker compose up -d --build

echo "✅ SMM Bot serverda muvaffaqiyatli ishga tushdi!"
echo "📊 Loglarni ko'rish uchun: docker compose logs -f bot"
