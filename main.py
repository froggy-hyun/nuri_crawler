from src.crawler import NuriCrawler
from src.logger import get_logger

logger = get_logger("MAIN")

if __name__ == "__main__":
    crawler = NuriCrawler()
    crawler.run()