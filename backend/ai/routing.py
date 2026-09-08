"""Conservative, free task classification; models remain server-owned."""
import re


def classify(prompt):
    text = prompt.lower()
    if re.search(r'\b(code|coding|debug|python|javascript|typescript|sql|algorithm|api)\b', text):
        return 'coding'
    if re.search(r'\b(reason|reasoning|trade-offs|tradeoffs|analyse|analyze|compare|proof)\b', text):
        return 'reasoning'
    if re.search(r'\b(article|essay|chapter|long|story|writing)\b', text):
        return 'writing'
    return 'default'


class AIRouter:
    def __init__(self, settings):
        self.settings = settings

    def select(self, prompt):
        return self.settings.routes.get(classify(prompt), self.settings.routes['default'])
