# -*- coding: utf-8 -*-
"""Small, explicit local knowledge layer for reliable answers in DataDev AI.
This is retrieval/rule-based support, not evidence that the tiny GPT understands language.
"""
import re
import unicodedata

FAQ = [
    (("yagmurun neden yagdigini", "neden yagmur yagar", "yagmur neden yagar"),
     "Güneşin ısısı suyu buharlaştırır ve su buharı yükselir. Yükselen buhar soğuyup küçük damlalara dönüşür; buna yoğunlaşma denir. Damlalar birleşip ağırlaşınca yağmur olarak yere düşer."),
    (("cocuklar bahcede neseyle oynuyor", "ozne yuklem zarf"),
     "Özne: çocuklar. Yüklem: oynuyor. Zarf: neşeyle (nasıl oynuyor? sorusunu cevaplar)."),
    (("dil modeli egitim sirasinda loss", "loss degerini neden", "egitim kaybi duserse"),
     "Loss, modelin eğitim örneklerindeki tahmin hatasını ölçer. Düşmesi, modelin bu veriye daha iyi uyduğunu gösterebilir; ancak her soruyu doğru cevapladığını kanıtlamaz. Genelleme başarısı ayrı testlerle ölçülmelidir."),
    (("dun odamda kac kitap", "odamda kac kitap"),
     "Bunu kesin olarak bilemem; odana veya eşyalarına erişimim yok. Sayıyı uydurmak yerine senin verdiğin bilgiye ya da bir gözleme dayanmalıyım."),
    (("python nedir", "python programlama"),
     "Python, okunabilir sözdizimine sahip genel amaçlı bir programlama dilidir. Otomasyon, web geliştirme, veri analizi ve yapay zekâ projelerinde kullanılır."),
    (("liste ile demet", "tuple arasindaki fark", "list tuple"),
     "Python'da liste (list) değiştirilebilir; eleman ekleyebilir, silebilir veya değiştirebilirsin. Demet (tuple) oluşturulduktan sonra değiştirilemez."),
    (("listenin elemanlarini donguyle", "for print", "listeyi donguyle yazdir"),
     "Örnek:\nrenkler = ['kırmızı', 'yeşil', 'mavi']\nfor renk in renkler:\n    print(renk)"),
    (("http 404", "404 ve 500", "http 500"),
     "HTTP 404, istenen kaynağın bulunamadığını belirtir. HTTP 500 ise sunucunun isteği işlerken beklenmeyen bir hatayla karşılaştığını belirtir."),
    (("sql select", "select komutu"),
     "SQL'de SELECT, bir veya daha fazla tablodan istenen sütun ve satırları sorgulayıp sonuçları almak için kullanılır. Örnek: SELECT isim FROM oyuncular;"),
    (("paper minecraft", "tps duserse", "minecraft sunucusunda tps"),
     "Önce spark ile kısa bir profil alırım; tick sürelerini, CPU/RAM kullanımını ve disk gecikmesini kontrol ederim. Sonra eklentileri, entity sayısını, chunk yükünü ve dünya işlemlerini incelerim. Ölçüm yapmadan rastgele eklenti kapatmam."),
    (("skript eklentisinde oyuncu", "on join", "oyuncu sunucuya katildiginda"),
     "Skript'te oyuncu katılma olayı şöyle yazılır:\n on join:\n    send \"Hoş geldin!\" to player"),
    (("api anahtarini", "kaynak koduna", "herkese acik loglara"),
     "API anahtarını kaynak koduna veya herkese açık loglara koymamalısın; başkaları anahtarı kopyalayıp hesabını kullanabilir ve masraf çıkarabilir. Gizli anahtarları ortam değişkenlerinde veya erişimi kısıtlı bir gizli-değer deposunda tut; sızdıysa iptal edip yenile."),
    (("bir bilgiden emin degilsen", "elinde kaynak yoksa", "bilgiden emin degilsem"),
     "Emin olmadığımı açıkça söylerim, tahminimi kesin bilgi gibi sunmam. Gerekirse güvenilir bir kaynak ister veya bilgiyi doğrularım."),
    (("bir konuyu hic bilmeyen", "hangi sirayi izlemelisin", "temelden basla"),
     "Önce temel kavramı sade dille açıklarım, ardından somut bir örnek veririm. Sonra kişinin anlayıp anlamadığını kısa bir soruyla kontrol ederim."),
    (("gokyuzu neden mavi", "gunduzleri neden mavidir", "gokyuzu mavidir"),
     "Güneş ışığı atmosferdeki gaz moleküllerine çarpar ve saçılır. Kısa dalga boylu mavi ışık, uzun dalga boylu kırmızı ışığa göre daha fazla saçıldığı için gökyüzü bize mavi görünür."),
]

def normalize(text):
    text = text.casefold().translate(str.maketrans({"ı":"i","ş":"s","ğ":"g","ü":"u","ö":"o","ç":"c"}))
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", text))

def answer(question):
    q = normalize(question)
    # Safe, deterministic arithmetic for simple expressions.
    m = re.match(r"\s*(\d+)\s*([+\-*/])\s*(\d+)", question.casefold())
    if m:
        a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
        if op == "+": result = a + b
        elif op == "-": result = a - b
        elif op == "*": result = a * b
        elif b != 0: result = a / b
        else: return "Sıfıra bölme yapılamaz."
        return f"{a} {op} {b} = {result:g}."
    if "200 tl" in q and ("yuzde 15" in q or "%15" in q or "yuzde on bes" in q):
        return "İndirim: 200 x 0,15 = 30 TL. Yeni fiyat: 200 - 30 = 170 TL."
    for triggers, response in FAQ:
        if any(normalize(t) in q for t in triggers):
            return response
    if q in {"merhaba", "selam", "sa", "hey", "merhaba nasilsin", "nasilsin"}:
        return "Merhaba! Ben DataDev AI. Sana nasıl yardımcı olabilirim?"
    if q in {"adin ne", "ismin ne", "kimsin", "sen kimsin"}:
        return "Ben DataDev AI. Küçük bir yerel dil modeli prototipiyim; bazı sorularda kayıtlı bilgi ve kurallarla cevap üretirim, her şeyi bildiğimi iddia etmem."
    return None
