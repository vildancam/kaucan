# Canlıya Alma Notları

## GitHub Pages

GitHub Pages yalnızca statik dosya yayınlar. Bu proje ise şu çalışan servisleri
gerektirir:

- FastAPI backend
- site tarama ve indeks dosyaları
- kullanıcı sorgu/geri bildirim logları
- Ollama HTTP servisi
- `llama3.2` model dosyası

Bu nedenle uygulamanın tamamı GitHub Pages üzerinde çalıştırılamaz. GitHub Pages
ancak statik bir tanıtım sayfası veya harici bir API'ye bağlanan ayrı frontend
için kullanılabilir.

## Ollama Dahil VPS Kurulumu

Ollama ile canlı çalıştırmak için en uygun seçenek Docker destekli bir VPS'tir.
En az 4 GB RAM önerilir; daha rahat kullanım için 8 GB RAM tercih edilmelidir.

Sunucuda Docker ve Compose kurulduktan sonra:

```bash
git clone git@github.com:vildancam/kaucan.git
cd kaucan
docker compose -f docker-compose.server.yml up -d --build
```

Bu komut:

1. FastAPI uygulamasını build eder.
2. Ollama servisini başlatır.
3. `llama3.2` modelini indirir.
4. Uygulamayı `80` portundan yayınlar.
5. `data`, `logs` ve Ollama model dosyalarını Docker volume içinde saklar.

Canlı sağlık kontrolü:

```bash
curl http://SUNUCU_IP/health
```

Logları izlemek için:

```bash
docker compose -f docker-compose.server.yml logs -f app
docker compose -f docker-compose.server.yml logs -f ollama
```

Modeli manuel indirmek gerekirse:

```bash
docker compose -f docker-compose.server.yml exec ollama ollama pull llama3.2
```

## Güncelleme

Yeni GitHub değişikliklerini sunucuya almak için:

```bash
git pull
docker compose -f docker-compose.server.yml up -d --build
```

## HTTPS

Alan adı bağlanacaksa sunucuda Caddy, Nginx Proxy Manager veya Cloudflare Tunnel
kullanılabilir. GitHub Pages bu backend ve Ollama servislerinin yerine geçmez.
