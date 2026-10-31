"""First-Person-Kamera mit exakter Valorant-Rotation.

Koordinatensystem (Meter): +x rechts, +y oben, +z vorne. Die Kamera steht fest
im Ursprung auf Augenhoehe, nur die Blickrichtung aendert sich.
Yaw wird bewusst NICHT auf 0..360 gewrappt, damit keine Rundungsspruenge
entstehen; die Kamera akkumuliert in float64 (keine Count-Verluste).
"""
import math

from .valorant_math import deg_per_count, wrap180

PITCH_LIMIT = 89.0


class Camera:
    def __init__(self, sens: float, eye_height: float = 1.6):
        self.sens = sens
        self.yaw = 0.0      # Grad, positiv = nach rechts
        self.pitch = 0.0    # Grad, positiv = nach oben
        self.pos = (0.0, eye_height, 0.0)

    def apply_counts(self, dx: int, dy: int) -> None:
        """Rohe Maus-Counts -> Rotation. Identisch zu Valorant: linear, kein Smoothing."""
        k = deg_per_count(self.sens)
        self.yaw += dx * k
        self.pitch -= dy * k   # Maus nach vorne (dy < 0) = nach oben schauen
        self.pitch = max(-PITCH_LIMIT, min(PITCH_LIMIT, self.pitch))

    # --- Basisvektoren -------------------------------------------------
    def basis(self):
        y, p = math.radians(self.yaw), math.radians(self.pitch)
        sy, cy, sp, cp = math.sin(y), math.cos(y), math.sin(p), math.cos(p)
        forward = (sy * cp, sp, cy * cp)
        right = (cy, 0.0, -sy)
        up = (-sy * sp, cp, -cy * sp)
        return forward, right, up

    def to_camera_space(self, point, basis=None):
        """Welt -> Kameraraum (x rechts, y oben, z Tiefe)."""
        forward, right, up = basis or self.basis()
        d = (point[0] - self.pos[0], point[1] - self.pos[1], point[2] - self.pos[2])
        return (_dot(d, right), _dot(d, up), _dot(d, forward))

    def angles_to(self, point):
        """Absolute Yaw/Pitch (Grad), unter denen ein Weltpunkt von der Kamera aus liegt."""
        dx, dy, dz = (point[0] - self.pos[0], point[1] - self.pos[1], point[2] - self.pos[2])
        return math.degrees(math.atan2(dx, dz)), math.degrees(math.atan2(dy, math.hypot(dx, dz)))

    def angular_error_to(self, point):
        """Signierter Fehler (Grad) Ziel - Fadenkreuz. Yaw mit cos(pitch) skaliert,
        damit der Wert dem echten Bildschirmwinkel entspricht."""
        ty, tp = self.angles_to(point)
        return wrap180(ty - self.yaw) * math.cos(math.radians(tp)), tp - self.pitch

    def ray_hits_sphere(self, center, radius) -> bool:
        forward, _, _ = self.basis()
        d = (center[0] - self.pos[0], center[1] - self.pos[1], center[2] - self.pos[2])
        t = _dot(d, forward)
        if t <= 0:
            return False
        closest_sq = _dot(d, d) - t * t
        return closest_sq <= radius * radius


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
