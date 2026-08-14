"""Russian -> English furniture lexicon for hybrid retrieval.

Why this exists: the catalogue text extracted from the price lists is English, so a
MongoDB text search for «обеденный стол» matches nothing, and the distilled
multilingual CLIP encoder aligns some Russian nouns only weakly. Translating the
query's domain vocabulary lets an exact keyword signal ride alongside the vector
score, which forces the right category to the top while embeddings still handle
the semantic / visual fallback.

Keys are stems (prefix match) so Russian declensions resolve:
«диван», «дивана», «диваны», «диванов» -> sofa.
"""
import re

RU_STEMS = {
    # ---- furniture types ----
    "диван": ["sofa", "settee"],
    "кушетк": ["daybed", "chaise"],
    "шезлонг": ["chaise", "longue"],
    "кресл": ["armchair", "chair"],
    "стул": ["chair"],
    "табурет": ["stool"],
    "пуф": ["pouf", "ottoman", "footstool"],
    "банкетк": ["bench"],
    "скамь": ["bench"],
    "кроват": ["bed"],
    "матрас": ["mattress"],
    "изголов": ["headboard"],
    "стол": ["table"],
    "столик": ["table", "coffee"],
    "столешниц": ["worktop", "top"],
    "шкаф": ["wardrobe", "cabinet", "cupboard"],
    "гардероб": ["dressing", "wardrobe", "walk-in"],
    "комод": ["chest", "drawers", "sideboard"],
    "буфет": ["sideboard", "cupboard"],
    "витрин": ["display", "showcase", "glass"],
    "стеллаж": ["shelving", "bookcase", "system"],
    "полк": ["shelf", "shelves"],
    "книжн": ["bookcase"],
    "ящик": ["drawer", "drawers"],
    "двер": ["door", "doors"],
    "фасад": ["front", "door"],
    "панел": ["panel", "panels"],
    "перегородк": ["partition", "divider"],
    "зеркал": ["mirror"],
    "светильник": ["lamp", "light"],
    "коврик": ["rug", "carpet"],
    "ковер": ["rug", "carpet"],
    "вешалк": ["coat", "hanger", "rail"],
    "тумб": ["cabinet", "nightstand", "unit"],
    "мойк": ["sink"],
    "смесител": ["tap", "mixer"],
    "вытяжк": ["hood"],
    "варочн": ["hob", "cooktop"],
    "духов": ["oven"],
    "остров": ["island"],
    "фартук": ["backsplash", "splashback"],
    "корпус": ["carcass", "structure", "unit"],
    "модул": ["module", "modular", "unit"],
    "секци": ["section", "element"],
    "элемент": ["element"],
    "цокол": ["plinth", "base"],
    "опор": ["leg", "support", "feet"],
    "ножк": ["leg", "feet"],
    # ---- rooms / usage ----
    "кухн": ["kitchen"],
    "кухон": ["kitchen"],
    "спальн": ["bed", "sleeping", "night"],
    "гостин": ["living"],
    "обеден": ["dining"],
    "прихож": ["entrance", "hall"],
    "ванн": ["bathroom", "bath"],
    "офис": ["office", "desk"],
    "кабинет": ["office", "desk", "study"],
    "письмен": ["desk", "writing"],
    "журнальн": ["coffee"],
    "барн": ["bar"],
    "детск": ["children", "kids"],
    # ---- materials / finishes ----
    "кож": ["leather", "hide"],
    "ткан": ["fabric", "textile"],
    "тканев": ["fabric"],
    "велюр": ["velvet"],
    "дуб": ["oak"],
    "орех": ["walnut"],
    "ясен": ["ash"],
    "клен": ["maple"],
    "дерев": ["wood", "woods", "wooden"],
    "шпон": ["veneer"],
    "лак": ["lacquer", "lacquered"],
    "глянц": ["glossy", "gloss"],
    "матов": ["matt", "mat"],
    "мрамор": ["marble"],
    "камен": ["stone"],
    "керамик": ["ceramic"],
    "стекл": ["glass"],
    "металл": ["metal", "metallic"],
    "сталь": ["steel"],
    "латун": ["brass"],
    "бронз": ["bronze"],
    "алюмин": ["aluminium"],
    "плетен": ["woven", "wicker"],
    "бетон": ["concrete"],
    # ---- attributes ----
    "угловой": ["corner"],
    "углов": ["corner"],
    "раскладн": ["folding", "extendable"],
    "раздвижн": ["sliding"],
    "подъемн": ["lifting", "lift"],
    "навесн": ["wall", "hanging", "suspended"],
    "настен": ["wall"],
    "напольн": ["floor"],
    "встроен": ["built-in", "integrated"],
    "открыт": ["open"],
    "закрыт": ["closed"],
    "круглый": ["round"],
    "кругл": ["round"],
    "овальн": ["oval"],
    "прямоугольн": ["rectangular"],
    "квадратн": ["square"],
    "высок": ["high", "tall"],
    "низк": ["low"],
    "широк": ["wide"],
    "глубин": ["depth"],
    "ширин": ["width"],
    "высот": ["height"],
    "размер": ["size", "dimension"],
    "цена": ["price"],
}

RU_STOP = {"из", "для", "с", "со", "и", "в", "на", "по", "или", "а", "от", "до",
           "the", "of", "with", "for", "and", "in", "on", "a", "an"}

_STEMS = sorted(RU_STEMS.items(), key=lambda kv: -len(kv[0]))


def translate_query(q):
    """Return (english_terms, matched_ru_tokens)."""
    toks = re.findall(r"[\w\-]+", (q or "").lower(), flags=re.UNICODE)
    terms, matched = [], []
    for t in toks:
        if t in RU_STOP or len(t) < 2:
            continue
        if re.search(r"[\u0400-\u04FF]", t):
            hit = None
            # longest stem first, prefix match only - Russian declensions append
            # suffixes, so t.startswith(stem) is both sufficient and safe.
            # (A reverse 'stem.startswith(t)' fallback was tried and removed: it
            # mapped «стол» onto «столешниц» -> worktop instead of table.)
            for stem, eng in _STEMS:
                if t.startswith(stem):
                    hit = eng
                    break
            if hit:
                terms.extend(hit)
                matched.append(t)
        else:
            terms.append(t)
    seen, out = set(), []
    for t in terms:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out, matched
