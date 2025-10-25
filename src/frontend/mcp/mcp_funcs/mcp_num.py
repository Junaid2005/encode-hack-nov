import random


def get_random_number() -> str:
    """Get a random number"""
    number = random.randint(1, 100)
    return f"Random number: {number}"
