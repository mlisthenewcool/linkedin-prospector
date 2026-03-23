"""Moteur Jinja2 pour les messages personnalisés."""

from __future__ import annotations

import structlog
from jinja2 import Environment, FileSystemLoader

from src.config import TEMPLATES_DIR, Config

logger = structlog.get_logger()


class TemplateEngine:
    def __init__(self, config: Config) -> None:
        self.config = config
        templates_dir = TEMPLATES_DIR
        if not templates_dir.exists():
            raise FileNotFoundError(f"Dossier templates introuvable : {templates_dir}")
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=False,  # noqa: S701 — templates plain text, pas HTML
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_name: str, **context) -> str:
        """Rend un template avec le contexte donné."""
        # Ajouter les infos utilisateur au contexte
        context.setdefault("user_first_name", self.config.user.first_name)
        context.setdefault("user_last_name", self.config.user.last_name)
        context.setdefault("user_title", self.config.user.title)

        template = self.env.get_template(template_name)
        rendered = template.render(**context).strip()
        logger.debug("Template rendu", template=template_name, chars=len(rendered))
        return rendered

    def render_first_message(
        self,
        first_name: str,
        company: str | None = None,
        headline: str | None = None,
    ) -> str:
        return self.render(
            "first_message.txt.j2",
            first_name=first_name,
            company=company or "",
            headline=headline or "",
        )

    def render_followup(self, first_name: str) -> str:
        return self.render(
            "follow_up.txt.j2",
            first_name=first_name,
        )
