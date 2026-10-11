import re

DIRECT_IDENTIFIERS = (
    re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    re.compile(r"(?:姓名|患者姓名|身份证|住院号|门诊号|联系电话|patient\s+name|medical\s+record\s+number)\s*[:：]", re.I),
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?<!\d)[1-9]\d{16}[\dXx](?!\d)"),
)


def check_text(text: str) -> None:
    if any(pattern.search(text) for pattern in DIRECT_IDENTIFIERS):
        raise ValueError("possible direct identifier detected; de-identify the input locally")
