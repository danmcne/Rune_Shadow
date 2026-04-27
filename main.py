"""
Rune & Shadow – Entry Point
Run:  python main.py
      python main.py 99999   (custom seed)
"""
import sys
import pygame
from constants import SCREEN_WIDTH, SCREEN_HEIGHT, FPS, TITLE
from game import Game


def main():
    seed = 12345
    if len(sys.argv) > 1:
        try:
            seed = int(sys.argv[1])
        except ValueError:
            print(f"Invalid seed {sys.argv[1]!r}, using default.")

    pygame.init()
    pygame.font.init()

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(TITLE)
    clock  = pygame.time.Clock()

    game = Game(screen, clock, seed=seed)
    game.run()


if __name__ == "__main__":
    main()
