# KAÜ CAN Chat Bot

Kafkas Üniversitesi İktisadi ve İdari Bilimler Fakültesi web sitesi içeriğine dayalı, kaynak gösteren RAG chatbot uygulaması.

## Kapsam

Uygulama `https://kafkas.edu.tr/iibf` adresinden başlar ve `kafkas.edu.tr` alan adı içinde kalan bağlantıları takip eder. HTML sayfalarından başlık, paragraf, liste, tablo hücresi ve anlamlı metin bloklarını çıkarır. PDF dosyalarından metin çıkarmayı destekler; diğer ek dosyaları kaynak olarak kaydeder ancak metin çıkarımı yapmaz.

Yanıtlar yalnızca indekslenmiş web sitesi içeriğine dayanır. Güvenilir sonuç bulunamazsa şu metin döndürülür:

```text
Bu konuda kesin bir bilgiye ulaşılamadı. Detaylı bilgi için ilgili fakülte ile iletişime geçmeniz önerilir.
```

## Kurulum

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

İsteğe bağlı ayarlar için `.env.example` dosyasını `.env` olarak kopyalayabilirsiniz.
Site yoğun istekleri geçici olarak sınırlayabildiği için `KAU_REQUEST_DELAY` değerini çok düşürmemeniz önerilir.

## Siteyi Tarama ve İndeksleme

```bash
python -m kau_can_bot refresh --max-pages 1000
```

Bu komut:

1. Siteyi ve aynı alan adındaki iç bağlantıları tarar.
2. Çıkarılan sayfa içeriklerini `data/pages.jsonl` dosyasına yazar.
3. Metinleri semantik parçalara ayırır.
4. Yerel TF-IDF embedding indeksi üretir ve `data/search_index.joblib` dosyasına kaydeder.

Varsayılan tarama kapsamı fakülte odaklıdır:

```bash
KAU_CRAWL_SCOPE=faculty
```

Bu kapsam İİBF ana sayfası, fakülte alt sayfaları, bölüm alt siteleri, duyurular,
haberler, etkinlikler, personel sayfaları ve fakülteyle ilişkili belge
bağlantılarını önceleyerek indeks gürültüsünü azaltır. Tüm `kafkas.edu.tr`
alan adına yayılmak istenirse `KAU_CRAWL_SCOPE=domain` kullanılabilir.

## Soru Sorma

```bash
python -m kau_can_bot ask "Fakültenin iletişim bilgileri nelerdir?"
```

Kurulumdan sonra kısa komut da kullanılabilir:

```bash
kau-can ask "Duyurular hakkında bilgi verir misiniz?"
```

## ChatGPT / OpenAI API Bağlantısı

Uygulama OpenAI Responses API ile çalışacak şekilde yapılandırılmıştır. API anahtarı verilirse yanıt metni ChatGPT/OpenAI modeliyle, yalnızca web sitesinden getirilen kaynak parçalarına dayanarak üretilir.

`.env` dosyasına şu değerleri ekleyin:

```bash
KAU_USE_OPENAI=true
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5-chat-latest
```

API anahtarı tanımlı değilse sistem yerel RAG özetleme yanıtına düşer.
API anahtarı tanımlı olup hesap kotası veya billing tarafında sorun varsa uygulama çalışmaya devam eder ve yerel RAG yanıtına döner.

## Ollama / Yerel Model Bağlantısı

Uygulama `KAU_LLM_PROVIDER=ollama` ayarıyla yerel Ollama servisini kullanabilir. Varsayılan yerel model `llama3.2` olarak ayarlanmıştır.

```bash
KAU_LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2
OLLAMA_HOST=http://127.0.0.1:11434
```

macOS üzerinde CLI doğrudan şu yoldan kullanılabilir:

```bash
/Applications/Ollama.app/Contents/Resources/ollama pull llama3.2
```

## API Olarak Çalıştırma

Önce indeks oluşturulmalıdır. Ardından:

```bash
uvicorn app:app --reload
```

Web arayüzü aynı sunucu üzerinde açılır:

```text
http://127.0.0.1:8000/
```

Örnek istek:

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Akademik personel bilgileri nelerdir?"}'
```

## Sorgu Öğrenme ve Geri Bildirim

Kullanıcı sorguları, çıkarılan anahtar kelimeler, bulunan kaynak URL'leri ve yanıt
durumu `logs/queries.jsonl` ve `logs/interactions.jsonl` dosyalarında saklanır.
Arayüzdeki yararlı/geliştirilmeli geri bildirimleri `logs/feedback.jsonl`
dosyasına yazılır.

Bu kayıtlar LLM ağırlıklarını yeniden eğitmez. Bunun yerine:

- sık sorulan konular izlenir,
- alan terimleriyle sorgu genişletme yapılır,
- hatalı/zayıf yanıtlar geri bildirim kayıtlarından analiz edilebilir,
- sistem web sitesi dışındaki bilgiyle yanıt üretmez.

Özet öğrenme durumu `/health` çıktısındaki `learning` alanında görülebilir.

## Docker

Tek uygulama imajını çalıştırmak için:

```bash
docker build -t kau-can-chat-bot .
docker run --rm -p 8000:8000 \
  -e KAU_LLM_PROVIDER=local \
  -e KAU_REFRESH_ON_START=true \
  kau-can-chat-bot
```

Ollama ve `llama3.2` modeliyle birlikte çalıştırmak için:

```bash
docker compose up --build
```

Servis açıldığında arayüz:

```text
http://127.0.0.1:8000/
```

## GitHub ve Canlıya Alma

Depoya CI ve Docker image workflow dosyaları eklenmiştir:

- `.github/workflows/ci.yml`: Python kurulum ve derleme kontrolü
- `.github/workflows/docker.yml`: `main` dalına push edildiğinde GHCR imajı üretir
- `.github/workflows/deploy-render.yml`: Render deploy hook secret'ı varsa canlı deploy tetikler

Render üzerinden canlıya almak için `render.yaml` hazırdır. GitHub reposu Render'a
bağlandıktan sonra `RENDER_DEPLOY_HOOK_URL` secret'ı eklenirse her `main` push'u
canlı deploy'u tetikler.

Bulut ortamında Ollama çalıştırılmayacaksa `KAU_LLM_PROVIDER=local` veya OpenAI
için `KAU_LLM_PROVIDER=openai` ve `OPENAI_API_KEY` kullanılmalıdır. Yerel/VPS
kurulumlarında `docker-compose.yml` Ollama servisini de ayağa kaldırır.

## Önemli Notlar

- Uygulama web sitesi dışındaki bilgilerle yanıt üretmez.
- Uygunsuz dil algılanırsa `Lütfen daha uygun bir dil kullanınız.` yanıtı döndürülür.
- Çok kısa veya belirsiz sorularda açıklayıcı bir soru sorulur.
- Güncel sonuçlar için site düzenli olarak yeniden taranmalıdır.
