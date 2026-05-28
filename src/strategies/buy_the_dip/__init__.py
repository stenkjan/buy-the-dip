from .config import BuyTheDipConfig
from .strategy import BuyTheDipStrategy

__all__ = ["BuyTheDipConfig", "BuyTheDipStrategy", "get_strategy"]


def get_strategy(config: BuyTheDipConfig | None = None) -> BuyTheDipStrategy:
    return BuyTheDipStrategy(config or BuyTheDipConfig())
