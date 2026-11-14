"""Conservative checks for empty input and standalone template placeholders.

This does not judge correctness, relevance, detail, or answer length.
"""
import re
import unicodedata


def no_content_reason(answer):
    text = unicodedata.normalize('NFKC', answer).strip()
    # Ignore Markdown/punctuation only when checking exact placeholder labels.
    compact = ''.join(char.lower() for char in text if char.isalnum())
    if not compact:
        return '回答只有空白或符號，沒有實質內容'
    labels = (
        r'(?:以下是|以下為)?(?:我的|本題的)?(?:測試用?|模擬)?(?:回答範例|範例回答|參考回答|示範回答|作答範例)',
        r'(?:以下是|以下為)(?:我的|本題的)?(?:測試用?|模擬)?(?:回答|作答)',
        r'請(?:在此|於此|輸入框內)?輸入(?:你的|您的|文字)?回答',
        r'(?:待補|待填|待填寫|待輸入|尚未作答|尚未回答)',
        r'(?:sampleanswer|exampleanswer|youranswerhere)',
        r'(?:嗯|呃|額|唔)+',
    )
    if any(re.fullmatch(pattern, compact) for pattern in labels):
        return '回答只有範例標籤、佔位文字或語助詞，沒有實質作答'
    return None
