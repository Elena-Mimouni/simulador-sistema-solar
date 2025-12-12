import pygame


class Camera:
    """
    Câmera com pan e zoom.

    - Mouse:
        Pan: botão direito + arrastar
        Zoom: scroll
    - Touch (tela sensível ao toque):
        1 dedo: pan
        2 dedos: pinch-zoom
    """

    def __init__(self, min_zoom=0.0015, max_zoom=20.0, zoom_sensitivity=1.0):
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        self.zoom_sensitivity = zoom_sensitivity

        self.position = pygame.Vector2(0.0, 0.0)  # posição no "mundo"
        self.zoom = 1.0

        # Pan via mouse
        self.pan_enabled = True
        self._dragging = False
        self._last_mouse_pos = pygame.Vector2(0.0, 0.0)

        # Pan/zoom via touch
        self.touches: dict[int, pygame.Vector2] = {}  # finger_id -> pos tela
        self.last_pinch_dist: float | None = None

        # flag pública usada no main para saber se o jogador está "arrastando"
        self.is_dragging = False

    # -----------------------
    # Utilitários internos
    # -----------------------

    def _screen_size(self):
        surf = pygame.display.get_surface()
        if surf is None:
            return 1, 1
        return surf.get_size()

    def _apply_zoom_around_point(self, new_zoom: float, screen_point):
        """
        Mantém o ponto da tela "parado" ao dar zoom, como no Godot.
        """
        screen_w, screen_h = self._screen_size()
        screen_center = pygame.Vector2(screen_w / 2, screen_h / 2)
        screen_point = pygame.Vector2(screen_point)

        # mundo antes do zoom
        world_before = (screen_point - screen_center) / self.zoom + self.position

        # aplica zoom com limites
        self.zoom = max(self.min_zoom, min(self.max_zoom, new_zoom))

        # recalcula posição da câmera para manter o mesmo ponto
        self.position = world_before - (screen_point - screen_center) / self.zoom

    def _pan_with_delta(self, rel):
        """
        Aplica pan em função do delta de movimento (mouse ou touch).
        O pan ajusta a velocidade conforme o zoom:
        - pouco zoom (longe) => anda mais rápido
        - muito zoom (perto) => anda mais devagar (mais delicado)
        """
        PAN_BASE_SPEED = 3.0
        zoom_factor = max(self.zoom, 0.05)
        move = rel * (PAN_BASE_SPEED / zoom_factor)
        self.position -= move

    # -----------------------
    # Eventos de toque
    # -----------------------

    def _handle_finger_down(self, event):
        screen_w, screen_h = self._screen_size()
        pos = pygame.Vector2(event.x * screen_w, event.y * screen_h)
        self.touches[event.finger_id] = pos

        if len(self.touches) == 1:
            # 1 dedo: pan
            self._dragging = True
            self.is_dragging = True
            self._last_mouse_pos = pos  # reaproveita lógica de pan
        elif len(self.touches) == 2:
            # 2 dedos: inicia pinch
            fingers = list(self.touches.values())
            self.last_pinch_dist = fingers[0].distance_to(fingers[1])

    def _handle_finger_up(self, event):
        if event.finger_id in self.touches:
            del self.touches[event.finger_id]

        if len(self.touches) == 0:
            self._dragging = False
            self.is_dragging = False
            self.last_pinch_dist = None
        elif len(self.touches) == 1:
            # Volta para pan de 1 dedo
            # atualiza referência de posição
            remaining_pos = list(self.touches.values())[0]
            self._last_mouse_pos = remaining_pos
            self.last_pinch_dist = None

    def _handle_finger_motion(self, event):
        screen_w, screen_h = self._screen_size()
        new_pos = pygame.Vector2(event.x * screen_w, event.y * screen_h)

        # posição anterior desse dedo
        old_pos = self.touches.get(event.finger_id, new_pos)
        self.touches[event.finger_id] = new_pos

        if len(self.touches) == 1:
            # Pan com 1 dedo
            rel = new_pos - old_pos
            self._dragging = True
            self.is_dragging = True
            self._pan_with_delta(rel)

        elif len(self.touches) == 2:
            # Pinch-zoom com 2 dedos
            fingers = list(self.touches.values())
            p1, p2 = fingers[0], fingers[1]
            new_dist = p1.distance_to(p2)

            if self.last_pinch_dist is not None and self.last_pinch_dist > 0:
                # se distância aumentou -> zoom "para dentro" (aproxima)
                # se diminuiu -> zoom "para fora" (afasta)
                dist_ratio = new_dist / self.last_pinch_dist

                # pequeno amortecimento pra não ficar nervoso
                if dist_ratio > 1.01:
                    # "aproxima" (coerente com o que você já tinha no scroll)
                    new_zoom = self.zoom * 0.9
                    pinch_center = (p1 + p2) / 2
                    self._apply_zoom_around_point(new_zoom, pinch_center)

                elif dist_ratio < 0.99:
                    # "afasta"
                    new_zoom = self.zoom * 1.1
                    pinch_center = (p1 + p2) / 2
                    self._apply_zoom_around_point(new_zoom, pinch_center)

            self.last_pinch_dist = new_dist

    # -----------------------
    # Eventos gerais (mouse + touch)
    # -----------------------

    def handle_event(self, event):
        """
        Processa eventos de mouse + touch.
        """

        # --- TOUCH / FINGER ---
        if event.type == pygame.FINGERDOWN:
            self._handle_finger_down(event)
            return

        if event.type == pygame.FINGERUP:
            self._handle_finger_up(event)
            return

        if event.type == pygame.FINGERMOTION:
            self._handle_finger_motion(event)
            return

        # Se há toques ativos, ignoramos pan via mouse para não misturar
        if self.touches:
            return

        # --- MOUSE ---
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 3 and self.pan_enabled:
                # botão direito inicia pan
                self._dragging = True
                self.is_dragging = True
                self._last_mouse_pos = pygame.Vector2(event.pos)

            # scroll para zoom
            elif event.button == 4:  # rolar para cima
                new_zoom = self.zoom * 0.9
                self._apply_zoom_around_point(new_zoom, event.pos)

            elif event.button == 5:  # rolar para baixo
                new_zoom = self.zoom * 1.1
                self._apply_zoom_around_point(new_zoom, event.pos)

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 3:
                self._dragging = False
                self.is_dragging = False

        elif event.type == pygame.MOUSEMOTION:
            if self._dragging and self.pan_enabled:
                rel = pygame.Vector2(event.rel)
                self._pan_with_delta(rel)
