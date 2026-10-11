import re
import unicodedata

from .schema import Sentence

BOUNDARY = re.compile(r"[。；;!！?？\n]+|(?<!\d)\.(?=\s|$)")
POSSIBLE = re.compile(r"cannot\s+(?:exclude|rule out)|possible|suspect|疑似|考虑|不除外|不能排除|可疑", re.I)
NEGATIVE = re.compile(r"\bno\b|\bwithout\b|\babsent\b|\bnot seen\b|未见|未显示|无(?:明显)?", re.I)
HISTORICAL = re.compile(r"status post|\brepaired\b|\brepair\b|previous|history of|术后|修补|既往|封堵", re.I)
RESIDUAL = re.compile(r"\bresidual\b|\brecurrent\b|残余|仍见|复发", re.I)


def normalized(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def term_key(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", normalized(text))


def sentences(text: str) -> list[Sentence]:
    spans = []
    start = 0
    for match in BOUNDARY.finditer(text):
        spans.append((start, match.start()))
        start = match.end()
    spans.append((start, len(text)))
    result = []
    for left, right in spans:
        while left < right and text[left].isspace():
            left += 1
        while right > left and text[right - 1].isspace():
            right -= 1
        if right > left:
            result.append(Sentence(sentence_id=f"S{len(result) + 1}", text=text[left:right],
                                   start=left, end=right))
    return result


def qualification(text: str) -> tuple[str, str, str]:
    possible = bool(POSSIBLE.search(text))
    polarity = "negated" if not possible and NEGATIVE.search(text) else "affirmative"
    historical = bool(HISTORICAL.search(text)) and not RESIDUAL.search(text)
    return "possible" if possible else "definite", "historical" if historical else "current", polarity
