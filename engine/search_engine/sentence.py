import re
import os
from tqdm import tqdm
import json
from datetime import datetime

def clean_text(text):
    # Replace \n and \t with a space
    text = text.replace('\n', ' ').replace('\t', ' ')
    # Replace multiple spaces with a single space
    text = re.sub(r'\s+', ' ', text)
    # Strip leading/trailing whitespace
    return text.strip()

def extract_main_body(text):
    """
    Yargıtay karar metninden 'İçtihat Metni' veya benzeri sinyaller sonrası karar gövdesini çıkarır.
    """
    lines = text.splitlines()
    main_body_started = False
    main_body_lines = []

    # Bazı kararlar "İçtihat Metni" gibi işaretlerle başlar, bunu kullan
    for i, line in enumerate(lines):
        if not main_body_started:
            # Başlangıç sinyali arıyoruz
            if "İçtihat Metni" in line or "İçtihat" in line:
                main_body_started = True
                continue
        else:
            # Karar gövdesi satırları
            main_body_lines.append(line)

    # Eğer yukarıdaki sinyalleri bulamadıysa, fallback olarak büyük harfli metadata'ları kullan
    if not main_body_lines:
        metadata_line_indices = []
        for i, line in enumerate(lines):
            if re.match(r'^[A-ZÇĞİÖŞÜ\s]+:\s*.*$', line.strip()):
                metadata_line_indices.append(i)
        if metadata_line_indices:
            last_metadata_index = metadata_line_indices[-1]
            main_body_lines = lines[last_metadata_index + 1:]
        else:
            main_body_lines = lines  # en kötü ihtimal tüm metni ver

    return "\n".join(main_body_lines).strip()

def custom_sentence_tokenize(text):
    # Satır sonlarını düzle
    text = re.sub(r'\s*\n\s*', ' ', text)

    # Cümle içinde nokta taşıyan ama bölünmemesi gereken kısaltmalar
    abbreviations = [
        "Av.", "Dr.", "Prof.", "Sn.", "Mr.", "Mrs.", "Ms.", "Mah.", "Ltd", "Şti", "Tic", "Müh."
        "Ltd.", "Şti.", "Stj.", "Doç.", "Yrd.", "İnş.", "San.", "Tic."
        "İth.", "İhr.", "A.Ş.", "K.D.V.", "vs.", "vb.", "Elk.", "Hiz.", "Nak.", "Teks.", "Öz."
    ]

    # Kısaltmaları geçici olarak koruma altına al
    placeholder_map = {}
    for i, abbr in enumerate(abbreviations):
        placeholder = f"<<ABBR_{i}>>"
        text = text.replace(abbr, placeholder)
        placeholder_map[placeholder] = abbr

    # Küçük harf ve nokta ardından büyük harfle başlayan yerlerde böl
    pattern = r'(?<=[a-zçğıöşü])\.(?=\s+[A-ZÇĞİÖŞÜ])'
    sentences = re.split(pattern, text)

    # Fazla boşlukları temizle
    sentences = [s.strip() for s in sentences if s.strip()]

    # Kısaltmaları geri getir
    restored_sentences = []
    for s in sentences:
        for placeholder, abbr in placeholder_map.items():
            s = s.replace(placeholder, abbr)
        restored_sentences.append(s)

    return restored_sentences

def merge_short_sentences(sentences, min_length=20):
    merged = []
    i = 0
    while i < len(sentences):
        if len(sentences[i]) < min_length:
            prev = merged.pop() if merged else ''
            curr = sentences[i]
            next_ = sentences[i+1] if i + 1 < len(sentences) else ''
            merged.append(f"{prev}. {curr}. {next_}.".strip())
            i += 2  # çünkü next_ cümlesi de işlenmiş oldu
        else:
            merged.append(sentences[i])
            i += 1
    return merged

def add_constant_to_strings(strings, constant):
    return [(s, constant) for s in strings]

if __name__ == "__main__":

    court_path = "./courts"
    output_path = "./courts_sentence.jsonl"

    for file in tqdm(os.listdir(court_path)):
        if ".txt" in file:
            with open(os.path.join(court_path, file), "r", encoding="utf-8") as f:
                text = f.read()
                body = extract_main_body(text)
                body = clean_text(body)
                sentences = custom_sentence_tokenize(body)
                sentences = merge_short_sentences(sentences)
                sentences = add_constant_to_strings(sentences, file)

            with open(output_path, "a", encoding="utf-8") as out_f:
                for sentence, filename in sentences[:-1]:
                    item = {
                        "sentence": sentence,
                        "file": filename
                    }
                    out_f.write(json.dumps(item, ensure_ascii=False) + "\n")



