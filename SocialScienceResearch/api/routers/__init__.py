"""Phase B-D endpoint routers (split so modules build in parallel).

Each router module owns its endpoints, response models and service wiring and
is included by ``create_app``. Routers read ``request.app.state.services`` /
``request.app.state.settings`` and lazily build their own services so no two
modules ever edit ``api.app`` at once.
"""
