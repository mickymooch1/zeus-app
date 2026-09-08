"""Conservative reservation, actual-usage settlement; USD rate per Hub credit."""
import math

from .config import COUNCIL_BETA_RESERVE_CREDITS


def cost(model, input_tokens, output_tokens):
    return (input_tokens * model.input_per_million + output_tokens * model.output_per_million) / 1_000_000


def credits(settings, usd, feature):
    multiplier = settings.council_multiplier if feature == 'council' else 1
    return math.ceil(usd * multiplier / settings.credit_usd) if usd > 0 else 0


def input_bound(messages):
    # One token per UTF-8 byte plus generous role/framing overhead. No tools/images.
    return sum(len(m['content'].encode('utf-8')) + 128 for m in messages) + 512


def quote(settings, feature, messages, selected):
    if feature == 'ask':
        model = settings.models[selected]
        usd = cost(model, input_bound(messages), model.max_output_tokens)
    else:
        usd = sum(cost(settings.models[n], input_bound(messages), settings.models[n].max_output_tokens) for n in settings.members)
        # Each final response is byte-capped by the adapter before synthesis.
        # JSON control-character escaping can expand a byte to six ASCII bytes.
        judge_input = input_bound(messages) + sum(settings.models[n].max_output_tokens * 8 * 6 + 512 for n in settings.members) + 2048
        model = settings.models[settings.judge]
        usd += cost(model, judge_input, model.max_output_tokens)
        if settings.mode == 'beta':
            # Private Council beta: fixed reservation, not the dollar-derived
            # amount — settlement charges a fixed 15/12 too (service.execute).
            return {'credits': COUNCIL_BETA_RESERVE_CREDITS, 'estimated_cost': usd}
    return {'credits': max(1, credits(settings, usd, feature)), 'estimated_cost': usd}
