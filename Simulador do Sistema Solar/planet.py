# planet.py
import math
import os
import unicodedata
import pygame


def clamp(value, vmin, vmax):
    return max(vmin, min(vmax, value))


def hex_to_rgb(hex_color: str):
    """Converte cor #RRGGBB para (R, G, B) em 0-255."""
    hex_color = hex_color.strip()
    if hex_color.startswith("#"):
        hex_color = hex_color[1:]
    if len(hex_color) != 6:
        return (255, 255, 255)
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (r, g, b)


# pasta das imagens (mesmo nível que main.py / planet.py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE_DIR, "img")


def _normalize_name_for_file(name: str) -> list[str]:
    """
    Remove acentos e espaços para montar possíveis nomes de arquivos.
    Ex.: "Mercúrio" -> ["Mercurio.png", "mercurio.png", "MERCURIO.png"]
    """
    n = name.strip()

    # tira acentos
    n = unicodedata.normalize("NFKD", n)
    n = "".join(c for c in n if not unicodedata.combining(c))

    # tira espaços
    n = n.replace(" ", "").replace("\t", "")

    return [
        f"{n}.png",
        f"{n.lower()}.png",
        f"{n.capitalize()}.png",
        f"{n.upper()}.png",
    ]


class Planet:
    def __init__(
        self,
        name: str,
        radius_km: float,
        a_au: float,
        period_days: float,
        color_hex: str,
        draw_orbit: bool = True,
        fact: str = "",
        parent_name: str | None = None,
    ):
        self.planet_name = name
        self.radius_km = float(radius_km)
        self.a_au = float(a_au)
        self.period_days = float(period_days)
        self.color = hex_to_rgb(color_hex)
        self.draw_orbit = draw_orbit
        self.fact = fact or ""

        # órbita / escala
        self.angle = 0.0
        self.radius_px = 5.0
        self.au_to_px = 1000.0
        self.time_scale = 20000.0
        self.position = pygame.Vector2(0.0, 0.0)

        # sistema de satélites
        self.parent_name = parent_name
        self.parent: "Planet | None" = None

        # imagem (sprite) do planeta
        self.image: pygame.Surface | None = None
        self._load_image_if_available()

    # ---------- imagem ----------

    def _load_image_if_available(self):
        """Tenta carregar uma imagem PNG na pasta img/ com o nome do planeta."""
        candidates = _normalize_name_for_file(self.planet_name)
        for filename in candidates:
            path = os.path.join(IMG_DIR, filename)
            if os.path.exists(path):
                try:
                    img = pygame.image.load(path).convert_alpha()
                    self.image = img
                    print(f"[Planet] Usando imagem para {self.planet_name}: {filename}")
                    return
                except Exception as e:
                    print(f"[Planet] Erro ao carregar {path}: {e}")
        # se não achar nada, fica None e usa bolinha
        print(f"[Planet] Sem imagem para {self.planet_name}, usando círculo.")

    # ---------- escala / órbita ----------

    def set_visual_scale(
        self,
        radius_px_min: float,
        radius_px_max: float,
        radius_scale: float,
        au_to_px: float
    ):
        """
        radius_scale é um fator linear em km → px.
        Como usamos o raio em km real, as proporções entre planetas
        já ficam fisicamente corretas. Ajustamos só min/max.
        """
        self.au_to_px = au_to_px
        # escala linear: km * fator → px (proporções reais entre raios)
        raw_px = self.radius_km * radius_scale
        self.radius_px = clamp(raw_px, radius_px_min, radius_px_max)

    def update_position(self, delta: float):
        """
        Se não tiver pai -> orbita (0,0).
        Se tiver pai     -> orbita em volta do pai (ex.: Lua em volta da Terra).
        """
        if self.period_days <= 0.0 or self.a_au <= 0.0:
            if self.parent is None:
                self.position.update(0.0, 0.0)
            else:
                self.position = self.parent.position.copy()
            return

        T_real = self.period_days * 86400.0
        if T_real == 0:
            return

        omega = (2.0 * math.pi * self.time_scale) / T_real
        self.angle = (self.angle + omega * delta) % (2.0 * math.pi)

        r = self.a_au * self.au_to_px
        rel_x = math.cos(self.angle) * r
        rel_y = math.sin(self.angle) * r

        if self.parent is None:
            self.position.x = rel_x
            self.position.y = rel_y
        else:
            self.position.x = self.parent.position.x + rel_x
            self.position.y = self.parent.position.y + rel_y

    # ---------- desenho ----------

    def draw(self, surface, camera, font):
        screen_w, screen_h = surface.get_size()
        center = pygame.Vector2(screen_w / 2, screen_h / 2)

        screen_pos = (self.position - camera.position) * camera.zoom + center
        radius_on_screen = max(1, int(self.radius_px * camera.zoom))

        # centro da órbita (Sol ou pai)
        if self.draw_orbit and self.a_au > 0.0:
            if self.parent is None:
                orbit_center_world = pygame.Vector2(0.0, 0.0)
            else:
                orbit_center_world = self.parent.position

            orbit_center_screen = (orbit_center_world - camera.position) * camera.zoom + center
            orbit_radius = int(self.a_au * self.au_to_px * camera.zoom)
            if orbit_radius > 0:
                pygame.draw.circle(
                    surface,
                    (255, 255, 255),
                    (int(orbit_center_screen.x), int(orbit_center_screen.y)),
                    orbit_radius,
                    width=1
                )

        # planeta: usa imagem se tiver, senão bolinha
        if self.image is not None:
            # fator de correção visual por planeta (Lua bem menor, etc.)
            scale_factor = 1.0
            name_lower = self.planet_name.lower()

            # Lua ~40% do raio da Terra
            if name_lower in ("lua", "moon"):
                scale_factor = 0.4

            # diâmetro em pixels na tela
            diameter = max(4, int(self.radius_px * 2 * camera.zoom * scale_factor))
            sprite = pygame.transform.smoothscale(self.image, (diameter, diameter))
            rect = sprite.get_rect(center=(screen_pos.x, screen_pos.y))
            surface.blit(sprite, rect)
        else:
            # bolinha colorida
            pygame.draw.circle(
                surface,
                self.color,
                (int(screen_pos.x), int(screen_pos.y)),
                radius_on_screen
            )
            pygame.draw.circle(
                surface,
                (0, 0, 0),
                (int(screen_pos.x), int(screen_pos.y)),
                radius_on_screen,
                width=1
            )

        # nome do planeta
        if font is not None:
            label_surf = font.render(self.planet_name, True, (255, 255, 255))
            label_rect = label_surf.get_rect()
            label_rect.center = (screen_pos.x, screen_pos.y - radius_on_screen - 15)
            surface.blit(label_surf, label_rect)

    # ---------- clique ----------

    def is_clicked(self, mouse_pos, camera, click_tolerance=1.2):
        screen_w, screen_h = pygame.display.get_surface().get_size()
        center = pygame.Vector2(screen_w / 2, screen_h / 2)

        screen_pos = (self.position - camera.position) * camera.zoom + center
        radius_on_screen = self.radius_px * camera.zoom * click_tolerance

        mouse_vec = pygame.Vector2(mouse_pos)
        dist = mouse_vec.distance_to(screen_pos)
        return dist <= radius_on_screen
