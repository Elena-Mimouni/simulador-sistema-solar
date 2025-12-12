# main.py
import json
import os
import pygame
import asyncio

from planet import Planet
from camera import Camera

# Em ambiente web (pygbag), caminhos relativos são mais seguros
DATA_FILE = "planets.json"

# Constantes globais
AU_TO_PX = 3000.0

# Escala de tamanho mais realista:
# raio_em_px = radius_km * RADIUS_SCALE
# Ex.: Terra ~6371 km → ~6.3 px (antes do zoom)
RADIUS_SCALE = 0.001
RADIUS_MIN = 1.0
RADIUS_MAX = 120.0
TIME_SCALE = 30000.0


def load_solar_system():
    """Carrega os planetas do JSON e cria os objetos Planet."""
    bodies = []

    print("Carregando JSON de:", DATA_FILE)
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            arr = json.load(f)
    except Exception as e:
        print(f"\n❌ ERRO ao abrir ou ler {DATA_FILE}: {e}")
        return []

    # 1ª passada: cria todos os planetas / satélites
    for d in arr:
        try:
            name = d.get("name", "")
            radius_km = float(d.get("radius_km", 0.0))
            a_au = float(d.get("a_au", 0.0))
            period_days = float(d.get("period_days", 0.0))
            color = str(d.get("color", "#FFFFFF"))
            fact = d.get("fact", "")
            parent_name = d.get("parent_name")  # pode ser None
        except Exception as e:
            print(f"[ERRO] Problema ao ler entrada do JSON: {d} -> {e}")
            continue

        planet = Planet(
            name=name,
            radius_km=radius_km,
            a_au=a_au,
            period_days=period_days,
            color_hex=color,
            draw_orbit=a_au > 0.0,
            fact=fact,
            parent_name=parent_name,
        )
        planet.time_scale = TIME_SCALE
        planet.set_visual_scale(RADIUS_MIN, RADIUS_MAX, RADIUS_SCALE, AU_TO_PX)

        # posição inicial aproximada
        if planet.a_au <= 0:
            planet.position.update(0.0, 0.0)
        else:
            planet.position.update(planet.a_au * AU_TO_PX, 0.0)

        bodies.append(planet)

    print(f"[Main] Planetas carregados: {len(bodies)}")

    # 2ª passada: liga cada planeta ao seu "pai" (ex.: Lua → Terra)
    by_name = {p.planet_name: p for p in bodies}
    for p in bodies:
        if getattr(p, "parent_name", None):
            parent = by_name.get(p.parent_name)
            if parent:
                p.parent = parent
            else:
                print(f"[AVISO] parent_name '{p.parent_name}' não encontrado para '{p.planet_name}'")

    # Atualizar pais antes de filhos (Sol/Terra antes da Lua)
    bodies.sort(key=lambda p: 0 if getattr(p, "parent", None) is None else 1)

    return bodies


def reorder_bodies_for_buttons(bodies):
    """
    Garante que a Lua venha imediatamente depois da Terra nos botões.
    Mantém a ordem original dos outros planetas.
    """
    earth = None
    moon = None

    for b in bodies:
        if b.planet_name.lower() in ("terra", "earth"):
            earth = b
        elif b.planet_name.lower() in ("lua", "moon"):
            moon = b

    if earth is None or moon is None:
        return bodies

    new_list = []
    added_moon = False

    for b in bodies:
        if b == earth:
            new_list.append(b)
            new_list.append(moon)
            added_moon = True
        elif b == moon:
            if not added_moon:
                new_list.append(b)
        else:
            new_list.append(b)

    return new_list


def get_focus_zoom_for_planet(planet):
    """
    Define o nível de zoom automático quando a câmera foca em um planeta
    a partir dos botões da barra inferior.
    """
    name = planet.planet_name.lower()

    # Sol
    if "sol" in name or "sun" in name:
        return 2.0

    # Júpiter e Saturno
    if "júpiter" in name or "jupiter" in name:
        return 3.0
    if "saturno" in name or "saturn" in name:
        return 3.2

    # Pequenos: Mercúrio, Lua
    if "mercúrio" in name or "mercurio" in name or "mercury" in name:
        return 6.0
    if "lua" in name or "moon" in name:
        return 6.5

    # Demais (Terra, Marte, Vênus, Urano, Netuno…)
    return 5.0


def wrap_text(text, font, max_width):
    """Quebra texto em linhas para caber na largura max_width."""
    words = text.split()
    lines = []
    current_line = ""

    for w in words:
        test_line = current_line + (" " if current_line else "") + w
        width, _ = font.size(test_line)
        if width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = w

    if current_line:
        lines.append(current_line)
    return lines


def draw_planet_info_box(screen, planet, camera, font_title, font_text):
    """Desenha a caixinha de informação ao lado do planeta selecionado."""
    if planet is None or not planet.fact:
        return

    screen_w, screen_h = screen.get_size()
    center = pygame.Vector2(screen_w / 2, screen_h / 2)

    planet_screen_pos = (planet.position - camera.position) * camera.zoom + center

    title = planet.planet_name
    fact_text = planet.fact

    max_box_width = 320
    padding = 10
    OFFSET_X = 60  # caixinha um pouco mais à direita

    title_surf = font_title.render(title, True, (255, 255, 255))
    title_w, title_h = title_surf.get_size()

    lines = wrap_text(fact_text, font_text, max_box_width - 2 * padding)
    line_surfs = [font_text.render(line, True, (230, 230, 230)) for line in lines]
    line_height = font_text.get_height()

    content_height = title_h + 8 + len(line_surfs) * line_height
    box_width = max(title_w, max((s.get_width() for s in line_surfs), default=0)) + 2 * padding
    box_height = content_height + 2 * padding

    box_x = planet_screen_pos.x + OFFSET_X
    box_y = planet_screen_pos.y - box_height / 2

    # Mantém dentro da tela
    if box_x + box_width > screen_w - 10:
        box_x = planet_screen_pos.x - box_width - OFFSET_X
    if box_x < 10:
        box_x = 10
    if box_y < 10:
        box_y = 10
    if box_y + box_height > screen_h - 10:
        box_y = screen_h - box_height - 10

    box_rect = pygame.Rect(int(box_x), int(box_y), int(box_width), int(box_height))
    box_surface = pygame.Surface((box_rect.width, box_rect.height), pygame.SRCALPHA)
    box_surface.fill((10, 10, 40, 200))  # fundo semi-transparente

    pygame.draw.rect(box_surface, (255, 255, 255), box_surface.get_rect(), width=1)

    y = padding
    box_surface.blit(title_surf, (padding, y))
    y += title_h + 8

    for s in line_surfs:
        box_surface.blit(s, (padding, y))
        y += line_height

    screen.blit(box_surface, box_rect.topleft)


def build_planet_buttons(bodies, screen_width, screen_height, font):
    """Cria um botão retangular para cada planeta na parte inferior da tela."""
    margin = 10
    button_height = 36
    y = screen_height - button_height - margin

    n = len(bodies)
    if n == 0:
        return []

    available_width = screen_width - 2 * margin
    button_width = max(80, int((available_width - (n - 1) * margin) / n))

    buttons = []
    x = margin

    for p in bodies:
        rect = pygame.Rect(int(x), int(y), int(button_width), int(button_height))
        buttons.append({"planet": p, "rect": rect})
        x += button_width + margin

    return buttons


def draw_planet_buttons(screen, buttons, font, selected_planet):
    """Desenha a barra de botões com o nome de cada planeta."""
    for btn in buttons:
        rect = btn["rect"]
        planet = btn["planet"]

        is_selected = (planet == selected_planet)
        bg_color = (60, 60, 140) if is_selected else (30, 30, 80)
        border_color = (200, 200, 255)
        text_color = (255, 255, 255)

        pygame.draw.rect(screen, bg_color, rect, border_radius=6)
        pygame.draw.rect(screen, border_color, rect, width=1, border_radius=6)

        label_surf = font.render(planet.planet_name, True, text_color)
        label_rect = label_surf.get_rect(center=rect.center)
        screen.blit(label_surf, label_rect)


def draw_tiled_background(screen, camera, bg_image):
    """
    Desenha o background repetido (tiling), acompanhando o pan.
    O fundo não é escalado pelo zoom (parece um céu muito distante).
    """
    if bg_image is None:
        screen.fill((5, 5, 20))
        return

    screen_w, screen_h = screen.get_size()
    bg_w, bg_h = bg_image.get_size()

    # paralaxe suave: o fundo se move mais devagar que os planetas
    PARALLAX = 0.1
    offset_x = int(-camera.position.x * PARALLAX) % bg_w
    offset_y = int(-camera.position.y * PARALLAX) % bg_h

    for x in range(-bg_w, screen_w + bg_w, bg_w):
        for y in range(-bg_h, screen_h + bg_h, bg_h):
            screen.blit(bg_image, (x + offset_x, y + offset_y))


async def main():
    pygame.init()
    pygame.display.set_caption("Simulador do Sistema Solar (escala aproximada)")

    screen_width, screen_height = 1280, 720
    screen = pygame.display.set_mode((screen_width, screen_height))

    clock = pygame.time.Clock()

    # Fontes: Font(None, size) é mais seguro em ambiente web do que SysFont
    font = pygame.font.Font(None, 18)
    info_font = pygame.font.Font(None, 20)
    title_font = pygame.font.Font(None, 22)
    text_font = pygame.font.Font(None, 18)
    button_font = pygame.font.Font(None, 18)

    # Carrega o background de estrelas (caminho relativo simples)
    bg_path = os.path.join("img", "background.png")
    try:
        bg_image = pygame.image.load(bg_path).convert()
        print(f"[Main] Background carregado: {bg_path}")
    except Exception as e:
        print(f"[Main] ERRO ao carregar background ({bg_path}): {e}")
        bg_image = None

    # max_zoom maior para chegar bem perto, min_zoom bem pequeno p/ ver o sistema inteiro
    cam = Camera(min_zoom=0.0015, max_zoom=10.0, zoom_sensitivity=1.0)
    cam.position.update(0.0, 0.0)
    cam.zoom = 1.0

    bodies = load_solar_system()
    bodies = reorder_bodies_for_buttons(bodies)

    selected_planet = None
    follow_planet = None
    camera_locked_to_planet = False

    buttons = build_planet_buttons(bodies, screen_width, screen_height, button_font)

    info_text = (
        f"Escalas — Distância: {AU_TO_PX:.0f} px/AU | "
        f"Tamanho: {RADIUS_SCALE:.4f} px/km | "
        f"Tempo: x{TIME_SCALE:.0f}  "
        f"Pan: botão direito/1 dedo + arrastar | Zoom: scroll/pinch | "
        f"Clique no planeta ou nos botões abaixo"
    )

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # camera (mouse + touch)
            cam.handle_event(event)

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = event.pos

                # 1) Verifica se clicou em algum botão
                clicked_button = None
                for btn in buttons:
                    if btn["rect"].collidepoint(mouse_pos):
                        clicked_button = btn
                        break

                if clicked_button is not None:
                    selected_planet = clicked_button["planet"]
                    follow_planet = selected_planet
                    camera_locked_to_planet = True

                    # Zoom específico para cada planeta
                    desired_zoom = get_focus_zoom_for_planet(selected_planet)
                    cam.zoom = max(cam.min_zoom, min(cam.max_zoom, desired_zoom))

                    # Centraliza na posição atual do planeta
                    cam.position = follow_planet.position.copy()

                else:
                    # 2) Clique direto no planeta (centraliza mas NÃO trava)
                    clicked_planet = None
                    for p in bodies:
                        if p.is_clicked(mouse_pos, cam):
                            clicked_planet = p
                            break
                    selected_planet = clicked_planet
                    if clicked_planet is not None:
                        follow_planet = None
                        camera_locked_to_planet = False
                        cam.position = clicked_planet.position.copy()

        # Se estava travada em planeta e o jogador começou a dar pan, destrava
        if camera_locked_to_planet and cam.is_dragging:
            camera_locked_to_planet = False
            follow_planet = None

        # Atualiza planetas
        for p in bodies:
            p.update_position(dt)

        # Se está travada em planeta, acompanha ele
        if camera_locked_to_planet and follow_planet is not None:
            cam.position = follow_planet.position.copy()

        # Desenho
        draw_tiled_background(screen, cam, bg_image)

        # Se não carregou nenhum planeta, mostra mensagem em vez de tela preta
        if len(bodies) == 0:
            msg1 = "Nenhum planeta carregado."
            msg2 = "Verifique se 'planets.json' está no mesmo diretório que main.py"
            msg3 = "e se ele foi incluído no build do pygbag."

            text1 = info_font.render(msg1, True, (255, 200, 200))
            text2 = text_font.render(msg2, True, (255, 255, 255))
            text3 = text_font.render(msg3, True, (255, 255, 255))

            screen.blit(text1, (40, 80))
            screen.blit(text2, (40, 110))
            screen.blit(text3, (40, 140))
        else:
            for p in bodies:
                p.draw(screen, cam, font)

            draw_planet_info_box(screen, selected_planet, cam, title_font, text_font)
            draw_planet_buttons(screen, buttons, button_font, selected_planet)

        info_surface = info_font.render(info_text, True, (255, 255, 255))
        screen.blit(info_surface, (16, 16))

        pygame.display.flip()

        await asyncio.sleep(0)

    pygame.quit()

if __name__ == "__main__":
    asyncio.run(main())
