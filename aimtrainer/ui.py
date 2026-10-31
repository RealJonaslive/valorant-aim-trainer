"""Minimale Maus-UI fuer das Menue: Buttons, Textfelder, Schalter, Schieberegler.

Widgets werden jeden Frame aus dem aktuellen Zustand neu aufgebaut; fluechtiger
UI-Zustand (welches Feld fokussiert ist, welcher Regler gezogen wird) liegt in UIState.
"""
import pygame

BG, PANEL, FIELD, HOVER = (16, 18, 24), (26, 29, 38), (40, 44, 56), (58, 64, 80)
ACCENT, TEXT, MUTED = (255, 70, 85), (232, 232, 238), (150, 152, 165)
GOOD, WARN, HIGHLIGHT = (120, 255, 140), (255, 140, 90), (255, 220, 120)


class Fonts:
    def __init__(self):
        self.small = pygame.font.SysFont("segoeui", 15)
        self.normal = pygame.font.SysFont("segoeui", 18)
        self.body = pygame.font.SysFont("segoeui", 16)
        self.bold = pygame.font.SysFont("segoeui", 18, bold=True)
        self.big = pygame.font.SysFont("segoeui", 24, bold=True)
        self.title = pygame.font.SysFont("segoeui", 32, bold=True)
        self.mono = pygame.font.SysFont("consolas", 16)


class UIState:
    def __init__(self):
        self.focus = None   # Key des fokussierten Textfelds
        self.drag = None    # Key des gezogenen Schiebereglers


def wrap(text, font, width):
    lines = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            test = f"{line} {word}".strip()
            if font.size(test)[0] <= width or not line:
                line = test
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def draw_wrapped(surf, text, font, color, x, y, width, spacing=4):
    for line in wrap(text, font, width):
        surf.blit(font.render(line, True, color), (x, y))
        y += font.get_height() + spacing
    return y


def card(surf, rect, fonts=None, title=None, border=None):
    """Hintergrund-Kachel fuer zusammengehoerige Inhalte."""
    rect = pygame.Rect(rect)
    pygame.draw.rect(surf, PANEL, rect, border_radius=10)
    if border:
        pygame.draw.rect(surf, border, rect, 2, border_radius=10)
    if title:
        surf.blit(fonts.big.render(title, True, TEXT), (rect.x + 20, rect.y + 14))
    return rect


def text_height(text, font, width, spacing=4):
    return len(wrap(text, font, width)) * (font.get_height() + spacing)


def _clicked(e, rect):
    return e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and rect.collidepoint(e.pos)


class Button:
    def __init__(self, rect, label, on_click, selected=False, swatch=None, sub=None, font="bold"):
        self.rect, self.label, self.on_click = pygame.Rect(rect), label, on_click
        self.selected, self.swatch, self.sub, self.font = selected, swatch, sub, font

    def handle(self, e, st):
        if _clicked(e, self.rect):
            self.on_click()
            return True
        return False

    def draw(self, surf, fonts, st):
        hover = self.rect.collidepoint(pygame.mouse.get_pos())
        bg = ACCENT if self.selected else (HOVER if hover else FIELD)
        pygame.draw.rect(surf, bg, self.rect, border_radius=6)
        if self.swatch:
            inner = self.rect.inflate(-10, -10)
            pygame.draw.rect(surf, self.swatch, inner, border_radius=4)
            return
        font = getattr(fonts, self.font)
        if self.sub:   # Karte mit Titel + Beschreibung
            surf.blit(font.render(self.label, True, TEXT), (self.rect.x + 14, self.rect.y + 10))
            draw_wrapped(surf, self.sub, fonts.small, TEXT if self.selected else MUTED,
                         self.rect.x + 14, self.rect.y + 38, self.rect.w - 28, 2)
        else:
            img = font.render(self.label, True, TEXT)
            surf.blit(img, img.get_rect(center=self.rect.center))


class TextField:
    """Zahlenfeld (Standard) oder Textfeld (text=True, mit Strg+V zum Einfügen)."""

    def __init__(self, rect, label, store, key, text=False, max_len=8, placeholder=""):
        self.rect, self.label, self.store, self.key = pygame.Rect(rect), label, store, key
        self.text, self.max_len, self.placeholder = text, max_len, placeholder

    def _allowed(self, ch):
        return ch.isprintable() if self.text else (ch.isdigit() or ch in ".,")

    def handle(self, e, st):
        if _clicked(e, self.rect):
            st.focus = self.key
            return True
        if e.type == pygame.KEYDOWN and st.focus == self.key:
            value = self.store[self.key]
            if e.key == pygame.K_BACKSPACE:
                value = "" if e.mod & pygame.KMOD_CTRL else value[:-1]
            elif e.key == pygame.K_v and e.mod & pygame.KMOD_CTRL:
                try:
                    clip = pygame.scrap.get_text() or ""
                except pygame.error:
                    clip = ""
                value += "".join(ch for ch in clip.strip() if self._allowed(ch))
            elif e.unicode and self._allowed(e.unicode) and not e.mod & pygame.KMOD_CTRL:
                value += e.unicode if self.text else e.unicode.replace(",", ".")
            else:
                return False
            self.store[self.key] = value[:self.max_len]
            return True
        return False

    def draw(self, surf, fonts, st):
        surf.blit(fonts.small.render(self.label, True, MUTED), (self.rect.x, self.rect.y - 20))
        focused = st.focus == self.key
        pygame.draw.rect(surf, FIELD, self.rect, border_radius=5)
        pygame.draw.rect(surf, ACCENT if focused else HOVER, self.rect, 2, border_radius=5)
        caret = "|" if focused and pygame.time.get_ticks() // 500 % 2 else ""
        font = fonts.body if self.text else fonts.big
        value = self.store[self.key]
        if not value and not focused and self.placeholder:
            img = font.render(self.placeholder, True, MUTED)
        else:
            img = font.render(value + caret, True, TEXT)
        inner = self.rect.inflate(-20, 0)
        # zu langer Text: das Ende anzeigen (dort wird getippt)
        x = inner.x if img.get_width() <= inner.w else inner.right - img.get_width()
        old = surf.get_clip()
        surf.set_clip(inner.clip(old) if old else inner)
        surf.blit(img, (x, self.rect.centery - img.get_height() // 2))
        surf.set_clip(old)


class Toggle:
    def __init__(self, rect, label, get, set_):
        self.rect, self.label, self.get, self.set = pygame.Rect(rect), label, get, set_

    def handle(self, e, st):
        if _clicked(e, self.rect):
            self.set(not self.get())
            return True
        return False

    def draw(self, surf, fonts, st):
        on = self.get()
        box = pygame.Rect(self.rect.x, self.rect.centery - 10, 38, 20)
        pygame.draw.rect(surf, ACCENT if on else FIELD, box, border_radius=10)
        knob_x = box.right - 10 if on else box.x + 10
        pygame.draw.circle(surf, TEXT, (knob_x, box.centery), 8)
        surf.blit(fonts.normal.render(self.label, True, TEXT), (box.right + 10, self.rect.centery - 12))


class Slider:
    def __init__(self, rect, label, get, set_, lo, hi, step, key, fmt="{:.0f}"):
        self.rect, self.label, self.get, self.set = pygame.Rect(rect), label, get, set_
        self.lo, self.hi, self.step, self.key, self.fmt = lo, hi, step, key, fmt

    def _track(self):
        return pygame.Rect(self.rect.x + 130, self.rect.centery - 3, self.rect.w - 190, 6)

    def _set_from_x(self, x):
        tr = self._track()
        k = min(1.0, max(0.0, (x - tr.x) / tr.w))
        v = self.lo + round(k * (self.hi - self.lo) / self.step) * self.step
        self.set(round(v, 4) if isinstance(self.step, float) else int(v))

    def handle(self, e, st):
        if _clicked(e, self.rect.inflate(0, 6)):
            st.drag = self.key
            self._set_from_x(e.pos[0])
            return True
        if e.type == pygame.MOUSEMOTION and st.drag == self.key:
            self._set_from_x(e.pos[0])
            return True
        if e.type == pygame.MOUSEBUTTONUP and st.drag == self.key:
            st.drag = None
            return True
        return False

    def draw(self, surf, fonts, st):
        surf.blit(fonts.small.render(self.label, True, MUTED), (self.rect.x, self.rect.centery - 10))
        tr = self._track()
        pygame.draw.rect(surf, FIELD, tr, border_radius=3)
        k = (self.get() - self.lo) / (self.hi - self.lo)
        pygame.draw.rect(surf, ACCENT, (tr.x, tr.y, int(tr.w * k), tr.h), border_radius=3)
        pygame.draw.circle(surf, TEXT, (tr.x + int(tr.w * k), tr.centery), 8)
        surf.blit(fonts.small.render(self.fmt.format(self.get()), True, TEXT), (tr.right + 14, self.rect.centery - 10))
