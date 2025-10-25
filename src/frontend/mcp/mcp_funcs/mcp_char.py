import random
import string


def get_random_chars(length: int = 5) -> str:
    """Get random characters"""
    chars = "".join(random.choices(string.ascii_letters, k=length))
    return f"Random chars: {chars}"
